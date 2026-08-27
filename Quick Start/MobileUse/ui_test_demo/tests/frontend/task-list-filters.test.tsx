import { screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, delay, http } from "msw";
import { readFileSync } from "node:fs";
import { expect, it, vi } from "vitest";

import type { Task } from "../../web/api/types";
import { expectCsrf, renderApp, server, user } from "./setup";

function makeTask(overrides: Partial<Task>): Task {
  return {
    id: "task_1",
    case_id: "case_1",
    script_version_id: null,
    prompt_snapshot: null,
    result_summary: null,
    result_evidence: [],
    runner_type: "mobile_use",
    scenario: "场景",
    execution_status: "result_ready",
    verdict: "pass",
    review_result: null,
    reviewed_by: null,
    reviewed_at: null,
    review_note: null,
    failure_type: null,
    version: 1,
    created_at: "2026-07-28T03:00:00Z",
    started_at: "2026-07-28T03:00:01Z",
    finished_at: "2026-07-28T03:00:05Z",
    ...overrides,
    created_by: overrides.created_by ?? "admin",
  };
}

function cellFor(row: HTMLElement, headerName: string): HTMLElement {
  const headerIndex = screen
    .getAllByRole("columnheader")
    .findIndex((header) => header.textContent === headerName);
  expect(headerIndex).toBeGreaterThanOrEqual(0);
  return within(row).getAllByRole("cell")[headerIndex];
}

it("uses visibly distinct source badge backgrounds", () => {
  const css = readFileSync("web/styles.css", "utf8");

  expect(css).toContain(".source-badge-single {\n  background: var(--mua-neutral-100);");
  expect(css).toContain(".source-badge-multi {\n  background: var(--mua-primary-100);");
  expect(css).toContain("min-width: 64px;");
  expect(css).toContain("justify-content: center;");
  expect(css).toMatch(
    /\.source-badge\s*\{[^}]*border-radius:\s*9999px;/s,
  );
  expect(css).toMatch(
    /\.task-target-name-wrapper\s*\{[^}]*position:\s*relative/s,
  );
  expect(css).toMatch(
    /\.task-target-name-wrapper::after\s*\{[^}]*bottom:\s*calc\(100% \+ 8px\)/s,
  );
  expect(css).toMatch(
    /\.task-target-name-wrapper::after\s*\{[^}]*background:\s*var\(--mua-card\)/s,
  );
  expect(css).toMatch(
    /\.task-target-name-wrapper::after\s*\{[^}]*box-shadow:\s*0 14px 30px/s,
  );
  expect(css).toMatch(
    /\.task-target-name-wrapper::after\s*\{[^}]*content:\s*attr\(data-full-title\)/s,
  );
  expect(css).toContain("grid-template-columns: repeat(5, minmax(0, 1fr));");
  expect(css).toContain("min-height: 76px;");
  expect(css).toContain(".task-action-pill {\n  align-items: center;");
  expect(css).toMatch(
    /\.task-action-pill\s*\{[^}]*justify-content:\s*center;/s,
  );
  expect(css).toContain("width: 68px;");
  expect(css).toContain("padding: 3px 10px;");
  expect(css).toContain("border-radius: 9999px;");
  expect(css).toContain("font-size: 0.75rem;");
  expect(css).toContain("line-height: 1.5;");
  expect(css).toMatch(
    /\.task-action-pill-review\s*\{[^}]*background:\s*var\(--state-review-bg\);[^}]*border-color:\s*var\(--state-review-border\);[^}]*color:\s*var\(--state-review-fg\);/s,
  );
  expect(css).toMatch(
    /\.task-action-pill-review-edit\s*\{[^}]*background:\s*var\(--mua-primary-50\);[^}]*border-color:\s*var\(--mua-primary-200\);[^}]*color:\s*var\(--mua-primary-700\);/s,
  );
  expect(css).toContain(".modal-panel.task-review-dialog {\n  max-width: 520px;");
  expect(css).toContain(".task-review-select-field .single-select-trigger {\n  width: 100%;");
  expect(css).toContain(".task-review-select-field .single-select-option-list {\n  gap: 0.35rem;");
  expect(css).toContain(".task-review-dialog .modal-footer button {\n  height: 36px;");
  expect(css).toContain("width: 92px;");
});

it("renders four unified task metrics", async () => {
  server.use(
    http.get("/api/v1/tasks/stats", () =>
      HttpResponse.json({
        total: 42,
        running: 3,
        queued: 5,
        pass_rate: 91,
        manual_review_fail_count: 2,
        manual_review_total: 8,
        manual_review_fail_rate: 25,
      }),
    ),
  );

  renderApp("/tasks");

  expect(await screen.findByTestId("metric-total")).toHaveTextContent("42");
  expect(screen.getByTestId("metric-running")).toHaveTextContent("3");
  expect(screen.getByTestId("metric-queued")).toHaveTextContent("5");
  expect(screen.getByTestId("metric-pass-rate")).toHaveTextContent("91%");
  expect(screen.getByTestId("metric-manual-review-fail-rate")).toHaveTextContent("25%");
  expect(screen.getAllByTestId(/^metric-/)).toHaveLength(5);
});

it("does not render a top-right create task entry", async () => {
  renderApp("/tasks");

  expect(await screen.findByRole("heading", { name: "执行记录" }))
    .toBeVisible();
  expect(screen.queryByRole("link", { name: "新建任务" }))
    .not.toBeInTheDocument();
});

it("refreshes the task list and KPIs with visible pending feedback", async () => {
  let taskRequests = 0;
  let statsRequests = 0;
  server.use(
    http.get("/api/v1/tasks", async () => {
      taskRequests += 1;
      if (taskRequests > 1) await delay(80);
      return HttpResponse.json({
        items: [
          makeTask({
            id: taskRequests > 1 ? "task_after_refresh" : "task_before_refresh",
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      });
    }),
    http.get("/api/v1/tasks/stats", async () => {
      statsRequests += 1;
      if (statsRequests > 1) await delay(80);
      return HttpResponse.json({
        total: statsRequests > 1 ? 2 : 1,
        running: 0,
        queued: 0,
        pass_rate: 100,
      });
    }),
  );

  renderApp("/tasks");

  expect(await screen.findByText("task_before_refresh")).toBeVisible();
  expect(screen.getByTestId("metric-total")).toHaveTextContent("1");

  await user.click(screen.getByRole("button", { name: "刷新" }));

  const refreshButton = screen.getByRole("button", { name: "刷新中..." });
  expect(refreshButton).toBeDisabled();
  expect(await screen.findByText("task_after_refresh")).toBeVisible();
  expect(screen.getByTestId("metric-total")).toHaveTextContent("2");
  expect(screen.getByRole("button", { name: "刷新" })).toBeEnabled();
  expect(taskRequests).toBeGreaterThanOrEqual(2);
  expect(statsRequests).toBeGreaterThanOrEqual(2);
});

it("keeps global KPIs when task filters have no matches", async () => {
  server.use(
    http.get("/api/v1/tasks/stats", () =>
      HttpResponse.json({
        total: 12,
        running: 2,
        queued: 3,
        pass_rate: 88.5,
      })),
    http.get("/api/v1/tasks", ({ request }) => {
      const filtered = Boolean(
        new URL(request.url).searchParams.get("search"),
      );
      return HttpResponse.json({
        items: filtered ? [] : [makeTask({ id: "task_global" })],
        total: filtered ? 0 : 1,
        page: 1,
        page_size: 20,
      });
    }),
  );

  renderApp("/");
  expect(await screen.findByTestId("metric-total")).toHaveTextContent("12");
  await user.type(
    screen.getByRole("searchbox", { name: "搜索任务" }),
    "missing",
  );

  expect(await screen.findByText(
    "无匹配结果，请调整搜索条件或表头筛选",
  )).toBeVisible();
  expect(screen.getByTestId("metric-total")).toHaveTextContent("12");
  expect(screen.getByTestId("metric-running")).toHaveTextContent("2");
  expect(screen.queryByRole("link", { name: "创建第一个任务" }))
    .not.toBeInTheDocument();
});

it("filters by status and result from custom selects and copies task id", async () => {
  const seen: Array<{
    status: string | null;
    verdict: string | null;
    reviewResult: string | null;
    operator: string | null;
    createdAfter: string | null;
    page: string | null;
  }> = [];
  server.use(
    http.get("/api/v1/tasks/stats", () =>
      HttpResponse.json({ total: 3, running: 1, queued: 1, pass_rate: 50 }),
    ),
    http.get("/api/v1/tasks", ({ request }) => {
      const url = new URL(request.url);
      seen.push({
        status: url.searchParams.get("status"),
        verdict: url.searchParams.get("verdict"),
        reviewResult: url.searchParams.get("review_result"),
        operator: url.searchParams.get("operator"),
        createdAfter: url.searchParams.get("created_after"),
        page: url.searchParams.get("page"),
      });
      return HttpResponse.json({
        items: [makeTask({ id: "task_alpha" })],
        total: 1,
        page: 1,
        page_size: 20,
      });
    }),
    http.get("/api/v1/tasks/operators", () =>
      HttpResponse.json({ items: ["admin", "reviewer"] })),
  );

  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  renderApp("/tasks");

  const idCell = await screen.findByText("task_alpha");
  const row = idCell.closest("tr") as HTMLElement;
  await user.click(within(row).getByRole("button", { name: "复制任务ID" }));
  await waitFor(() => expect(writeText).toHaveBeenCalledWith("task_alpha"));

  expect(screen.getByRole("combobox", { name: "操作者筛选" })).toHaveTextContent("全部操作者");

  await user.click(screen.getByRole("combobox", { name: "状态筛选" }));
  await user.click(screen.getByRole("option", { name: "执行中" }));
  await user.click(screen.getByRole("combobox", { name: "执行结果筛选" }));
  await user.click(screen.getByRole("option", { name: "失败" }));
  await user.click(screen.getByRole("combobox", { name: "人工审核筛选" }));
  await user.click(screen.getByRole("option", { name: "复核失败" }));
  await user.click(screen.getByRole("combobox", { name: "时间筛选" }));
  await user.click(screen.getByRole("option", { name: "最近3天" }));
  await user.click(screen.getByRole("combobox", { name: "操作者筛选" }));
  await user.click(screen.getByRole("option", { name: "reviewer" }));

  await waitFor(() =>
    expect(seen.some((entry) => entry.status === "running")).toBe(true),
  );
  await waitFor(() =>
    expect(seen.some((entry) => entry.verdict === "fail")).toBe(true),
  );
  await waitFor(() =>
    expect(seen.some((entry) => entry.reviewResult === "fail")).toBe(true),
  );
  await waitFor(() =>
    expect(
      seen.some(
        (entry) => entry.status === "running"
          && entry.verdict === "fail"
          && entry.reviewResult === "fail"
          && entry.operator === "reviewer",
      ),
    ).toBe(true),
  );
  await waitFor(() =>
    expect(seen.some((entry) => entry.createdAfter !== null)).toBe(true),
  );
});

it("renders the phase-one task table structure with real single-case source", async () => {
  server.use(
    http.get("/api/v1/tasks", () =>
      HttpResponse.json({
        items: [makeTask({
          id: "task_structure",
          case_id: "case_structure",
          scenario: "登录链路验证",
        })],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    ),
  );

  renderApp("/tasks");
  await screen.findByText("task_structure");

  expect(screen.getByRole("heading", { name: "执行记录" }).closest(".tasks-page"))
    .toHaveClass("tasks-page");
  expect(screen.getByRole("table")).toHaveClass("task-table");
  expect(screen.getByRole("combobox", { name: "状态筛选" }))
    .toHaveClass("single-select-trigger");

  const headers = screen.getAllByRole("columnheader").map((header) => header.textContent);
  expect(headers).toEqual([
    "任务ID",
    "执行对象",
    "来源",
    "状态",
    "结果",
    "人工审核",
    "创建时间",
    "耗时",
    "操作者",
    "操作",
  ]);
  const row = screen.getByText("task_structure").closest("tr") as HTMLElement;
  const targetCell = cellFor(row, "执行对象");
  const sourceCell = cellFor(row, "来源");
  const targetLink = within(targetCell).getByText("登录链路验证");
  expect(targetLink).toHaveClass("task-target-link");
  expect(targetLink).not.toHaveAttribute("title");
  expect(targetLink.closest(".task-target-name-wrapper"))
    .toHaveAttribute("data-full-title", "登录链路验证");
  expect(within(targetCell).getByText("case_structure")).toHaveClass("task-target-case");
  expect(within(sourceCell).getByText("用例库")).toHaveClass("source-badge-single");
  expect(screen.queryByText("单用例")).not.toBeInTheDocument();
});

it("keeps a long execution object name truncated with the full name available on hover", async () => {
  const longScenario = "Mock验证-执行对象名称超长展示-登录注册支付退款会员权益优惠券库存同步订单详情售后入口全链路回归验证";
  server.use(
    http.get("/api/v1/tasks", () =>
      HttpResponse.json({
        items: [makeTask({
          id: "task_long_target",
          case_id: "case_long_target",
          scenario: longScenario,
        })],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    ),
  );

  renderApp("/tasks");

  const row = (await screen.findByText("task_long_target")).closest("tr") as HTMLElement;
  const targetCell = cellFor(row, "执行对象");
  const targetLink = within(targetCell).getByRole("link", { name: longScenario });
  const wrapper = targetLink.closest(".task-target-name-wrapper");
  const css = readFileSync("web/styles.css", "utf8");
  expect(targetLink).toHaveClass("task-target-link");
  expect(targetLink).not.toHaveAttribute("title");
  expect(wrapper).toHaveAttribute("data-full-title", longScenario);
  expect(within(targetCell).getByText("case_long_target")).toBeVisible();
  expect(css).toMatch(
    /\.task-target-link\s*\{[^}]*display:\s*block;[^}]*max-width:\s*280px;[^}]*overflow:\s*hidden;[^}]*text-overflow:\s*ellipsis;[^}]*white-space:\s*nowrap;/s,
  );
  expect(css).toMatch(
    /\.task-target-name-wrapper::after\s*\{[^}]*content:\s*attr\(data-full-title\)/s,
  );
});

it("renders shared batch id and child task id for multi-case rows", async () => {
  server.use(
    http.get("/api/v1/tasks", () =>
      HttpResponse.json({
        items: [
          makeTask({
            id: "task_child_1",
            batch_id: "batch_shared",
            batch_position: 0,
            display_task_id: "batch_shared",
            source_type: "multi_cases",
            queue_reason: "waiting_for_capacity",
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    ),
  );

  renderApp("/tasks");

  expect(await screen.findByText("batch_shared")).toBeVisible();
  expect(screen.getByText("task_child_1")).toBeVisible();
  expect(screen.queryByText("BatchID")).not.toBeInTheDocument();
  expect(screen.queryByText("TaskID")).not.toBeInTheDocument();

  const batchId = screen.getByText("batch_shared");
  const idStack = batchId.closest(".task-id-stack");
  expect(idStack).toBeInTheDocument();
  expect(idStack).toHaveClass("multi-case");
  expect(batchId).toHaveClass("batch-id");
  expect(batchId).toHaveClass("task-id-neutral");
  expect(screen.getByText("task_child_1")).toHaveClass("child-task-id");
  expect(screen.getByText("task_child_1")).toHaveClass("task-id-neutral");
  const row = screen.getByText("task_child_1").closest("tr") as HTMLElement;
  expect(within(cellFor(row, "来源")).getByText("测试计划")).toHaveClass("source-badge-multi");
  expect(screen.queryByText("多用例")).not.toBeInTheDocument();
  expect(idStack?.textContent).toBe("batch_sharedtask_child_1");
  expect(screen.getByRole("columnheader", { name: "操作" })).toHaveClass("col-actions-centered");
  expect(screen.getByRole("cell", { name: /查看/ })).toHaveClass("col-actions-centered");
});

it("shows zero elapsed time for queued tasks even when timestamps exist", async () => {
  server.use(
    http.get("/api/v1/tasks", () =>
      HttpResponse.json({
        items: [makeTask({
          id: "task_queued_duration",
          execution_status: "queued",
          verdict: null,
          started_at: "2026-07-28T03:00:01Z",
          finished_at: null,
        })],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    ),
  );

  renderApp("/tasks");

  const row = (await screen.findByText("task_queued_duration")).closest("tr") as HTMLElement;
  expect(cellFor(row, "耗时")).toHaveTextContent("0 秒");
});

it("paginates using backend total", async () => {
  server.use(
    http.get("/api/v1/tasks/stats", () =>
      HttpResponse.json({ total: 25, running: 0, queued: 2, pass_rate: 100 }),
    ),
    http.get("/api/v1/tasks", ({ request }) => {
      const url = new URL(request.url);
      const page = Number(url.searchParams.get("page") ?? "1");
      return HttpResponse.json({
        items: [makeTask({ id: `task_page_${page}` })],
        total: 25,
        page,
        page_size: 20,
      });
    }),
  );

  renderApp("/tasks");

  expect(await screen.findByText("task_page_1")).toBeVisible();
  expect(screen.getByText("第 1 / 2 页")).toBeVisible();
});

it("searches by case id while typing and removes all-value filters", async () => {
  const queries: Array<{
    search: string | null;
    status: string | null;
    verdict: string | null;
    reviewResult: string | null;
    createdAfter: string | null;
  }> = [];
  server.use(
    http.get("/api/v1/tasks", ({ request }) => {
      const url = new URL(request.url);
      queries.push({
        search: url.searchParams.get("search"),
        status: url.searchParams.get("status"),
        verdict: url.searchParams.get("verdict"),
        reviewResult: url.searchParams.get("review_result"),
        createdAfter: url.searchParams.get("created_after"),
      });
      return HttpResponse.json({
        items: [makeTask({ id: "task_case_search", case_id: "case_target" })],
        total: 1,
        page: 1,
        page_size: 20,
      });
    }),
  );

  renderApp("/tasks");

  await screen.findByText("task_case_search");
  await user.type(screen.getByLabelText("搜索任务"), "case_target");
  await waitFor(() =>
    expect(queries.some((query) => query.search === "case_target")).toBe(true),
  );

  await user.click(screen.getByRole("combobox", { name: "状态筛选" }));
  await user.click(screen.getByRole("option", { name: "排队中" }));
  await user.click(screen.getByRole("combobox", { name: "执行结果筛选" }));
  await user.click(screen.getByRole("option", { name: "成功" }));
  await user.click(screen.getByRole("combobox", { name: "人工审核筛选" }));
  await user.click(screen.getByRole("option", { name: "待审核" }));
  await user.click(screen.getByRole("combobox", { name: "时间筛选" }));
  await user.click(screen.getByRole("option", { name: "最近一天" }));
  await user.click(screen.getByRole("button", { name: "重置筛选" }));

  await waitFor(() =>
    expect(
      queries.some(
        (query) => query.search === null
          && query.status === null
          && query.verdict === null
          && query.reviewResult === null
          && query.createdAfter === null,
      ),
    ).toBe(true),
  );
});

it("offers cancellation only for active tasks and calls the local cancel endpoint", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  let cancelledTaskId = "";
  server.use(
    http.get("/api/v1/tasks/stats", () =>
      HttpResponse.json({ total: 2, running: 1, queued: 1, pass_rate: 0 }),
    ),
    http.get("/api/v1/tasks", () =>
      HttpResponse.json({
        items: [
          makeTask({ id: "task_running", execution_status: "running", verdict: null }),
          makeTask({ id: "task_done", execution_status: "result_ready", verdict: "pass" }),
        ],
        total: 2,
        page: 1,
        page_size: 20,
      }),
    ),
    http.post("/api/v1/tasks/task_running/cancel", ({ request }) => {
      expectCsrf(request);
      cancelledTaskId = "task_running";
      return HttpResponse.json(
        makeTask({ id: "task_running", execution_status: "running", verdict: null }),
      );
    }),
  );

  renderApp("/tasks");

  const runningRow = (await screen.findByText("task_running")).closest("tr") as HTMLElement;
  const completedRow = screen.getByText("task_done").closest("tr") as HTMLElement;
  expect(cellFor(runningRow, "结果")).toHaveTextContent("-");
  expect(within(runningRow).getByRole("button", { name: "取消" })).toBeEnabled();
  const viewLink = within(completedRow).getByRole("link", { name: "查看" });
  expect(viewLink).toHaveClass("task-action-pill");
  expect(viewLink.querySelector("svg")).not.toBeInTheDocument();
  expect(within(completedRow).getByRole("button", { name: "人工审核" })).toHaveClass("task-action-pill");
  expect(within(completedRow).queryByRole("button", { name: "取消" })).not.toBeInTheDocument();

  await user.click(within(runningRow).getByRole("button", { name: "取消" }));
  await waitFor(() => expect(cancelledTaskId).toBe("task_running"));
  expect(confirm).toHaveBeenCalledOnce();
  confirm.mockRestore();
});

it("reviews completed tasks and refreshes task data", async () => {
  let reviewPayload: unknown;
  server.use(
    http.get("/api/v1/tasks", () =>
      HttpResponse.json({
        items: [
          makeTask({ id: "task_review_ready", review_result: null }),
          makeTask({ id: "task_reviewed", review_result: "pass", reviewed_by: "admin", reviewed_at: "2026-07-28T04:00:00Z" }),
          makeTask({ id: "task_not_ready", execution_status: "running", verdict: null }),
        ],
        total: 3,
        page: 1,
        page_size: 20,
      }),
    ),
    http.put("/api/v1/tasks/task_review_ready/review", async ({ request }) => {
      expectCsrf(request);
      reviewPayload = await request.json();
      return HttpResponse.json(
        makeTask({
          id: "task_review_ready",
          review_result: "fail",
          reviewed_by: "admin",
          reviewed_at: "2026-07-28T04:30:00Z",
          review_note: "实际流程失败",
        }),
      );
    }),
  );

  renderApp("/tasks");

  const readyRow = (await screen.findByText("task_review_ready")).closest("tr") as HTMLElement;
  const reviewedRow = screen.getByText("task_reviewed").closest("tr") as HTMLElement;
  const runningRow = screen.getByText("task_not_ready").closest("tr") as HTMLElement;

  expect(cellFor(readyRow, "人工审核")).toHaveTextContent("待审核");
  expect(cellFor(reviewedRow, "人工审核")).toHaveTextContent("复核通过");
  expect(within(runningRow).queryByRole("button", { name: "人工审核" })).not.toBeInTheDocument();
  expect(within(readyRow).getByRole("button", { name: "人工审核" }))
    .toHaveClass("task-action-pill-review");
  expect(within(reviewedRow).getByRole("button", { name: "修改审核" }))
    .toHaveClass("task-action-pill-review-edit");

  await user.click(within(readyRow).getByRole("button", { name: "人工审核" }));
  const dialog = await screen.findByRole("dialog", { name: "人工审核" });
  expect(dialog).toBeVisible();
  expect(within(dialog).queryByText("Manual Review")).not.toBeInTheDocument();
  expect(within(dialog).getByText("人工结论不会覆盖系统执行结果，只用于复核统计。"))
    .toHaveClass("confirm-dialog-description", "task-review-description");
  expect(dialog.querySelector(".modal-body")).toHaveClass("task-review-body");
  expect(within(dialog).getByRole("button", { name: "关闭" })).toHaveClass("modal-close");
  expect(screen.getByRole("combobox", { name: "审核结论" }).closest(".task-review-select-field"))
    .toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "取消" })).toHaveClass("task-review-footer-button");
  expect(within(dialog).getByRole("button", { name: "保存审核" })).toHaveClass("task-review-footer-button");
  await user.click(screen.getByRole("combobox", { name: "审核结论" }));
  await user.click(screen.getByRole("option", { name: "复核失败" }));
  await user.type(screen.getByLabelText("审核备注"), "实际流程失败");
  await user.click(screen.getByRole("button", { name: "保存审核" }));

  await waitFor(() =>
    expect(reviewPayload).toEqual({
      review_result: "fail",
      review_note: "实际流程失败",
    }),
  );
});
