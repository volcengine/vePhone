import { expect, type Page } from "@playwright/test";

export type CreatedTask = {
  id: string;
  case_id: string;
  runner_type: string;
  execution_status: string;
  verdict: string | null;
  failure_type: string | null;
  remote_run_id: string | null;
};

export async function csrfToken(page: Page): Promise<string> {
  const cookie = (await page.context().cookies()).find(
    (item) => item.name === "csrf",
  );
  if (!cookie) throw new Error("csrf cookie not found");
  return cookie.value;
}

export async function createCaseAndTask(
  page: Page,
  {
    appUrl,
    title,
    content = `## 执行任务\n- 验证 ${title}`,
    idempotencyKey = `e2e-${title}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  }: {
    appUrl: string;
    title: string;
    content?: string;
    idempotencyKey?: string;
  },
): Promise<CreatedTask> {
  const csrf = await csrfToken(page);
  const createdCase = await page.request.post(`${appUrl}/api/v1/cases`, {
    headers: { "X-CSRF-Token": csrf },
    data: {
      title,
      module: "E2E",
      content_markdown: content,
      tags: ["e2e"],
      automation_level: "auto",
    },
  });
  expect(createdCase.status(), await createdCase.text()).toBe(201);
  const testCase = await createdCase.json() as { id: string };

  const createdTask = await page.request.post(
    `${appUrl}/api/v1/cases/${testCase.id}/execute`,
    {
      headers: { "X-CSRF-Token": csrf },
      data: {
        idempotency_key: idempotencyKey,
        agent_config_mode: "global",
      },
    },
  );
  expect(createdTask.status(), await createdTask.text()).toBe(201);
  return createdTask.json() as Promise<CreatedTask>;
}

export async function configureMockRunner(
  page: Page,
  appUrl: string,
): Promise<void> {
  const response = await page.request.put(`${appUrl}/api/v1/settings/runner`, {
    headers: { "X-CSRF-Token": await csrfToken(page) },
    data: { mode: "mock" },
  });
  expect(response.status(), await response.text()).toBe(200);
}

export async function getTask(
  page: Page,
  appUrl: string,
  taskId: string,
): Promise<CreatedTask> {
  const response = await page.request.get(`${appUrl}/api/v1/tasks/${taskId}`);
  expect(response.status(), await response.text()).toBe(200);
  return response.json() as Promise<CreatedTask>;
}

export async function cancelTask(
  page: Page,
  appUrl: string,
  taskId: string,
): Promise<CreatedTask> {
  const response = await page.request.post(
    `${appUrl}/api/v1/tasks/${taskId}/cancel`,
    {
      headers: { "X-CSRF-Token": await csrfToken(page) },
    },
  );
  expect(response.status(), await response.text()).toBe(200);
  return response.json() as Promise<CreatedTask>;
}
