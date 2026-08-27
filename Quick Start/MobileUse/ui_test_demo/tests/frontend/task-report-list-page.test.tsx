import { HttpResponse, delay, http } from "msw";
import { screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { expect, it, vi } from "vitest";

import type {
  PlanReportListResponse,
  PlanReportStatsResponse,
  TestPlan,
} from "../../web/api/types";
import pageSource from "../../web/pages/task-report-list-page.tsx?raw";
import { renderApp, server, user } from "./setup";

const STYLES = readFileSync("web/styles.css", "utf8");

const KPI_ICON_PATHS = [
  "M6 3h8l4 4v14H6zM14 3v5h5M9 13h6M9 17h4",
  "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-4-9 3 3 5-6",
  "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-3-6 6-6M9 9l6 6",
  "M4 18 10 12l4 4 6-10M7 7h.01M17 17h.01M7 17 17 7",
];

const report: PlanReportListResponse["items"][number] = {
  execution_id: "execution_1",
  task_batch_id: "batch_ade72413d6004c508efd9f99d1a44bff",
  test_plan_id: "plan_1",
  plan_name_snapshot: "核心回归计划名称非常长用于验证列表展示截断",
  report_status: "success",
  pass_rate: 94.44,
  created_at: "2026-07-29T12:03:00Z",
  started_at: "2026-07-29T12:03:05Z",
  finished_at: "2026-07-29T12:04:10Z",
  duration_seconds: 65,
};

function plan(index: number): TestPlan {
  return {
    id: `plan_${index}`,
    name: index === 1 ? "核心回归" : `计划 ${index}`,
    description: null,
    test_type: "regression",
    tags: [],
    case_ids: ["case_1"],
    case_count: 1,
    execution_count: 1,
    latest_execution: null,
    created_by: "admin",
    created_at: "2026-07-29T00:00:00Z",
    updated_at: "2026-07-29T00:00:00Z",
  };
}

it("uses the refreshed task report KPI icons", () => {
  for (const path of KPI_ICON_PATHS) {
    expect(pageSource).toContain(`path="${path}"`);
  }
  expect(STYLES).toMatch(
    /(?:^|\n)\.metric-card-icon svg\s*\{[^}]*fill:\s*none;[^}]*stroke:\s*currentColor;[^}]*stroke-linecap:\s*round;[^}]*stroke-linejoin:\s*round;/s,
  );
});

it("loads at most fifty plans and searches plans on the backend", async () => {
  const planUrls: URL[] = [];
  server.use(
    http.get("/api/v1/test-plans", ({ request }) => {
      const url = new URL(request.url);
      planUrls.push(url);
      return HttpResponse.json({
        items: url.searchParams.get("search") === "核心" ? [plan(1)] : [],
        total: 1,
        page: 1,
        page_size: 50,
      });
    }),
    http.get("/api/v1/task-reports", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 10 })),
    http.get("/api/v1/task-reports/stats", () =>
      HttpResponse.json({
        report_count: 0,
        success_count: 0,
        failure_count: 0,
        average_pass_rate: 0,
      })),
  );

  renderApp("/task-reports");
  await user.click(await screen.findByRole("combobox", {
    name: "测试计划筛选",
  }));
  await user.type(
    screen.getByRole("searchbox", { name: "搜索测试计划" }),
    "核心",
  );

  await waitFor(() =>
    expect(planUrls.at(-1)?.searchParams.get("search")).toBe("核心")
  );
  expect(planUrls.every((url) =>
    url.searchParams.get("page") === "1"
    && url.searchParams.get("page_size") === "50"
  )).toBe(true);
});

it("syncs list filters with the URL while keeping report stats global", async () => {
  const listUrls: URL[] = [];
  const statsUrls: URL[] = [];
  const plans = Array.from({ length: 101 }, (_, index) => plan(index + 1));
  server.use(
    http.get("/api/v1/test-plans", ({ request }) => {
      const url = new URL(request.url);
      const page = Number(url.searchParams.get("page") ?? 1);
      const pageSize = Number(url.searchParams.get("page_size") ?? 100);
      const start = (page - 1) * pageSize;
      return HttpResponse.json({
        items: plans.slice(start, start + pageSize),
        total: plans.length,
        page,
        page_size: pageSize,
      });
    }),
    http.get("/api/v1/task-reports", ({ request }) => {
      listUrls.push(new URL(request.url));
      return HttpResponse.json({
        items: [report],
        total: 1,
        page: 1,
        page_size: 10,
      } satisfies PlanReportListResponse);
    }),
    http.get("/api/v1/task-reports/stats", ({ request }) => {
      statsUrls.push(new URL(request.url));
      return HttpResponse.json({
        report_count: 9,
        success_count: 7,
        failure_count: 2,
        average_pass_rate: 88.88,
      } satisfies PlanReportStatsResponse);
    }),
  );

  renderApp("/task-reports", { browser: true });
  expect(await screen.findByRole("heading", { name: "测试报告" })).toBeVisible();
  const filterBar = document.querySelector(".task-report-filter-bar") as HTMLElement;
  expect(within(filterBar).queryByText("测试计划")).not.toBeInTheDocument();
  expect(within(filterBar).queryByText("执行结果")).not.toBeInTheDocument();
  expect(within(filterBar).queryByText("创建时间")).not.toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "测试计划筛选" }))
    .toHaveTextContent("全部任务");
  expect(screen.getByRole("combobox", { name: "报告状态筛选" }))
    .toHaveTextContent("全部结果");
  expect(screen.getByRole("combobox", { name: "时间筛选" }))
    .toHaveTextContent("全部时间");
  expect(STYLES).toMatch(
    /\.task-report-filter-field\.plan-filter[\s\S]*?\.single-select-trigger\s*\{[^}]*width:\s*180px/s,
  );
  expect(STYLES).toMatch(
    /\.task-report-filter-field\.status-filter[\s\S]*?\.single-select-trigger\s*\{[^}]*width:\s*132px/s,
  );
  expect(STYLES).toMatch(
    /\.task-report-filter-field\.time-filter[\s\S]*?\.single-select-trigger\s*\{[^}]*width:\s*154px/s,
  );
  expect(STYLES).toMatch(
    /\.task-report-filter-bar\s*\{[^}]*overflow:\s*visible/s,
  );
  expect(STYLES).toMatch(
    /\.task-report-table\s*\{[^}]*min-width:\s*1260px/s,
  );
  expect(STYLES).toMatch(
    /\.task-report-table th:first-child,\s*\.task-report-table td:first-child\s*\{[^}]*width:\s*360px/s,
  );
  expect(STYLES).toMatch(
    /\.task-report-plan-name\s*\{[^}]*max-width:\s*220px;[^}]*overflow:\s*hidden;[^}]*text-overflow:\s*ellipsis/s,
  );
  expect(STYLES).toMatch(
    /\.task-report-table th,[\s\S]*?\.task-report-table td,[\s\S]*?\{[^}]*text-align:\s*left/s,
  );
  await user.click(screen.getByRole("combobox", { name: "测试计划筛选" }));
  expect(screen.queryByRole("option", { name: "计划 101" }))
    .not.toBeInTheDocument();

  await user.click(screen.getByRole("option", { name: "核心回归" }));
  await user.click(screen.getByRole("combobox", { name: "报告状态筛选" }));
  await user.click(screen.getByRole("option", { name: "成功" }));
  await user.click(screen.getByRole("combobox", { name: "时间筛选" }));
  await user.click(screen.getByRole("option", { name: "最近一周" }));

  await waitFor(() => {
    const list = listUrls.at(-1);
    const stats = statsUrls.at(-1);
    expect(list?.searchParams.get("test_plan_id")).toBe("plan_1");
    expect(list?.searchParams.get("status")).toBe("success");
    expect(list?.searchParams.get("created_after")).toBeTruthy();
    expect(stats?.search).toBe("");
    expect(list?.searchParams.has("time_range")).toBe(false);
    expect(stats?.searchParams.has("time_range")).toBe(false);
    expect(window.location.search).toContain("test_plan_id=plan_1");
    expect(window.location.search).toContain("status=success");
    expect(new URLSearchParams(window.location.search).get("time_range"))
      .toBe("7d");
  });
  expect(screen.getByRole("combobox", { name: "时间筛选" }))
    .toHaveTextContent("最近一周");

  expect(screen.getByTestId("report-count")).toHaveTextContent("9");
  expect(screen.getByTestId("report-average")).toHaveTextContent("89%");
  expect(screen.getByRole("link", { name: report.task_batch_id })).toHaveClass("task-report-id-link");
  expect(screen.getByText(report.plan_name_snapshot)).toHaveClass("task-report-plan-name");
  expect(screen.getByText("94%")).toBeVisible();
  expect(screen.queryByText("94.44%")).not.toBeInTheDocument();
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.getByText("2026-07-29 20:03:00")).toBeVisible();
  expect(screen.getByText("1 分 5 秒")).toBeVisible();

  await user.click(screen.getByRole("button", { name: "重置筛选" }));
  await waitFor(() => {
    const params = new URLSearchParams(window.location.search);
    expect(params.has("time_range")).toBe(false);
    expect(params.has("created_after")).toBe(false);
  });
});

it("copies the full report task id from the list", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50 })),
    http.get("/api/v1/task-reports", () =>
      HttpResponse.json({
        items: [report],
        total: 1,
        page: 1,
        page_size: 10,
      })),
    http.get("/api/v1/task-reports/stats", () =>
      HttpResponse.json({
        report_count: 1,
        success_count: 1,
        failure_count: 0,
        average_pass_rate: 100,
      })),
  );

  renderApp("/task-reports");

  await screen.findByRole("link", { name: report.task_batch_id });
  await user.click(screen.getByRole("button", { name: "复制任务ID" }));

  await waitFor(() => expect(writeText).toHaveBeenCalledWith(report.task_batch_id));
});


it("downloads terminal reports from the list with selectable formats", async () => {
  const requests: URL[] = [];
  const createObjectURL = vi.fn(() => "blob:report-download");
  const revokeObjectURL = vi.fn();
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => undefined);
  Object.defineProperty(URL, "createObjectURL", {
    value: createObjectURL,
    configurable: true,
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    value: revokeObjectURL,
    configurable: true,
  });
  const reports: PlanReportListResponse["items"] = [
    report,
    {
      ...report,
      execution_id: "execution_failure",
      task_batch_id: "batch_failure",
      report_status: "failure",
      pass_rate: 75,
    },
    {
      ...report,
      execution_id: "execution_exception",
      task_batch_id: "batch_exception",
      report_status: "exception",
      pass_rate: 60,
    },
    {
      ...report,
      execution_id: "execution_running",
      task_batch_id: "batch_running",
      report_status: "running",
      pass_rate: 40,
    },
    {
      ...report,
      execution_id: "execution_cancelled",
      task_batch_id: "batch_cancelled",
      report_status: "cancelled",
      pass_rate: 0,
    },
  ];
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50 })),
    http.get("/api/v1/task-reports", () =>
      HttpResponse.json({
        items: reports,
        total: reports.length,
        page: 1,
        page_size: 10,
      } satisfies PlanReportListResponse)),
    http.get("/api/v1/task-reports/stats", () =>
      HttpResponse.json({
        report_count: reports.length,
        success_count: 1,
        failure_count: 1,
        average_pass_rate: 54,
      } satisfies PlanReportStatsResponse)),
    http.get("/api/v1/task-reports/:executionId/download", async ({ request }) => {
      requests.push(new URL(request.url));
      await delay(80);
      return HttpResponse.text("报告ID,任务批次ID\nexecution_1,batch_1\n", {
        headers: {
          "Content-Disposition": 'attachment; filename="mua-test-report-batch_1.csv"',
          "Content-Type": "text/csv; charset=utf-8",
        },
      });
    }),
  );

  renderApp("/task-reports");

  const downloadButton = await screen.findByRole("button", {
    name: `下载报告 ${report.task_batch_id}`,
  });
  expect(screen.getByRole("button", { name: "下载报告 batch_failure" }))
    .toBeVisible();
  expect(screen.getByRole("button", { name: "下载报告 batch_exception" }))
    .toBeVisible();
  expect(screen.queryByRole("button", { name: "下载报告 batch_running" }))
    .not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "下载报告 batch_cancelled" }))
    .not.toBeInTheDocument();
  expect(screen.getByText("完成后可下载")).toBeVisible();
  expect(screen.getByText("不支持下载")).toBeVisible();

  await user.click(downloadButton);

  expect(downloadButton.closest(".task-report-download-action"))
    .toHaveClass("open");
  expect(downloadButton.closest("td"))
    .toHaveClass("task-report-download-cell", "open");
  expect(downloadButton.closest("tr"))
    .toHaveClass("download-menu-open");
  expect(STYLES).toMatch(
    /\.task-report-table tr\.download-menu-open\s*\{[^}]*position:\s*relative;[^}]*z-index:\s*40/s,
  );
  expect(STYLES).toMatch(
    /\.task-report-download-cell\.open\s*\{[^}]*position:\s*relative;[^}]*z-index:\s*50/s,
  );
  expect(STYLES).toMatch(
    /\.task-report-download-action\.open\s*\{[^}]*z-index:\s*30/s,
  );
  expect(STYLES).toMatch(
    /\.task-report-download-menu\s*\{[^}]*background:\s*var\(--mua-card\)/s,
  );
  expect(screen.getByRole("menuitem", { name: /Markdown 报告/ })).toBeVisible();
  await user.click(screen.getByRole("heading", { name: "测试报告" }));
  expect(screen.queryByRole("menuitem", { name: /Markdown 报告/ }))
    .not.toBeInTheDocument();
  expect(downloadButton).toHaveAttribute("aria-expanded", "false");

  await user.click(downloadButton);
  expect(screen.getByRole("menuitem", { name: /Markdown 报告/ })).toBeVisible();
  await user.click(screen.getByRole("menuitem", { name: /CSV 明细表/ }));

  expect(await screen.findByRole("button", { name: "生成中..." }))
    .toBeDisabled();
  await waitFor(() => expect(requests).toHaveLength(1));
  expect(requests[0].pathname).toBe("/api/v1/task-reports/execution_1/download");
  expect(requests[0].searchParams.get("format")).toBe("csv");
  await waitFor(() => expect(createObjectURL).toHaveBeenCalled());
  expect(click).toHaveBeenCalled();
  expect(revokeObjectURL).toHaveBeenCalledWith("blob:report-download");
  expect(screen.queryByText("测试报告已开始下载")).not.toBeInTheDocument();
  click.mockRestore();
});

it("keeps global report KPIs when report filters have no matches", async () => {
  const listUrls: URL[] = [];
  const statsUrls: URL[] = [];
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({
        items: [plan(1)],
        total: 1,
        page: 1,
        page_size: 50,
      })),
    http.get("/api/v1/task-reports", ({ request }) => {
      listUrls.push(new URL(request.url));
      return HttpResponse.json({
        items: [],
        total: 0,
        page: 1,
        page_size: 10,
      });
    }),
    http.get("/api/v1/task-reports/stats", ({ request }) => {
      statsUrls.push(new URL(request.url));
      return HttpResponse.json({
        report_count: 9,
        success_count: 7,
        failure_count: 2,
        average_pass_rate: 88.88,
      });
    }),
  );

  renderApp("/task-reports");
  await user.click(await screen.findByRole("combobox", {
    name: "测试计划筛选",
  }));
  await user.click(screen.getByRole("option", { name: "核心回归" }));
  await user.click(screen.getByRole("combobox", { name: "报告状态筛选" }));
  await user.click(screen.getByRole("option", { name: "成功" }));

  const message = await screen.findByText(
    "无匹配结果，请调整搜索条件或表头筛选",
  );
  expect(message).toBeVisible();
  expect(listUrls.at(-1)?.searchParams.get("test_plan_id")).toBe("plan_1");
  expect(listUrls.at(-1)?.searchParams.get("status")).toBe("success");
  expect(statsUrls.at(-1)?.search).toBe("");
  expect(screen.getByTestId("report-count")).toHaveTextContent("9");
  expect(screen.getByTestId("report-average")).toHaveTextContent("89%");
  expect(within(message.closest(".empty-state") as HTMLElement)
    .queryByRole("link", { name: "返回测试计划" }))
    .not.toBeInTheDocument();
});

it("searches reports by task id while keeping report stats global", async () => {
  const listUrls: URL[] = [];
  const statsUrls: URL[] = [];
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50 })),
    http.get("/api/v1/task-reports", ({ request }) => {
      listUrls.push(new URL(request.url));
      return HttpResponse.json({
        items: [report],
        total: 1,
        page: 1,
        page_size: 10,
      });
    }),
    http.get("/api/v1/task-reports/stats", ({ request }) => {
      statsUrls.push(new URL(request.url));
      return HttpResponse.json({
        report_count: 9,
        success_count: 7,
        failure_count: 2,
        average_pass_rate: 88.88,
      });
    }),
  );

  renderApp("/task-reports", { browser: true });
  const search = await screen.findByRole("searchbox", { name: "搜索任务ID" });
  await user.type(search, "batch_1");

  await waitFor(() => {
    expect(listUrls.at(-1)?.searchParams.get("search")).toBe("batch_1");
    expect(window.location.search).toContain("search=batch_1");
  });
  expect(statsUrls.at(-1)?.search).toBe("");

  await user.click(screen.getByRole("button", { name: "重置筛选" }));

  await waitFor(() => {
    expect(listUrls.at(-1)?.searchParams.has("search")).toBe(false);
    expect(new URLSearchParams(window.location.search).has("search")).toBe(false);
  });
});

it.each([
  {
    path: "/task-reports?created_after=2026-07-23T03%3A00%3A00.000Z",
    label: "自定义时间",
  },
  {
    path: "/task-reports?time_range=7d",
    label: "全部时间",
  },
  {
    path:
      "/task-reports?time_range=invalid&created_after=2026-07-23T03%3A00%3A00.000Z",
    label: "自定义时间",
  },
])("restores compatible time label for $path", async ({ path, label }) => {
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 })),
    http.get("/api/v1/task-reports", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 10 })),
    http.get("/api/v1/task-reports/stats", () =>
      HttpResponse.json({
        report_count: 0,
        success_count: 0,
        failure_count: 0,
        average_pass_rate: 0,
      })),
  );

  renderApp(path, { browser: true });

  expect(await screen.findByRole("combobox", { name: "时间筛选" }))
    .toHaveTextContent(label);
});

it("keeps report pagination fixed at ten items per page", async () => {
  const requests: URL[] = [];
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 })),
    http.get("/api/v1/task-reports", ({ request }) => {
      requests.push(new URL(request.url));
      return HttpResponse.json({
        items: [report],
        total: 31,
        page: Number(new URL(request.url).searchParams.get("page") ?? 1),
        page_size: Number(
          new URL(request.url).searchParams.get("page_size") ?? 10,
        ),
      });
    }),
    http.get("/api/v1/task-reports/stats", () =>
      HttpResponse.json({
        report_count: 31,
        success_count: 1,
        failure_count: 0,
        average_pass_rate: 94.44,
      })),
  );

  renderApp("/task-reports?page=2&page_size=20", { strict: true });
  await waitFor(() =>
    expect(requests.at(-1)?.searchParams.get("page")).toBe("2")
  );
  expect(requests.at(-1)?.searchParams.get("page_size")).toBe("10");
  expect(screen.getByRole("table")).toHaveClass("task-table");
  expect(screen.queryByRole("combobox", { name: "每页条数" })).not.toBeInTheDocument();
});

it("keeps a deleted plan URL filter visible and applied until reset", async () => {
  const listUrls: URL[] = [];
  const statsUrls: URL[] = [];
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({
        items: [plan(1)],
        total: 1,
        page: 1,
        page_size: 100,
      })),
    http.get("/api/v1/test-plans/plan_deleted", () =>
      HttpResponse.json(
        {
          error: {
            code: "test_plan_not_found",
            message: "Test plan not found",
          },
        },
        { status: 404 },
      )),
    http.get("/api/v1/task-reports", ({ request }) => {
      listUrls.push(new URL(request.url));
      return HttpResponse.json({
        items: [report],
        total: 1,
        page: 1,
        page_size: 10,
      } satisfies PlanReportListResponse);
    }),
    http.get("/api/v1/task-reports/stats", ({ request }) => {
      statsUrls.push(new URL(request.url));
      return HttpResponse.json({
        report_count: 1,
        success_count: 1,
        failure_count: 0,
        average_pass_rate: 94.44,
      } satisfies PlanReportStatsResponse);
    }),
  );

  renderApp("/task-reports?test_plan_id=plan_deleted", { browser: true });

  const planFilter = await screen.findByRole("combobox", {
    name: "测试计划筛选",
  });
  await waitFor(() =>
    expect(planFilter).toHaveTextContent("已删除计划（plan_deleted）")
  );
  await waitFor(() => {
    expect(listUrls.at(-1)?.searchParams.get("test_plan_id"))
      .toBe("plan_deleted");
    expect(statsUrls.at(-1)?.search).toBe("");
  });

  await user.click(screen.getByRole("button", { name: "重置筛选" }));

  expect(planFilter).toHaveTextContent("全部任务");
  await waitFor(() => {
    expect(listUrls.at(-1)?.searchParams.has("test_plan_id")).toBe(false);
    expect(statsUrls.at(-1)?.searchParams.has("test_plan_id")).toBe(false);
  });
});

it("restores filters and pagination from browser Back and Forward", async () => {
  const listUrls: URL[] = [];
  const statsUrls: URL[] = [];
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({
        items: [plan(1)],
        total: 1,
        page: 1,
        page_size: 100,
      })),
    http.get("/api/v1/task-reports", ({ request }) => {
      const url = new URL(request.url);
      listUrls.push(url);
      return HttpResponse.json({
        items: [report],
        total: 31,
        page: Number(url.searchParams.get("page") ?? 1),
        page_size: Number(url.searchParams.get("page_size") ?? 10),
      } satisfies PlanReportListResponse);
    }),
    http.get("/api/v1/task-reports/stats", ({ request }) => {
      statsUrls.push(new URL(request.url));
      return HttpResponse.json({
        report_count: 31,
        success_count: 1,
        failure_count: 0,
        average_pass_rate: 94.44,
      } satisfies PlanReportStatsResponse);
    }),
  );

  renderApp("/task-reports", { browser: true });
  window.history.pushState(window.history.state, "", "/task-reports");
  const planFilter = await screen.findByRole("combobox", {
    name: "测试计划筛选",
  });
  const statusFilter = screen.getByRole("combobox", {
    name: "报告状态筛选",
  });
  const timeFilter = screen.getByRole("combobox", { name: "时间筛选" });

  await user.click(planFilter);
  await user.click(screen.getByRole("option", { name: "核心回归" }));
  await user.click(statusFilter);
  await user.click(screen.getByRole("option", { name: "成功" }));
  await user.click(timeFilter);
  await user.click(screen.getByRole("option", { name: "最近一周" }));
  await user.click(screen.getByRole("button", { name: "下一页" }));

  await waitFor(() => {
    expect(window.location.search).toContain("page=2");
    expect(window.location.search).not.toContain("page_size");
  });

  const assertLatestRequests = (
    expected: Record<string, string | null | "present">,
  ) => {
    const list = listUrls.at(-1);
    const stats = statsUrls.at(-1);
    for (const [key, value] of Object.entries(expected)) {
      if (value === "present") {
        expect(list?.searchParams.get(key)).toBeTruthy();
      } else {
        expect(list?.searchParams.get(key)).toBe(value);
      }
    }
    expect(stats?.search).toBe("");
  };

  window.history.back();
  await waitFor(() => {
    expect(screen.getByText("第 1 / 4 页")).toBeVisible();
    assertLatestRequests({
      test_plan_id: "plan_1",
      status: "success",
      created_after: "present",
      page: "1",
      page_size: "10",
    });
  });

  window.history.back();
  await waitFor(() => {
    expect(timeFilter).toHaveTextContent("全部时间");
    assertLatestRequests({
      test_plan_id: "plan_1",
      status: "success",
      created_after: null,
    });
  });

  window.history.back();
  await waitFor(() => {
    expect(statusFilter).toHaveTextContent("全部结果");
    assertLatestRequests({
      test_plan_id: "plan_1",
      status: null,
      created_after: null,
    });
  });

  window.history.back();
  await waitFor(() => {
    expect(planFilter).toHaveTextContent("全部任务");
    assertLatestRequests({
      test_plan_id: null,
      status: null,
      created_after: null,
    });
  });

  window.history.forward();
  await waitFor(() => {
    expect(planFilter).toHaveTextContent("核心回归");
    assertLatestRequests({
      test_plan_id: "plan_1",
      status: null,
      created_after: null,
    });
  });

  window.history.forward();
  await waitFor(() => {
    expect(statusFilter).toHaveTextContent("成功");
    assertLatestRequests({
      test_plan_id: "plan_1",
      status: "success",
      created_after: null,
    });
  });

  window.history.forward();
  await waitFor(() => {
    expect(timeFilter).toHaveTextContent("最近一周");
    assertLatestRequests({
      test_plan_id: "plan_1",
      status: "success",
      created_after: "present",
    });
  });

  window.history.forward();
  await waitFor(() => {
    expect(screen.getByText("第 2 / 4 页")).toBeVisible();
    assertLatestRequests({
      test_plan_id: "plan_1",
      status: "success",
      created_after: "present",
      page: "2",
      page_size: "10",
    });
  });
});
