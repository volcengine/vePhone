import { screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, it } from "vitest";

import { expectCsrf, renderApp, server, user } from "./setup";

const failedTask = {
  id: "task_review",
  case_id: "case_680a16d47526471eb8f91915be7b13f0",
  script_version_id: null,
  prompt_snapshot: "## 执行任务\n打开抖音APP查看3个视频",
  result_summary: "执行失败：页面卡住",
  result_evidence: ["GetAgentResult Content: 执行失败：页面卡住"],
  runner_type: "mobile_use",
  scenario: "打开抖音APP查看3个视频",
  execution_status: "result_ready",
  verdict: "fail",
  failure_type: "runner_interrupted",
  version: 3,
  created_at: "2026-07-28T03:35:31.564869Z",
  started_at: "2026-07-28T03:35:31.575333Z",
  finished_at: "2026-07-28T03:35:32.263965Z",
  remote_thread_id: "thread-review",
  remote_status_code: 6,
  remote_step_id: "finished",
  recording_url: null,
  result_assets: { usage: { in_tokens: 0, out_tokens: 0 }, screenshots: {}, files: [] },
  created_by: "admin",
};

const failedRuntime = {
  task: failedTask,
  current_step: null,
  thread_groups: [],
  thread_steps: [],
  result: {
    summary: "执行失败：页面卡住",
    evidence: ["GetAgentResult Content: 执行失败：页面卡住"],
    recording_url: null,
    assets: { usage: { in_tokens: 0, out_tokens: 0 }, screenshots: {}, files: [] },
  },
  errors: {},
};

const caseResponse = {
  id: failedTask.case_id,
  title: "打开抖音APP查看3个视频",
  module: "稳定性",
  content_markdown: "## 执行任务\n打开抖音APP查看3个视频",
  tags: [],
  automation_level: "auto",
  default_agent_options: null,
  execution_count: 1,
  pass_count: 0,
  fail_count: 1,
  last_executed_at: null,
  created_by: "admin",
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-20T00:00:00Z",
};

it("shows failed task details when task is interrupted", async () => {
  server.use(
    http.get("/api/v1/tasks/task_review", () => HttpResponse.json(failedTask)),
    http.get("/api/v1/tasks/task_review/runtime", () => HttpResponse.json(failedRuntime)),
    http.get(`/api/v1/cases/${failedTask.case_id}`, () => HttpResponse.json(caseResponse)),
  );

  renderApp("/tasks/task_review");

  expect(await screen.findByText(/任务 ID/)).toHaveTextContent("task_review");
  expect(screen.queryByText("任务详情加载失败")).not.toBeInTheDocument();
  expect(screen.getByText("已完成")).toBeVisible();
  expect(screen.getAllByText("失败").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("执行失败：页面卡住")).toBeVisible();
  expect(screen.getByText("GetAgentResult Content: 执行失败：页面卡住")).toBeVisible();
});

it("reviews result-ready tasks from the detail page without moving automatically", async () => {
  let reviewPayload: unknown;
  server.use(
    http.get("/api/v1/tasks/task_review", () => HttpResponse.json(failedTask)),
    http.get("/api/v1/tasks/task_review/runtime", () => HttpResponse.json(failedRuntime)),
    http.get(`/api/v1/cases/${failedTask.case_id}`, () => HttpResponse.json(caseResponse)),
    http.get("/api/v1/tasks", () =>
      HttpResponse.json({
        items: [
          failedTask,
          { ...failedTask, id: "task_next", scenario: "下一个待审核任务" },
        ],
        total: 2,
        page: 1,
        page_size: 100,
      })),
    http.put("/api/v1/tasks/task_review/review", async ({ request }) => {
      expectCsrf(request);
      reviewPayload = await request.json();
      return HttpResponse.json({
        ...failedTask,
        review_result: "pass",
        reviewed_by: "admin",
        reviewed_at: "2026-07-28T04:30:00Z",
        review_note: "人工确认通过",
      });
    }),
  );

  renderApp("/tasks/task_review?review=1&status=result_ready&review_result=unreviewed", {
    browser: true,
  });

  const panel = await screen.findByRole("region", { name: "人工审核" });
  expect(within(panel).getByRole("button", { name: "上一条" })).toBeDisabled();
  expect(await within(panel).findByRole("link", { name: "下一条" }))
    .toHaveAttribute(
      "href",
      "/biz/biz_default/tasks/task_next?review=1&status=result_ready&review_result=unreviewed",
    );
  await user.click(within(panel).getByRole("combobox", { name: "审核结论" }));
  await user.click(screen.getByRole("option", { name: "复核通过" }));
  await user.clear(within(panel).getByLabelText("审核备注"));
  await user.type(within(panel).getByLabelText("审核备注"), "人工确认通过");
  await user.click(within(panel).getByRole("button", { name: "保存审核" }));

  await waitFor(() =>
    expect(reviewPayload).toEqual({
      review_result: "pass",
      review_note: "人工确认通过",
    }),
  );
  expect(window.location.pathname).toBe("/biz/biz_default/tasks/task_review");
  expect(window.location.search).toBe("?review=1&status=result_ready&review_result=unreviewed");
});

it("does not offer manual review for running tasks", async () => {
  const runningTask = {
    ...failedTask,
    execution_status: "running",
    verdict: null,
    finished_at: null,
  };
  server.use(
    http.get("/api/v1/tasks/task_review", () => HttpResponse.json(runningTask)),
    http.get(`/api/v1/cases/${failedTask.case_id}`, () => HttpResponse.json(caseResponse)),
    http.get("/api/v1/tasks/task_review/runtime", () =>
      HttpResponse.json({ ...failedRuntime, task: runningTask })),
  );

  renderApp("/tasks/task_review?review=1");

  expect(await screen.findByText(/任务 ID/)).toHaveTextContent("task_review");
  expect(screen.queryByRole("region", { name: "人工审核" })).not.toBeInTheDocument();
});
