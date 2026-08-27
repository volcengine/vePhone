import { expect, test, type Page } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  cancelTask,
  configureMockRunner,
  createCaseAndTask,
  getTask,
} from "./current-ui-helpers";

type TestServer = {
  process: ChildProcess;
  output: string[];
};

async function findFreePort(): Promise<number> {
  const probe = createServer();
  probe.listen(0, "127.0.0.1");
  await once(probe, "listening");
  const address = probe.address();
  if (!address || typeof address === "string") {
    probe.close();
    throw new Error("failed to allocate an E2E server port");
  }
  const port = address.port;
  probe.close();
  await once(probe, "close");
  return port;
}

async function startControlledServer(
  dataDir: string,
  holdFile: string,
  port: number,
  startLog?: string,
): Promise<TestServer> {
  const output: string[] = [];
  const child = spawn(
    "uv",
    [
      "run",
      "uvicorn",
      "controlled_server:app",
      "--app-dir",
      "tests/e2e",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
    ],
    {
      cwd: process.cwd(),
      detached: true,
      env: {
        ...process.env,
        APP_ENV: "e2e",
        APP_SECRET_KEY: "e2e-controlled-secret-key-at-least-32-bytes",
        APP_DATA_DIR: dataDir,
        E2E_RUNNER_HOLD_FILE: holdFile,
        TASK_WORKER_DRAIN_TIMEOUT_SECONDS: "1",
        ...(startLog ? { E2E_RUNNER_START_LOG: startLog } : {}),
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  child.stdout?.on("data", (chunk) => output.push(String(chunk)));
  child.stderr?.on("data", (chunk) => output.push(String(chunk)));

  const readyUrl = `http://127.0.0.1:${port}/health/ready`;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (child.exitCode !== null) {
      throw new Error(`controlled server exited early:\n${output.join("")}`);
    }
    try {
      const response = await fetch(readyUrl);
      if (response.ok) {
        return { process: child, output };
      }
    } catch {
      // The child has not bound the port yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  await stopControlledServer({ process: child, output });
  throw new Error(`controlled server did not become ready:\n${output.join("")}`);
}

async function terminateControlledServer(server: TestServer): Promise<void> {
  const pid = server.process.pid;
  if (pid && server.process.exitCode === null) {
    process.kill(-pid, "SIGTERM");
    await once(server.process, "exit");
  }
}

async function stopControlledServer(server: TestServer): Promise<void> {
  const pid = server.process.pid;
  if (pid && server.process.exitCode === null) {
    process.kill(-pid, "SIGKILL");
    await once(server.process, "exit");
  }
}

async function createControlledTask(page: Page, title: string): Promise<string> {
  const origin = new URL(page.url()).origin;
  const task = await createCaseAndTask(page, {
    appUrl: origin,
    title: "success",
    content: `## 执行任务\n- ${title}`,
  });
  await page.goto(`${origin}/tasks/${task.id}`);
  return task.id;
}

async function getTaskRunId(
  page: Page,
  appUrl: string,
  taskId: string,
): Promise<string> {
  const response = await page.request.get(`${appUrl}/api/v1/tasks/${taskId}`);
  expect(response.status(), await response.text()).toBe(200);
  const task = await response.json() as { remote_run_id?: string | null };
  return task.remote_run_id ?? "";
}

test("admin verifies success, failure, and review reports", async ({ page }) => {
  const dataDir = await mkdtemp(join(tmpdir(), "mua-mock-results-e2e-"));
  const holdFile = join(dataDir, "hold-runner");
  const port = await findFreePort();
  const appUrl = `http://localhost:${port}`;
  let server: TestServer | undefined;
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  try {
    server = await startControlledServer(dataDir, holdFile, port);
    await page.goto(appUrl);
    await page.getByLabel("用户名").fill("admin");
    await page.getByLabel("密码").fill("StrongPassword123!");
    await page.getByRole("button", { name: "创建管理员" }).click();
    await expect(page.getByRole("heading", { name: "执行记录" })).toBeVisible();
    await configureMockRunner(page, appUrl);

  async function createTask(
    scenario: "success" | "assertion_failure" | "evidence_missing",
  ) {
    const task = await createCaseAndTask(page, {
      appUrl,
      title: scenario,
    });
    await expect.poll(
      async () => (await getTask(page, appUrl, task.id))
        .execution_status,
    ).toBe("result_ready");
    return task.id;
  }

  const successId = await createTask("success");
  const failureId = await createTask("assertion_failure");
  const evidenceMissingId = await createTask("evidence_missing");

  async function verifyConsistentResult(
    taskId: string,
    scenario: string,
    verdict: "pass" | "fail",
    failureType: string | null,
    failureTypeLabel: string,
  ) {
    const current = await getTask(page, appUrl, taskId);
    expect(current).toMatchObject({
      execution_status: "result_ready",
      verdict,
      failure_type: failureType,
    });

    await page.goto(`${appUrl}/tasks`);
    const row = page.getByRole("row").filter({ hasText: taskId });
    await expect(row).toContainText(scenario);
    await expect(row).toContainText("已完成");
    await expect(row).toContainText(verdict === "pass" ? "成功" : "失败");

    await page.goto(`${appUrl}/tasks/${taskId}`);
    await expect(
      page.getByRole("heading", { name: `${scenario} 测试` }),
    ).toBeVisible();
    await expect(page.getByText("已完成", { exact: true })).toBeVisible();
    await expect(
      page.getByText(
        verdict === "pass" ? "成功" : "失败",
        { exact: true },
      ).first(),
    ).toBeVisible();
    await expect(
      page.getByText("失败类型", { exact: true }).locator(".."),
    ).toContainText(failureTypeLabel);

    const eventsResponse = await page.request.get(
      `${appUrl}/api/v1/tasks/${taskId}/events`,
    );
    expect(eventsResponse.status()).toBe(200);
    const events = await eventsResponse.json() as {
      items: Array<{ type: string }>;
    };
    expect(events.items.some((event) => event.type === "task_finished")).toBe(true);
  }

  await verifyConsistentResult(successId, "success", "pass", null, "-");
  await verifyConsistentResult(
    failureId,
    "assertion_failure",
    "fail",
    "assertion_failed",
    "断言失败",
  );
  await verifyConsistentResult(
    evidenceMissingId,
    "evidence_missing",
    "fail",
    "evidence_missing",
    "证据缺失",
  );

  await page.reload();
  await expect(
    page.getByText("失败类型", { exact: true }).locator(".."),
  ).toContainText("证据缺失");
  await expect(page.getByText("成功", { exact: true })).toHaveCount(0);

    expect(successId).toMatch(/^task_/);
    expect(failureId).toMatch(/^task_/);
    expect(evidenceMissingId).toMatch(/^task_/);
    expect(new Set([successId, failureId, evidenceMissingId]).size).toBe(3);
    const casesResponse = await page.request.get(
      `${appUrl}/api/v1/cases?page=1&page_size=10`,
    );
    expect(casesResponse.status()).toBe(200);
    const cases = await casesResponse.json() as {
      total: number;
      items: Array<{ title: string }>;
    };
    expect(cases.total).toBe(3);
    expect(cases.items.map((item) => item.title).sort()).toEqual([
      "assertion_failure",
      "evidence_missing",
      "success",
    ]);
    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);
    console.log(JSON.stringify({ successId, failureId, evidenceMissingId }));
  } finally {
    if (server) await stopControlledServer(server);
    await rm(dataDir, { recursive: true, force: true });
  }
});

test("admin cancels active tasks and a second service resumes persisted work", async ({
  page,
}) => {
  const dataDir = await mkdtemp(join(tmpdir(), "mua-loop2-e2e-"));
  const holdFile = join(dataDir, "hold-runner");
  const startLog = join(dataDir, "runner-start.log");
  const port = await findFreePort();
  const appUrl = `http://localhost:${port}`;
  let server: TestServer | undefined;

  try {
    await writeFile(holdFile, "hold");
    await writeFile(startLog, "");
    server = await startControlledServer(dataDir, holdFile, port, startLog);

    await page.goto(appUrl);
    await page.getByLabel("用户名").fill("admin");
    await page.getByLabel("密码").fill("StrongPassword123!");
    await page.getByRole("button", { name: "创建管理员" }).click();
    await expect(page.getByRole("heading", { name: "执行记录" })).toBeVisible();
    await configureMockRunner(page, appUrl);

    const runningId = await createControlledTask(page, "运行中取消");
    await expect.poll(
      async () => (await getTask(page, appUrl, runningId)).execution_status,
    ).toBe("running");
    await expect(page.getByText("执行中", { exact: true })).toBeVisible();

    const queuedId = await createControlledTask(page, "排队中取消");
    await expect.poll(
      async () => (await getTask(page, appUrl, queuedId)).execution_status,
    ).toBe("queued");
    await page.goto(`${appUrl}/tasks`);
    const queuedRow = page.getByRole("row").filter({ hasText: queuedId });
    await expect(queuedRow).toContainText("排队中");
    await expect(
      queuedRow.getByRole("button", { name: "取消", exact: true }),
    ).toBeVisible();
    await cancelTask(page, appUrl, queuedId);
    await expect.poll(
      async () => (await getTask(page, appUrl, queuedId)).execution_status,
    ).toBe("cancelled");

    await page.goto(`${appUrl}/tasks`);
    const runningRow = page.getByRole("row").filter({ hasText: runningId });
    await expect(
      runningRow.getByRole("button", { name: "取消", exact: true }),
    ).toBeVisible();
    await cancelTask(page, appUrl, runningId);
    await rm(holdFile);
    await expect.poll(
      async () => (await getTask(page, appUrl, runningId)).execution_status,
      { timeout: 10_000 },
    ).toBe("cancelled");

    await writeFile(holdFile, "hold");
    const recoveryId = await createControlledTask(page, "跨实例恢复");
    await expect.poll(
      async () => (await getTask(page, appUrl, recoveryId)).execution_status,
    ).toBe("running");
    let originalRunId = "";
    await expect.poll(
      async () => {
        originalRunId = await getTaskRunId(page, appUrl, recoveryId);
        return originalRunId;
      },
    ).not.toBe("");
    await expect(page.getByText("执行中", { exact: true })).toBeVisible();

    await terminateControlledServer(server);
    server = undefined;
    await rm(holdFile);
    server = await startControlledServer(dataDir, holdFile, port, startLog);

    await page.goto(`${appUrl}/tasks/${recoveryId}`);
    await expect.poll(
      async () => getTaskRunId(page, appUrl, recoveryId),
    ).toBe(originalRunId);
    await expect.poll(
      async () => (await getTask(page, appUrl, recoveryId)).execution_status,
      { timeout: 10_000 },
    ).toBe("result_ready");
    await page.reload();
    await expect(page.getByText("已完成", { exact: true })).toBeVisible();
    const events = await page.evaluate(async (taskId) => {
      const response = await fetch(`/api/v1/tasks/${taskId}/events`);
      return (await response.json()).items as Array<{
        sequence: number;
        type: string;
      }>;
    }, recoveryId);
    expect(events.map((event) => event.sequence)).toEqual(
      events.map((_event, index) => index + 1),
    );
    expect(events.filter((event) => event.type === "task_started")).toHaveLength(1);
    expect(
      events.filter((event) =>
        ["task_finished", "runner_interrupted", "task_cancelled"].includes(event.type),
      ),
    ).toHaveLength(1);
    expect(events.some((event) => event.type === "runner_interrupted")).toBe(false);
    const startLines = (await readFile(startLog, "utf8"))
      .trim()
      .split("\n")
      .filter((line) => line.startsWith(`${recoveryId} `));
    expect(startLines).toHaveLength(1);
    expect(startLines[0]).toBe(`${recoveryId} ${originalRunId}`);

    await page.goto(`${appUrl}/tasks/${queuedId}`);
    await expect(page.getByText("已取消", { exact: true })).toBeVisible();
  } finally {
    if (server) {
      await stopControlledServer(server);
    }
    await rm(dataDir, { recursive: true, force: true });
  }
});
