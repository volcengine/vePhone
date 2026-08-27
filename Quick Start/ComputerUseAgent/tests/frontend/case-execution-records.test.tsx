import { fireEvent, screen, within, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, it } from "vitest";

import type { TestCase } from "../../web/api/types";
import { renderApp, server, user } from "./setup";

const caseDetail: TestCase = {
  id: "case_records",
  title: "带执行记录的用例",
  module: "回归",
  content_markdown: "## 执行任务\n验证执行记录展示",
  tags: ["P0"],
  automation_level: "auto",
  default_agent_options: {
    thread_id: "thread-case-default",
    max_step: 123,
    timeout_seconds: 456,
    callback_info: { url: "https://callback.example.com" },
    output_schema: "{\"type\":\"object\"}",
    system_prompt: "custom default prompt",
    mcp_json: "{\"mcpServers\":{}}",
    max_output_tokens: 2048,
    request_headers: { "X-Env": "staging" },
  },
  execution_count: 2,
  pass_count: 1,
  fail_count: 1,
  last_executed_at: "2026-07-28T03:30:00Z",
  created_by: "admin",
  created_at: "2026-07-28T03:00:00Z",
  updated_at: "2026-07-28T03:00:00Z",
};

function task(overrides: Record<string, unknown>) {
  return {
    id: "task_default",
    case_id: "case_records",
    script_version_id: null,
    prompt_snapshot: null,
    result_summary: null,
    result_evidence: [],
    remote_thread_id: null,
    remote_status_code: null,
    remote_step_id: null,
    recording_url: null,
    result_assets: {},
    runner_type: "mock",
    scenario: "case_records",
    execution_status: "result_ready",
    verdict: "pass",
    failure_type: null,
    version: 1,
    created_at: "2026-07-28T03:30:00Z",
    started_at: "2026-07-28T03:30:00Z",
    finished_at: "2026-07-28T03:31:05Z",
    ...overrides,
  };
}

it("shows the case execution records table with task ids, results and time", async () => {
  server.use(
    http.get("/api/v1/cases/case_records", () => HttpResponse.json(caseDetail)),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["回归"] })),
    http.get("/api/v1/cases/case_records/tasks", () =>
      HttpResponse.json({
        items: [
          task({ id: "task_pass", verdict: "pass", execution_status: "result_ready" }),
          task({ id: "task_fail", verdict: "fail", execution_status: "result_ready" }),
        ],
        total: 2,
        page: 1,
        page_size: 5,
      }),
    ),
  );

  renderApp("/cases/case_records/edit");

  expect(await screen.findByText("用例结构说明")).toBeVisible();
  expect(screen.getByText("用例默认执行配置")).toBeVisible();
  expect(screen.getByText("已启用")).toBeVisible();
  expect(screen.getByText("thread-case-default")).toBeVisible();
  expect(screen.getByText("MaxStep")).toBeVisible();
  expect(screen.getByText("123")).toBeVisible();
  expect(screen.queryByLabelText("ThreadId")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "关闭配置" }));
  expect(screen.getByText("未启用默认配置，执行时使用全局或临时配置。"))
    .toBeVisible();
  expect(screen.getByRole("button", { name: "启用配置" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "启用配置" }));

  await user.click(screen.getByRole("button", { name: "编辑默认配置" }));

  expect(
    await screen.findByRole("dialog", { name: "编辑用例默认执行配置" }),
  ).toBeVisible();
  expect(screen.getByLabelText("ThreadId")).toHaveValue(
    "thread-case-default",
  );
  expect(screen.queryByLabelText(/UseBase64Screenshot/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/IsScreenRecord/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText("GpsInfo")).not.toBeInTheDocument();
  expect(screen.getByLabelText("请求 Header（JSON 对象）")).toHaveAttribute(
    "placeholder",
    '{"X-Env":"test","X-Request-Source":"cua"}',
  );
  expect(screen.getByLabelText("SystemPrompt")).toHaveValue(
    "custom default prompt",
  );
  expect(screen.getByLabelText("最大输出 Token")).toHaveValue(2048);
  await user.click(screen.getByRole("button", { name: "清除 SystemPrompt" }));
  await user.click(screen.getByRole("button", { name: "清除 CallbackInfo（JSON 对象）" }));
  await user.click(screen.getByRole("button", { name: "清除 OutputSchema（JSON 字符串）" }));
  await user.click(screen.getByRole("button", { name: "清除 McpJson（JSON 字符串）" }));
  await user.click(screen.getByRole("button", { name: "清除 请求 Header（JSON 对象）" }));
  await user.click(screen.getByRole("button", { name: "清除 最大输出 Token" }));
  expect(screen.getByLabelText("SystemPrompt")).toHaveValue("");
  expect(screen.getByLabelText("CallbackInfo（JSON 对象）")).toHaveValue("");
  expect(screen.getByLabelText("OutputSchema（JSON 字符串）")).toHaveValue("");
  expect(screen.getByLabelText("McpJson（JSON 字符串）")).toHaveValue("");
  expect(screen.getByLabelText("请求 Header（JSON 对象）")).toHaveValue("");
  expect(screen.getByLabelText("最大输出 Token")).toHaveValue(null);

  await user.click(screen.getByRole("button", { name: "完成" }));

  expect((await screen.findAllByText("执行记录")).length)
    .toBeGreaterThanOrEqual(1);

  const passId = await screen.findByText("task_pass");
  const passRow = passId.closest("tr");
  expect(passRow).not.toBeNull();
  expect(within(passRow as HTMLElement).getByText("成功")).toBeVisible();
  // Created time rendered in China timezone.
  expect(within(passRow as HTMLElement).getByText("2026-07-28 11:30:00")).toBeVisible();
  // Elapsed time between start and finish.
  expect(within(passRow as HTMLElement).getByText("1 分 5 秒")).toBeVisible();
  expect(within(passRow as HTMLElement).getByRole("link", { name: "查看" }))
    .toHaveAttribute("href", "/biz/biz_default/tasks/task_pass");

  const failRow = screen.getByText("task_fail").closest("tr");
  expect(within(failRow as HTMLElement).getByText("失败")).toBeVisible();
});

it("shows an empty state when the case has no execution records", async () => {
  const disabledCase = {
    ...caseDetail,
    default_agent_options: null,
  };
  server.use(
    http.get("/api/v1/cases/case_records", () => HttpResponse.json(disabledCase)),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["回归"] })),
    http.get("/api/v1/cases/case_records/tasks", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
  );

  renderApp("/cases/case_records/edit");

  expect(await screen.findByText("未启用")).toBeVisible();
  expect(screen.getByText("未启用默认配置，执行时使用全局或临时配置。"))
    .toBeVisible();
  expect(screen.getByRole("button", { name: "启用配置" })).toBeVisible();
  expect(await screen.findByText("该用例暂无执行记录")).toBeVisible();
});

it("keeps default execution config enabled after saving the edited case", async () => {
  let currentCase: TestCase = {
    ...caseDetail,
    default_agent_options: null,
  };
  server.use(
    http.get("/api/v1/cases/case_records", () => HttpResponse.json(currentCase)),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["回归"] })),
    http.get("/api/v1/cases/case_records/tasks", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
    http.put("/api/v1/cases/case_records", async ({ request }) => {
      const body = await request.json() as Pick<TestCase, "default_agent_options">;
      expect(body).toMatchObject({
        default_agent_options: expect.objectContaining({
          thread_id: "thread-saved",
        }),
      });
      currentCase = {
        ...currentCase,
        default_agent_options: body.default_agent_options,
        updated_at: "2026-07-28T04:00:00Z",
      };
      return HttpResponse.json(currentCase);
    }),
  );

  renderApp("/cases/case_records/edit");

  await user.click(await screen.findByRole("button", { name: "启用配置" }));
  await user.click(screen.getByRole("button", { name: "编辑默认配置" }));
  fireEvent.change(await screen.findByLabelText("ThreadId"), {
    target: { value: "thread-saved" },
  });
  await user.click(screen.getByRole("button", { name: "完成" }));
  await user.click(screen.getByRole("button", { name: "保存" }));

  await waitFor(() => {
    expect(screen.getByText("已启用")).toBeVisible();
    expect(screen.getByText("thread-saved")).toBeVisible();
  });
});
