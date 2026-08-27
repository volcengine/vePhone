import { screen, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, it } from "vitest";

import { renderApp, server } from "./setup";

const task = {
  id: "task-1",
  case_id: "case-1",
  script_version_id: null,
  prompt_snapshot: null,
  result_summary: null,
  result_evidence: [],
  runner_type: "mobile_use",
  scenario: "assertion_failure",
  execution_status: "result_ready",
  verdict: "fail",
  failure_type: "assertion_failed",
  version: 3,
  created_at: "2026-07-26T08:00:00Z",
  started_at: "2026-07-26T08:00:01Z",
  finished_at: "2026-07-26T08:00:02Z",
  remote_thread_id: "thread-1",
  remote_status_code: 3,
  remote_step_id: "finished",
  recording_url: null,
  result_assets: { usage: { in_tokens: 0, out_tokens: 0 }, screenshots: {}, files: [] },
  created_by: "admin",
};

const runtimePayload = {
  task,
  execution_config: {
    source: "custom",
    account_id: "2107192146",
    product_id: null,
    pod_id: null,
    tos_bucket: null,
    tos_endpoint: null,
    tos_region: null,
    timeout_seconds: 456,
    use_base64_screenshot: null,
    max_step: 123,
    callback_info: null,
    output_schema: null,
    retry_limit: 7,
    system_prompt: null,
    screen_record: null,
    mcp_json: null,
    max_output_tokens: null,
    gps_info: null,
    request_headers: { configured: false, names: [] },
  },
  current_step: {
    run_id: "run-1",
    thread_id: "thread-1",
    status: 6,
    step_id: "failed",
    results: [
      {
        Action: "assert",
        Param: { condition: "视频正常播放" },
        StepResult: { IsSuccess: false, Result: "断言失败：视频未自动播放" },
        Timestamp: "2026-07-26T16:00:02+08:00",
      },
    ],
  },
  thread_groups: [{
    thread_id: "thread-1",
    task_next_token: null,
    tasks: [{
      run_id: "run-1",
      thread_id: "thread-1",
      run_name: "assertion_failure",
      status: 3,
      pod_id: "pod-1",
      product_id: null,
      created_at: "2026-07-26 16:00:01 +0800 CST",
      started_at: "2026-07-26 16:00:01 +0800 CST",
      updated_at: "2026-07-26 16:00:02 +0800 CST",
      completed_at: "2026-07-26 16:00:02 +0800 CST",
      trace_id: "trace-1",
      artifact_count: { Screenshot: 0 },
    }],
  }],
  thread_steps: [{
    run_id: "run-1",
    thread_id: "thread-1",
    status: 6,
    step_id: "finished",
    results: [
      {
        Action: "assert",
        Param: { condition: "视频正常播放" },
        StepResult: { IsSuccess: false, Result: "断言失败：视频未自动播放" },
        Timestamp: "2026-07-26T16:00:02+08:00",
      },
      {
        Action: "screenshot",
        Param: { mode: "screen" },
        StepResult: {
          IsSuccess: true,
          Result: JSON.stringify({
            status: "failure",
            error: {
              code: "7000003",
              message: "screenshot command failed exit_code=255 stderr=",
            },
          }),
        },
        Timestamp: "2026-07-26T16:00:03+08:00",
      },
    ],
  }],
  result: {
    summary: "断言失败",
    evidence: ["断言失败：视频未自动播放"],
    recording_url: null,
    assets: { usage: { in_tokens: 0, out_tokens: 0 }, screenshots: {}, files: [] },
  },
  errors: {},
};

it("shows trace page with completed steps timeline for a failed task", async () => {
  server.use(
    http.get("/api/v1/tasks/task-1", () => HttpResponse.json(task)),
    http.get("/api/v1/tasks/task-1/runtime", () => HttpResponse.json(runtimePayload)),
  );

  renderApp("/tasks/task-1/trace");

  expect(await screen.findByText("执行步骤详情")).toBeVisible();
  expect(await screen.findByText("assert")).toBeVisible();
  const screenshotCard = (await screen.findByText("screenshot"))
    .closest(".trace-timeline-content");
  expect(screenshotCard).not.toBeNull();
  expect(within(screenshotCard as HTMLElement).getByText("失败")).toBeVisible();
  expect(within(screenshotCard as HTMLElement).queryByText("成功"))
    .not.toBeInTheDocument();
  expect(screen.queryByText("当前步骤")).not.toBeInTheDocument();
  expect(screen.queryByText("自动刷新中")).not.toBeInTheDocument();
});

it("links from task details to the trace page via tab", async () => {
  server.use(
    http.get("/api/v1/tasks/task-1", () => HttpResponse.json(task)),
    http.get("/api/v1/tasks/task-1/runtime", () => HttpResponse.json(runtimePayload)),
  );

  renderApp("/tasks/task-1");

  const traceLink = await screen.findByRole("link", { name: /执行轨迹/ });
  expect(traceLink).toHaveAttribute("href", "/biz/biz_default/tasks/task-1/trace");
});
