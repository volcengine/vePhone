import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { readFileSync } from "node:fs";
import { afterEach, expect, it, vi } from "vitest";

import type {
  PlanExecutionResponse,
  PodPoolResponse,
  TestCaseListResponse,
  TestPlan,
} from "../../web/api/types";
import { expectCsrf, renderApp, server, user } from "./setup";

const STYLES = readFileSync("web/styles.css", "utf8");

const plan: TestPlan = {
  id: "plan_1",
  name: "登录与账号核心回归",
  description: "运行配置测试",
  test_type: "new_feature",
  tags: [],
  case_ids: ["case_1", "case_2"],
  case_count: 2,
  execution_count: 0,
  latest_execution: null,
  created_by: "admin",
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-29T12:03:00Z",
};

const planCases: TestCaseListResponse = {
  items: [
    {
      id: "case_1",
      title: "登录主流程",
      module: "账号",
      content_markdown: "## 执行任务\n登录",
      tags: ["P0"],
      automation_level: "auto",
      execution_count: 0,
      pass_count: 0,
      fail_count: 0,
      last_executed_at: null,
      created_by: "admin",
      created_at: "2026-07-20T00:00:00Z",
      updated_at: "2026-07-20T00:00:00Z",
    },
    {
      id: "case_2",
      title: "退出登录校验",
      module: "账号",
      content_markdown: "## 执行任务\n退出登录",
      tags: ["P1"],
      automation_level: "auto",
      execution_count: 0,
      pass_count: 0,
      fail_count: 0,
      last_executed_at: null,
      created_by: "admin",
      created_at: "2026-07-20T00:00:00Z",
      updated_at: "2026-07-20T00:00:00Z",
    },
  ],
  total: 2,
  page: 1,
  page_size: 100,
};

function makePlanCases(count: number): TestCaseListResponse {
  return {
    items: Array.from({ length: count }, (_, index) => {
      const position = index + 1;
      return {
        id: `case_${position}`,
        title: `计划用例 ${position}`,
        module: "账号",
        content_markdown: `## 执行任务\n执行第 ${position} 个用例`,
        tags: [],
        automation_level: "auto",
        execution_count: 0,
        pass_count: 0,
        fail_count: 0,
        last_executed_at: null,
        created_by: "admin",
        created_at: "2026-07-20T00:00:00Z",
        updated_at: "2026-07-20T00:00:00Z",
      };
    }),
    total: count,
    page: 1,
    page_size: 100,
  };
}

const pool: PodPoolResponse = {
  refreshed_at: "2026-07-29T12:03:00Z",
  items: [{
    product_id: "product_1",
    pod_id: "pod_1",
    pod_name: "pod_1",
    pod_status_code: 2,
    stream_status: null,
    discovery_state: "active",
    local_state: "available",
    image_id: null,
    image_name: null,
    aosp_version: "13",
    display_layout_id: null,
    dc_id: null,
    dc_name: null,
    isp_code: null,
    region: null,
    zone_id: null,
    config_code: null,
    config_name: "通用型",
    config_type: null,
    server_type_code: null,
    intranet_ip: null,
    adb_address: null,
    adb_status: null,
    data_size: null,
    data_size_used: null,
    pod_created_at: null,
    last_seen_at: "2026-07-29T12:03:00Z",
    last_checked_at: null,
    request_id: null,
    task_id: null,
    task_status: null,
    task_scenario: null,
    eip_address: null,
  }],
};

const multiPodPool: PodPoolResponse = {
  ...pool,
  items: [
    pool.items[0],
    {
      ...pool.items[0],
      pod_id: "pod_2",
      pod_name: "回归设备 2",
    },
  ],
};

const noOnlinePool: PodPoolResponse = {
  ...pool,
  items: [
    {
      ...pool.items[0],
      pod_id: "pod-abnormal",
      pod_name: "异常设备",
      pod_status_code: 4,
      local_state: "unavailable",
      task_id: null,
      task_status: null,
    },
  ],
};

function withPodState(
  localState: PodPoolResponse["items"][number]["local_state"],
  discoveryState: PodPoolResponse["items"][number]["discovery_state"] = "active",
): PodPoolResponse {
  return {
    ...pool,
    items: pool.items.map((pod) => ({
      ...pod,
      discovery_state: discoveryState,
      local_state: localState,
      task_id: localState === "available" ? null : "task_busy",
      task_status: localState === "available" ? null : "running",
    })),
  };
}

const execution = {
  id: "execution_created",
  test_plan_id: "plan_1",
  task_batch_id: "batch_created",
  plan_name_snapshot: plan.name,
  plan_tags_snapshot: [],
  case_ids_snapshot: plan.case_ids,
  device_strategy_snapshot: "specified",
  pod_ids_snapshot: ["pod_1"],
  concurrency_snapshot: 1,
  runner_type_snapshot: "mock",
  config_snapshot: { source: "custom" },
  created_by: "admin",
  created_at: "2026-07-29T12:03:00Z",
  batch: { tasks: [] },
} as unknown as PlanExecutionResponse;

function useRunHandlers(
  callback: (body: Record<string, unknown>) => Response,
) {
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(plan)),
    http.get("/api/v1/test-plans/plan_1/cases", () =>
      HttpResponse.json(planCases)),
    http.post("/api/v1/pod-pool/refresh", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json(pool);
    }),
    http.post("/api/v1/test-plans/plan_1/executions", async ({ request }) => {
      expectCsrf(request);
      return callback(await request.json() as Record<string, unknown>);
    }),
  );
}

afterEach(() => {
  vi.useRealTimers();
});

it("removes run test type selection and exposes stable execution controls", async () => {
  useRunHandlers(() => HttpResponse.json(execution, { status: 201 }));
  renderApp("/test-plans/plan_1/run");

  await screen.findByRole("heading", { name: "运行测试计划" });
  expect(screen.queryByLabelText("测试类型")).not.toBeInTheDocument();
  expect(screen.queryByText("选择本次执行目标")).not.toBeInTheDocument();
  expect(screen.getByText("登录主流程")).toBeVisible();
  expect(screen.getByText("case_1")).toBeVisible();
  expect(STYLES).toMatch(
    /\.plan-run-case-strip\s*\{[^}]*grid-template-columns:\s*1fr;[^}]*max-height:\s*180px;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-device-row\s*\{[^}]*display:\s*grid;[^}]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\);/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-strategy-grid\s*\{[^}]*display:\s*contents;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-strategy-grid > label\s*\{[^}]*height:\s*74px;[^}]*min-height:\s*74px;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-concurrency\s*\{[^}]*grid-template-areas:\s*"label input" "hint input";[^}]*height:\s*74px;[^}]*min-height:\s*74px;/s,
  );
  expect(STYLES).toMatch(
    /\.checkbox-row \.checkbox-box\s*\{[^}]*flex:\s*0 0 18px;[^}]*height:\s*18px;[^}]*width:\s*18px;/s,
  );
  expect(screen.queryByLabelText("执行超时时间")).not.toBeInTheDocument();
  expect(
    screen.getByRole("radiogroup", { name: "代理任务配置" }),
  ).toHaveClass("execution-agent-mode-seg");
  expect(
    screen.getByRole("radio", { name: "按用例默认配置" }),
  ).toBeVisible();
  expect(
    screen.getByRole("radio", { name: "自定义本次计划配置" }),
  ).toBeVisible();
  expect(STYLES).toMatch(
    /\.execution-agent-mode-seg\s*\{[^}]*grid-auto-flow:\s*column;[^}]*grid-auto-columns:\s*minmax\(0,\s*1fr\);/s,
  );
  expect(STYLES).toMatch(
    /\.agent-mode-seg-option\s*\{[^}]*min-height:\s*44px;/s,
  );
  expect(STYLES).toMatch(
    /\.execution-config-hint\s*\{[^}]*font-size:\s*0\.76rem;[^}]*padding:\s*0\.55rem 0\.7rem;/s,
  );
  const concurrency = screen.getByLabelText("设备并发数");
  expect(concurrency).toHaveAttribute("name", "concurrency");
  expect(concurrency).toHaveAttribute("autocomplete", "off");

  await user.click(screen.getByRole("radio", { name: "自定义本次计划配置" }));
  expect(screen.queryByLabelText("ThreadId")).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/UseBase64Screenshot/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/IsScreenRecord/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText("GpsInfo")).not.toBeInTheDocument();
  expect(screen.getByLabelText("请求 Header（JSON 对象）")).toHaveAttribute(
    "placeholder",
    '{"X-Env":"test","X-Request-Source":"cua"}',
  );

  await user.click(screen.getByRole("radio", { name: "指定设备" }));
  expect(screen.queryByRole("button", { name: /选择设备/ }))
    .not.toBeInTheDocument();
  expect(await screen.findByLabelText("搜索设备")).toHaveClass(
    "plan-run-pod-search-input",
  );
  expect(await screen.findByRole("group", { name: "设备选择" }))
    .toBeVisible();
  expect(screen.getByText("可选设备")).toBeVisible();
  expect(screen.getAllByText("0 / 1").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByLabelText("pod_1 pod_1")).toHaveAttribute(
    "name",
    "pod_ids",
  );
  expect(STYLES).toMatch(
    /\.plan-run-pod-panel\s*\{[^}]*border:\s*1px solid var\(--mua-primary-200\);[^}]*overflow:\s*hidden;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-device-select\s*\{[^}]*max-width:\s*none;[^}]*width:\s*100%;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-pod-toolbar\s*\{[^}]*display:\s*grid;[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\) auto;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-pod-search-input\s*\{[^}]*height:\s*34px;[^}]*padding-left:\s*0\.7rem;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-pod-list\s*\{[^}]*grid-template-columns:\s*1fr;[^}]*max-height:\s*240px;[^}]*overflow-y:\s*auto;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-pod-option\s*\{[^}]*grid-template-columns:\s*18px minmax\(0,\s*1fr\) auto;[^}]*min-height:\s*40px;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-pod-option\.selected::before\s*\{[^}]*background:\s*var\(--mua-primary\);/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-strategy-grid input\[type="radio"\]\s*\{[^}]*accent-color:\s*var\(--mua-primary\);[^}]*box-shadow:\s*none;/s,
  );
  expect(STYLES).not.toMatch(
    /\.plan-run-strategy-grid input\[type="radio"\]\s*\{[^}]*appearance:\s*none;/s,
  );
  expect(STYLES).not.toMatch(/\.plan-run-pod-menu\s*\{[^}]*position:\s*absolute;/s);
  expect(STYLES).toMatch(
    /\.agent-mode-seg-option\s*\{[^}]*position:\s*relative;/s,
  );
});

it("pins the run action bar to the bottom so no empty space follows it", () => {
  const block = STYLES.match(/\.plan-run-actions\s*\{[^}]*\}/s);
  expect(block).not.toBeNull();
  // Anchored to the bottom of the page, not floating over content
  expect(block![0]).not.toMatch(/position:\s*sticky/);
  expect(block![0]).not.toMatch(/position:\s*fixed/);
  expect(block![0]).toMatch(/margin-top:\s*auto/);
  expect(block![0]).toMatch(/justify-content:\s*flex-end/);
  expect(block![0]).toMatch(/border-top:\s*1px solid var\(--mua-border\)/);
  // The page fills the visible content area so the action bar sits at its base
  expect(STYLES).toMatch(
    /\.test-plan-run-page\s*\{[^}]*min-height:\s*calc\(100vh/s,
  );
  expect(STYLES).toMatch(
    /@media \(min-width:\s*901px\)\s*\{[^}]*html,\s*body,\s*#root\s*\{[^}]*height:\s*100%;[^}]*overflow:\s*hidden;/s,
  );
});

it("removes submit summary from the plan run page", async () => {
  useRunHandlers(() => HttpResponse.json(execution, { status: 201 }));
  renderApp("/test-plans/plan_1/run");

  await screen.findByRole("heading", { name: "运行测试计划" });

  expect(screen.queryByText("提交摘要")).not.toBeInTheDocument();
  expect(screen.queryByText("确认将创建的执行记录")).not.toBeInTheDocument();
});

it("paginates the plan scope when many cases are bound", async () => {
  const cases = makePlanCases(12);
  const largePlan: TestPlan = {
    ...plan,
    case_ids: cases.items.map((item) => item.id),
    case_count: cases.total,
  };
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(largePlan)),
    http.get("/api/v1/test-plans/plan_1/cases", () =>
      HttpResponse.json(cases)),
    http.post("/api/v1/pod-pool/refresh", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json(pool);
    }),
    http.post("/api/v1/test-plans/plan_1/executions", () =>
      HttpResponse.json(execution, { status: 201 })),
  );

  renderApp("/test-plans/plan_1/run");

  expect(await screen.findByText("计划用例 1")).toBeVisible();
  expect(screen.getByText("计划用例 10")).toBeVisible();
  expect(screen.queryByText("计划用例 11")).not.toBeInTheDocument();
  expect(screen.getByLabelText("分页")).toBeVisible();

  await user.click(screen.getByRole("button", { name: "下一页" }));

  expect(await screen.findByText("计划用例 11")).toBeVisible();
  expect(screen.getByText("计划用例 12")).toBeVisible();
  expect(screen.queryByText("计划用例 1")).not.toBeInTheDocument();
});

it("keeps device selection embedded inside the section card", () => {
  expect(STYLES).toMatch(
    /\.plan-run-section\s*\{[^}]*overflow:\s*visible;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-run-pod-panel\s*\{[^}]*position:\s*relative;/s,
  );
});

it("submits specified devices and shared custom execution fields", async () => {
  let body: Record<string, unknown> | null = null;
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(plan)),
    http.get("/api/v1/test-plans/plan_1/cases", () =>
      HttpResponse.json(planCases)),
    http.post("/api/v1/pod-pool/refresh", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json(multiPodPool);
    }),
    http.post("/api/v1/test-plans/plan_1/executions", async ({ request }) => {
      expectCsrf(request);
      body = await request.json() as Record<string, unknown>;
      return HttpResponse.json(execution, { status: 201 });
    }),
  );
  renderApp("/test-plans/plan_1/run");

  expect(await screen.findByText("2 个用例")).toBeVisible();
  await user.click(screen.getByRole("radio", { name: "指定设备" }));
  fireEvent.change(screen.getByLabelText("设备并发数"), {
    target: { value: "2" },
  });
  fireEvent.change(screen.getByLabelText("设备不可用后最大等待时间（秒）"), {
    target: { value: "90" },
  });
  await user.click(await screen.findByLabelText("pod_1 pod_1"));
  await user.click(screen.getByLabelText("回归设备 2 pod_2"));
  await user.click(screen.getByRole("radio", { name: "自定义本次计划配置" }));
  fireEvent.change(screen.getByLabelText("任务超时 Timeout（秒）"), {
    target: { value: "789" },
  });
  fireEvent.change(screen.getByLabelText("CallbackInfo（JSON 对象）"), {
    target: {
      value: '{"url":"https://callback.example.com","authorization":"Bearer secret"}',
    },
  });
  fireEvent.change(screen.getByLabelText("McpJson（JSON 字符串）"), {
    target: { value: '{"headers":{"Authorization":"Bearer mcp-secret"}}' },
  });
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));

  await waitFor(() => expect(body).not.toBeNull());
  expect(body).toMatchObject({
    test_type: "new_feature",
    device_strategy: "specified",
    pod_ids: ["pod_1", "pod_2"],
    concurrency: 2,
    device_wait_timeout_seconds: 90,
    timeout_seconds: 789,
    agent_config_mode: "custom",
    agent_options: expect.objectContaining({
      timeout_seconds: 789,
      callback_info: expect.objectContaining({
        authorization: "Bearer secret",
      }),
      mcp_json: expect.stringContaining("mcp-secret"),
    }),
  });
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
});

it("shows a friendly validation message when selected pods exceed concurrency", async () => {
  let executionRequests = 0;
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(plan)),
    http.get("/api/v1/test-plans/plan_1/cases", () =>
      HttpResponse.json(planCases)),
    http.post("/api/v1/pod-pool/refresh", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json(multiPodPool);
    }),
    http.post("/api/v1/test-plans/plan_1/executions", () => {
      executionRequests += 1;
      return HttpResponse.json(execution, { status: 201 });
    }),
  );
  renderApp("/test-plans/plan_1/run");

  await user.click(await screen.findByRole("radio", { name: "指定设备" }));
  fireEvent.change(screen.getByLabelText("设备并发数"), {
    target: { value: "2" },
  });
  await user.click(await screen.findByLabelText("pod_1 pod_1"));
  await user.click(screen.getByLabelText("回归设备 2 pod_2"));
  expect(screen.getAllByText("2 / 2").length).toBeGreaterThanOrEqual(1);

  fireEvent.change(screen.getByLabelText("设备并发数"), {
    target: { value: "1" },
  });

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "已选择 2 台设备，超过当前设备并发数 1。请减少设备数量，或提高设备并发数后再执行。",
  );
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));
  expect(screen.getByRole("alert")).toHaveTextContent(
    "已选择 2 台设备，超过当前设备并发数 1。请减少设备数量，或提高设备并发数后再执行。",
  );
  expect(executionRequests).toBe(0);
});

it("uses the plan test type as the default run type", async () => {
  let body: Record<string, unknown> | null = null;
  useRunHandlers((value) => {
    body = value;
    return HttpResponse.json(execution, { status: 201 });
  });
  renderApp("/test-plans/plan_1/run");

  await screen.findByRole("heading", { name: "运行测试计划" });
  expect(screen.queryByLabelText("测试类型")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));

  await waitFor(() => expect(body).not.toBeNull());
  expect(body).toMatchObject({ test_type: "new_feature" });
  expect(body).toMatchObject({
    agent_config_mode: "global",
    timeout_seconds: null,
  });
});

it("blocks automatic plan run when no online CUA node is available", async () => {
  let executionRequests = 0;
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(plan)),
    http.get("/api/v1/test-plans/plan_1/cases", () =>
      HttpResponse.json(planCases)),
    http.post("/api/v1/pod-pool/refresh", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json(noOnlinePool);
    }),
    http.post("/api/v1/test-plans/plan_1/executions", () => {
      executionRequests += 1;
      return HttpResponse.json(execution, { status: 201 });
    }),
  );
  renderApp("/test-plans/plan_1/run");

  await screen.findByRole("heading", { name: "运行测试计划" });
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "当前没有可用的已在线 CUA 节点，请检查设备池状态或稍后重试。",
  );
  expect(executionRequests).toBe(0);
});

it("automatic plan run caps concurrency by available online CUA nodes", async () => {
  let executionBody: Record<string, unknown> | null = null;
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(plan)),
    http.get("/api/v1/test-plans/plan_1/cases", () =>
      HttpResponse.json(planCases)),
    http.post("/api/v1/pod-pool/refresh", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json(pool);
    }),
    http.post("/api/v1/test-plans/plan_1/executions", async ({ request }) => {
      executionBody = await request.json() as Record<string, unknown>;
      return HttpResponse.json(execution, { status: 201 });
    }),
  );
  renderApp("/test-plans/plan_1/run");

  await screen.findByRole("heading", { name: "运行测试计划" });
  fireEvent.change(screen.getByLabelText("设备并发数"), {
    target: { value: "2" },
  });
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));

  await waitFor(() => expect(executionBody).not.toBeNull());
  expect(executionBody).toMatchObject({
    device_strategy: "automatic",
    concurrency: 1,
  });
});

it("keeps the idempotency key for failed retries and changes it after config edits", async () => {
  const bodies: Array<Record<string, unknown>> = [];
  useRunHandlers((value) => {
    bodies.push(value);
    if (bodies.length < 3) {
      return HttpResponse.json({
        error: { code: "runner_execution_settings_incomplete", message: "配置不完整" },
      }, { status: 409 });
    }
    return HttpResponse.json(execution, { status: 201 });
  });
  renderApp("/test-plans/plan_1/run");

  await screen.findByRole("heading", { name: "运行测试计划" });
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("配置不完整");
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));
  await waitFor(() => expect(bodies).toHaveLength(2));
  expect(bodies[1].idempotency_key).toBe(bodies[0].idempotency_key);

  fireEvent.change(screen.getByLabelText("设备并发数"), {
    target: { value: "2" },
  });
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));
  await waitFor(() => expect(bodies).toHaveLength(3));
  expect(bodies[2].idempotency_key).not.toBe(bodies[1].idempotency_key);
});

it("validates custom JSON and submits automatic allocation without pods", async () => {
  const bodies: Array<Record<string, unknown>> = [];
  useRunHandlers((value) => {
    bodies.push(value);
    return HttpResponse.json(execution, { status: 201 });
  });
  renderApp("/test-plans/plan_1/run");

  await screen.findByRole("heading", { name: "运行测试计划" });
  await user.click(screen.getByRole("radio", { name: "自定义本次计划配置" }));
  fireEvent.change(screen.getByLabelText("CallbackInfo（JSON 对象）"), {
    target: { value: "[]" },
  });
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "CallbackInfo 必须是 JSON 对象",
  );
  expect(bodies).toHaveLength(0);

  fireEvent.change(screen.getByLabelText("CallbackInfo（JSON 对象）"), {
    target: { value: "" },
  });
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));
  await waitFor(() => expect(bodies).toHaveLength(1));
  expect(bodies[0]).toMatchObject({
    device_strategy: "automatic",
    pod_ids: [],
  });
});

it("locks fields and prevents duplicate submission while pending", async () => {
  let requests = 0;
  let resolveRequest: () => void = () => undefined;
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(plan)),
    http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(pool)),
    http.post("/api/v1/test-plans/plan_1/executions", async () => {
      requests += 1;
      await new Promise<void>((resolve) => {
        resolveRequest = resolve;
      });
      return HttpResponse.json(execution, { status: 201 });
    }),
  );
  renderApp("/test-plans/plan_1/run");

  await screen.findByRole("heading", { name: "运行测试计划" });
  const submit = screen.getByRole("button", { name: "确认并开始执行" });
  await user.click(submit);
  await waitFor(() => expect(requests).toBe(1));

  expect(screen.queryByLabelText("测试类型")).not.toBeInTheDocument();
  expect(screen.getByLabelText("设备并发数")).toBeDisabled();
  expect(screen.getByRole("radio", { name: "使用全局配置" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "正在创建执行…" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "正在创建执行…" }));
  expect(requests).toBe(1);

  resolveRequest();
});

it("allows active busy pods and submits them for queued execution", async () => {
  let refreshRequests = 0;
  let executionBody: Record<string, unknown> | null = null;
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(plan)),
    http.post("/api/v1/pod-pool/refresh", ({ request }) => {
      expectCsrf(request);
      refreshRequests += 1;
      return HttpResponse.json(withPodState("leased"));
    }),
    http.post("/api/v1/test-plans/plan_1/executions", async ({ request }) => {
      executionBody = await request.json() as Record<string, unknown>;
      return HttpResponse.json(execution, { status: 201 });
    }),
  );
  renderApp("/test-plans/plan_1/run");

  await user.click(await screen.findByRole("radio", { name: "指定设备" }));
  await user.click(await screen.findByLabelText("pod_1 pod_1"));
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));

  await waitFor(() => expect(executionBody).not.toBeNull());
  expect(executionBody).toMatchObject({
    device_strategy: "specified",
    pod_ids: ["pod_1"],
  });
  expect(refreshRequests).toBeGreaterThan(0);
});

it("removes pods that become inactive and blocks submission until reselected", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let refreshRequests = 0;
  let executionRequests = 0;
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(plan)),
    http.post("/api/v1/pod-pool/refresh", () => {
      refreshRequests += 1;
      return HttpResponse.json(
        refreshRequests === 1 ? pool : withPodState("stale", "stale"),
      );
    }),
    http.post("/api/v1/test-plans/plan_1/executions", () => {
      executionRequests += 1;
      return HttpResponse.json(execution, { status: 201 });
    }),
  );
  renderApp("/test-plans/plan_1/run");

  await user.click(await screen.findByRole("radio", { name: "指定设备" }));
  await user.click(await screen.findByLabelText("pod_1 pod_1"));
  expect(screen.getByLabelText("pod_1 pod_1")).toBeChecked();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });
  await waitFor(() => expect(refreshRequests).toBeGreaterThanOrEqual(2));
  expect(screen.queryByLabelText("pod_1 pod_1"))
    .not.toBeInTheDocument();
  expect(screen.getByText("暂无可选设备")).toBeVisible();

  fireEvent.click(screen.getByRole("button", { name: "确认并开始执行" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "设备状态已更新，请重新选择可用设备",
  );
  expect(executionRequests).toBe(0);
});

it("shows a retry action when refreshing the device pool fails", async () => {
  let refreshRequests = 0;
  let executionRequests = 0;
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(plan)),
    http.post("/api/v1/pod-pool/refresh", () => {
      refreshRequests += 1;
      if (refreshRequests === 1) {
        return HttpResponse.json(
          { error: { code: "pod_refresh_failed", message: "刷新失败" } },
          { status: 502 },
        );
      }
      return HttpResponse.json(pool);
    }),
    http.post("/api/v1/test-plans/plan_1/executions", () => {
      executionRequests += 1;
      return HttpResponse.json(execution, { status: 201 });
    }),
  );
  renderApp("/test-plans/plan_1/run");

  await user.click(await screen.findByRole("radio", { name: "指定设备" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("设备池加载失败");
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));
  expect(await screen.findByText(
    "设备池刷新失败，请重新加载设备池后再提交。",
  )).toBeVisible();
  expect(executionRequests).toBe(0);
  await user.click(screen.getByRole("button", { name: "重新加载设备池" }));

  expect(await screen.findByRole("group", { name: "设备选择" }))
    .toBeVisible();
  expect(refreshRequests).toBe(2);
});

it("caps one-hundred-case plan concurrency at the backend limit", async () => {
  const largePlan: TestPlan = {
    ...plan,
    case_ids: Array.from({ length: 100 }, (_, index) => `case_${index + 1}`),
    case_count: 100,
  };
  let executionBody: Record<string, unknown> | null = null;
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(largePlan)),
    http.post("/api/v1/pod-pool/refresh", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json({
        ...pool,
        items: Array.from({ length: 20 }, (_, index) => ({
          ...pool.items[0],
          pod_id: `pod_${index + 1}`,
          pod_name: `并发设备 ${index + 1}`,
        })),
      });
    }),
    http.post("/api/v1/test-plans/plan_1/executions", async ({ request }) => {
      executionBody = await request.json() as Record<string, unknown>;
      return HttpResponse.json(execution, { status: 201 });
    }),
  );
  renderApp("/test-plans/plan_1/run");

  const concurrency = await screen.findByRole("spinbutton", {
    name: "设备并发数",
  });
  expect(concurrency).toHaveAttribute("max", "20");
  expect(screen.getByText("最大不超过 20 个并发任务")).toBeVisible();

  fireEvent.change(concurrency, { target: { value: "99" } });
  expect(concurrency).toHaveValue(20);
  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));

  await waitFor(() => expect(executionBody).not.toBeNull());
  expect(executionBody).toMatchObject({ concurrency: 20 });
});

it("keeps execution pending when an in-flight pod refresh becomes stale", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let refreshRequests = 0;
  let executionRequests = 0;
  let resolveRefresh: () => void = () => undefined;
  let resolveExecution: () => void = () => undefined;
  server.use(
    http.get("/api/v1/test-plans/plan_1", () => HttpResponse.json(plan)),
    http.post("/api/v1/pod-pool/refresh", async () => {
      refreshRequests += 1;
      if (refreshRequests === 1) return HttpResponse.json(pool);
      await new Promise<void>((resolve) => {
        resolveRefresh = resolve;
      });
      return HttpResponse.json(withPodState("stale", "stale"));
    }),
    http.post("/api/v1/test-plans/plan_1/executions", async () => {
      executionRequests += 1;
      await new Promise<void>((resolve) => {
        resolveExecution = resolve;
      });
      return HttpResponse.json(execution, { status: 201 });
    }),
  );
  renderApp("/test-plans/plan_1/run");

  await user.click(await screen.findByRole("radio", { name: "指定设备" }));
  await user.click(await screen.findByLabelText("pod_1 pod_1"));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });
  await waitFor(() => expect(refreshRequests).toBe(2));

  await user.click(screen.getByRole("button", { name: "确认并开始执行" }));
  await waitFor(() => expect(executionRequests).toBe(1));
  resolveRefresh();
  await act(async () => {
    await Promise.resolve();
  });

  expect(screen.getByLabelText("pod_1 pod_1")).toBeChecked();
  expect(screen.queryByText("设备状态已更新，请重新选择可用设备。"))
    .not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "正在创建执行…" }))
    .toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "正在创建执行…" }));
  expect(executionRequests).toBe(1);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(6000);
  });
  expect(refreshRequests).toBe(2);

  resolveExecution();
});
