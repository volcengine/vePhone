import { HttpResponse, http } from "msw";
import { screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import type { PlanReportDetailResponse } from "../../web/api/types";
import { renderApp, server, user } from "./setup";

function detail(
  status: PlanReportDetailResponse["report_status"] = "success",
): PlanReportDetailResponse {
  return {
    execution_id: "execution_1",
    task_batch_id: "batch_1",
    test_plan_id: "plan_1",
    plan_name_snapshot: "核心回归",
    report_status: status,
    pass_rate: 94.44,
    created_at: "2026-07-29T12:03:00Z",
    started_at: "2026-07-29T12:03:05Z",
    finished_at: status === "running" ? null : "2026-07-29T12:04:10Z",
    duration_seconds: status === "running" ? 120 : 65,
    plan_tags_snapshot: ["核心"],
    case_ids_snapshot: ["case_1", "case_2"],
    device_strategy_snapshot: "specified",
    pod_ids_snapshot: ["pod_1"],
    concurrency_snapshot: 1,
    runner_type_snapshot: "mobile_use",
    config_snapshot: {
      source: "custom",
      product_id: "product_1",
      pod_id: null,
      tos_bucket: null,
      tos_endpoint: null,
      tos_region: null,
      timeout_seconds: 600,
      device_wait_timeout_seconds: 75,
      use_base64_screenshot: false,
      max_step: 100,
      callback_info: {
        url: "https://callback.example.com",
        authorization: "***",
      },
      output_schema: null,
      retry_limit: 3,
      system_prompt: null,
      screen_record: false,
      mcp_json: '{"headers":{"Authorization":"***"}}',
      max_output_tokens: null,
      gps_info: null,
      request_headers: { configured: true, names: ["X-Env"] },
    },
    pass_count: 1,
    fail_count: 0,
    exception_count: 1,
    cancelled_count: 0,
    queued_count: 0,
    running_count: status === "running" ? 1 : 0,
    tasks: [
      {
        task_id: "task_1",
        remote_run_id: "run_1",
        case_id: "case_1",
        case_title: "登录",
        case_deleted: false,
        execution_status: "result_ready",
        verdict: "pass",
        failure_type: null,
        created_at: "2026-07-29T12:03:00Z",
        started_at: "2026-07-29T12:03:05Z",
        finished_at: "2026-07-29T12:04:10Z",
        duration_seconds: 65,
        input_tokens: 1234,
        output_tokens: 56,
        total_steps: 7,
      },
      {
        task_id: "task_unknown",
        remote_run_id: null,
        case_id: "case_2",
        case_title: "异常数据",
        case_deleted: true,
        execution_status: "unknown",
        verdict: "unknown",
        failure_type: "runner_interrupted",
        created_at: "2026-07-29T12:03:00Z",
        started_at: null,
        finished_at: null,
        duration_seconds: null,
        input_tokens: null,
        output_tokens: null,
        total_steps: null,
      },
    ],
    tasks_total: 12,
    page: 1,
    page_size: 10,
  };
}

it("shows plain metrics, safe snapshots, unknown enums and task drill-down", async () => {
  let lastUrl: URL | undefined;
  server.use(
    http.get("/api/v1/task-reports/execution_1", ({ request }) => {
      lastUrl = new URL(request.url);
      return HttpResponse.json(detail());
    }),
  );

  renderApp("/task-reports/execution_1");
  expect(await screen.findByRole("heading", { name: "核心回归" })).toBeVisible();
  expect(screen.getByTestId("plan-report-rate")).toHaveTextContent("94%");
  expect(screen.queryByText("94.44%")).not.toBeInTheDocument();
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.getAllByText("2026-07-29 20:03:00").length).toBeGreaterThan(0);
  expect(screen.getAllByText("1 分 5 秒").length).toBeGreaterThan(0);
  expect(screen.getByRole("columnheader", { name: "Run ID" })).toBeVisible();
  expect(screen.getByRole("columnheader", { name: "输入 Token" })).toBeVisible();
  expect(screen.getByRole("columnheader", { name: "输出 Token" })).toBeVisible();
  expect(screen.getByRole("columnheader", { name: "执行步数" })).toBeVisible();
  expect(screen.getByText("run_1")).toBeVisible();
  expect(screen.getByText("1,234")).toBeVisible();
  expect(screen.getByText("56")).toBeVisible();
  expect(screen.getByText("7")).toBeVisible();
  expect(screen.getByText("case_1").closest("td")).toHaveClass(
    "plan-report-case-cell",
  );
  expect(screen.getByRole("link", { name: "task_1" })).toHaveAttribute(
    "href",
    "/biz/biz_default/tasks/task_1",
  );
  expect(screen.getByRole("link", { name: "查看用例 登录" }))
    .toHaveAttribute("href", "/biz/biz_default/cases/case_1/edit");
  expect(screen.queryByRole("link", { name: "查看用例 异常数据" }))
    .not.toBeInTheDocument();
  expect(screen.getByText("未知状态")).toBeVisible();
  expect(screen.getByText("未知结果")).toBeVisible();
  expect(screen.getByText("runner_interrupted")).toBeVisible();
  expect(screen.getByText("已脱敏")).toBeVisible();
  expect(document.body.textContent).not.toContain("callback-secret");
  expect(document.body.textContent).not.toContain("mcp-secret");

  await user.click(screen.getByRole("button", { name: "下一页" }));
  await waitFor(() => expect(lastUrl?.searchParams.get("page")).toBe("2"));
});

it("restores task pagination from the URL and browser history", async () => {
  const requests: URL[] = [];
  server.use(
    http.get("/api/v1/task-reports/execution_1", ({ request }) => {
      const url = new URL(request.url);
      requests.push(url);
      return HttpResponse.json({
        ...detail(),
        tasks_total: 61,
        page: Number(url.searchParams.get("page") ?? 1),
        page_size: Number(url.searchParams.get("page_size") ?? 10),
      });
    }),
  );

  renderApp("/task-reports/execution_1?page=2&page_size=20", {
    browser: true,
  });

  expect(await screen.findByRole("combobox", { name: "每页条数" }))
    .toHaveTextContent("20 条 / 页");
  await waitFor(() => {
    expect(requests.at(-1)?.searchParams.get("page")).toBe("2");
    expect(requests.at(-1)?.searchParams.get("page_size")).toBe("20");
  });

  await user.click(screen.getByRole("button", { name: "下一页" }));
  await waitFor(() => expect(window.location.search).toContain("page=3"));

  window.history.back();
  await waitFor(() => expect(window.location.search).toContain("page=2"));
  expect(screen.getByRole("combobox", { name: "每页条数" }))
    .toHaveTextContent("20 条 / 页");

  window.history.forward();
  await waitFor(() => expect(window.location.search).toContain("page=3"));
});

it("polls running reports and stops after reaching a terminal status", async () => {
  vi.useFakeTimers();
  try {
    let requests = 0;
    server.use(
      http.get("/api/v1/task-reports/execution_1", () => {
        requests += 1;
        return HttpResponse.json(requests === 1 ? detail("running") : detail());
      }),
    );

    renderApp("/task-reports/execution_1");
    await vi.waitFor(() =>
      expect(screen.getAllByText("执行中").length).toBeGreaterThan(0)
    );
    expect(requests).toBe(1);

    await vi.advanceTimersByTimeAsync(3000);
    await vi.waitFor(() => expect(requests).toBe(2));
    expect(screen.getAllByText("成功").length).toBeGreaterThan(0);

    await vi.advanceTimersByTimeAsync(6000);
    expect(requests).toBe(2);
  } finally {
    vi.useRealTimers();
  }
});

it("renders stable not-found and permission errors", async () => {
  server.use(
    http.get("/api/v1/task-reports/execution_1", () =>
      HttpResponse.json(
        { error: { code: "task_report_not_found", message: "not found" } },
        { status: 404 },
      )),
  );
  renderApp("/task-reports/execution_1");
  expect(await screen.findByText("测试报告不存在")).toBeVisible();
});

it("renders a permission-specific state without retry actions", async () => {
  server.use(
    http.get("/api/v1/task-reports/execution_1", () =>
      HttpResponse.json(
        { error: { code: "forbidden", message: "forbidden" } },
        { status: 403 },
      )),
  );
  renderApp("/task-reports/execution_1");

  expect(await screen.findByText("无权查看测试报告")).toBeVisible();
  expect(screen.queryByRole("button", { name: "重新加载" }))
    .not.toBeInTheDocument();
});
