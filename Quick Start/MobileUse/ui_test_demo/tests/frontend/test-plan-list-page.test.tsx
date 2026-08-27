import { QueryClient } from "@tanstack/react-query";
import { screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, delay, http } from "msw";
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import type {
  TagOptionListResponse,
  TestPlanListResponse,
  TestPlanStatsResponse,
} from "../../web/api/types";
import { expectCsrf, renderApp, server, user } from "./setup";

const STYLES = readFileSync("web/styles.css", "utf8");

afterEach(() => {
  vi.restoreAllMocks();
});

beforeEach(() => {
  server.use(
    http.get("/api/v1/test-plans/tags", () =>
      HttpResponse.json(planTagList)),
  );
});

const stats: TestPlanStatsResponse = {
  active_plan_count: 1,
  distinct_case_count: 4,
  execution_count: 3,
  latest_completed_pass_rate: 88.88,
};

const plans: TestPlanListResponse = {
  items: [
    {
      id: "plan_login",
      name: "登录核心回归",
      description: "每日回归",
      test_type: "regression",
      tags: [
        {
          name: "核心链路",
          foreground_color: "#4338CA",
          background_color: "#4338CA1A",
          case_count: 4,
        },
        {
          name: "P0",
          foreground_color: "#0F766E",
          background_color: "#0F766E1A",
          case_count: 3,
        },
        {
          name: "登录",
          foreground_color: "#92400E",
          background_color: "#92400E1A",
          case_count: 2,
        },
        {
          name: "每日",
          foreground_color: "#1D4ED8",
          background_color: "#1D4ED81A",
          case_count: 1,
        },
      ],
      case_ids: ["case_1", "case_2", "case_3", "case_4"],
      case_count: 4,
      execution_count: 3,
      latest_execution: {
        execution_id: "execution_latest",
        task_batch_id: "batch_latest",
        report_status: "success",
        pass_rate: 100,
        created_at: "2026-07-29T12:03:00Z",
      },
      created_by: "admin",
      created_at: "2026-07-28T00:00:00Z",
      updated_at: "2026-07-29T12:03:00Z",
    },
  ],
  total: 1,
  page: 1,
  page_size: 10,
};

const tagList: TagOptionListResponse = {
  items: [
    {
      name: "P0",
      foreground_color: "#0F766E",
      background_color: "#0F766E1A",
      case_count: 3,
    },
    {
      name: "smoke",
      foreground_color: "#4338CA",
      background_color: "#4338CA1A",
      case_count: 1,
    },
  ],
  total: 2,
  page: 1,
  page_size: 100,
};

const planTagList: TagOptionListResponse = {
  items: [
    {
      name: "核心链路",
      foreground_color: "#4338CA",
      background_color: "#4338CA1A",
      case_count: null,
    },
    {
      name: "P0",
      foreground_color: "#0F766E",
      background_color: "#0F766E1A",
      case_count: null,
    },
    {
      name: "每日",
      foreground_color: "#1D4ED8",
      background_color: "#1D4ED81A",
      case_count: null,
    },
  ],
  total: 3,
  page: 1,
  page_size: 100,
};

function expectedTagToneClass(tag: string): string {
  let hash = 7;
  for (const char of tag) {
    hash = (hash * 33 + char.charCodeAt(0)) >>> 0;
  }
  return `tag-tone-${hash % 5}`;
}

it("keeps search labels accessible without letting them consume control width", () => {
  expect(STYLES).toMatch(
    /\.sr-only\s*\{[^}]*position:\s*absolute[^}]*width:\s*1px[^}]*height:\s*1px[^}]*overflow:\s*hidden/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-search,[\s\S]*?\.plan-case-search\s*\{[^}]*width:\s*270px/s,
  );
  expect(STYLES).toMatch(
    /\.plan-case-search\s*\{[^}]*width:\s*260px/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-table\s*\{[^}]*min-width:\s*1160px;/s,
  );
  expect(STYLES).toMatch(
    /\.task-table th\s*\{[^}]*background:\s*var\(--mua-neutral-50\);/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-table th:first-child\s*\{[^}]*min-width:\s*220px;/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-table th:last-child\s*\{[^}]*width:\s*116px;/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-page \.filter-card\s*\{[^}]*overflow:\s*visible;/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-filter-toolbar\s*\{[^}]*overflow:\s*visible;/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-filter-toolbar\s*\{[^}]*gap:\s*8px;/s,
  );
});

it("keeps global plan KPIs when search has no matches", async () => {
  server.use(
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/test-plans", ({ request }) => {
      const filtered = Boolean(
        new URL(request.url).searchParams.get("search"),
      );
      return HttpResponse.json({
        items: filtered ? [] : plans.items,
        total: filtered ? 0 : plans.total,
        page: 1,
        page_size: 10,
      });
    }),
  );

  renderApp("/test-plans");
  await waitFor(() =>
    expect(screen.getByTestId("plan-metric-active"))
      .toHaveTextContent(String(stats.active_plan_count))
  );
  await user.type(
    screen.getByRole("searchbox", { name: "搜索测试计划" }),
    "missing",
  );

  const message = await screen.findByText(
    "无匹配结果，请调整搜索条件或表头筛选",
  );
  expect(message).toBeVisible();
  expect(screen.getByTestId("plan-metric-active"))
    .toHaveTextContent(String(stats.active_plan_count));
  expect(within(message.closest(".empty-state") as HTMLElement)
    .queryByRole("link", { name: "新建测试计划" }))
    .not.toBeInTheDocument();
});

it("adds the test plan navigation and separates result from latest execution", async () => {
  server.use(
    http.get("/api/v1/test-plans", () => HttpResponse.json(plans)),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/test-plans/tags", () => HttpResponse.json(planTagList)),
  );

  renderApp("/test-plans");

  expect(await screen.findByRole("heading", { name: "测试计划" })).toBeVisible();
  await screen.findByRole("link", { name: "登录核心回归" });
  expect(screen.getByRole("link", { name: "测试计划" })).toHaveAttribute(
    "href",
    "/biz/biz_default/test-plans",
  );
  expect(screen.getAllByRole("columnheader").map((item) => item.textContent)).toEqual([
    "测试计划名称",
    "测试类型",
    "关联用例",
    "标签",
    "总执行次数",
    "最近执行结果",
    "最近执行",
    "操作者",
    "操作",
  ]);
  expect(screen.getByTestId("plan-metric-rate")).toHaveTextContent("89%");
  const row = screen.getByRole("link", { name: "登录核心回归" }).closest("tr");
  expect(row).not.toBeNull();
  const nameWrapper = within(row as HTMLElement)
    .getByRole("link", { name: "登录核心回归" })
    .closest(".test-plan-name-wrapper") as HTMLElement;
  expect(nameWrapper).not.toHaveClass("has-tooltip");
  expect(nameWrapper).not.toHaveAttribute("data-full-title");
  expect(within(row as HTMLElement).getByText("回归测试")).toBeVisible();
  expect(within(row as HTMLElement).getByText("成功")).toBeVisible();
  expect(within(row as HTMLElement).getByText("2026-07-29 20:03:00")).toBeVisible();
  expect(within(row as HTMLElement).getByText("admin")).toBeVisible();
  expect(within(row as HTMLElement).getByRole("link", { name: /batch_latest/ }))
    .toHaveAttribute("href", "/biz/biz_default/task-reports/execution_latest");
  expect(within(row as HTMLElement).getByText("+1")).toBeVisible();
  expect(within(row as HTMLElement).getByRole("link", { name: "执行测试计划" }))
    .toHaveAttribute("href", "/biz/biz_default/test-plans/plan_login/run");
  expect(within(row as HTMLElement).getByRole("link", { name: "编辑测试计划" }))
    .toHaveAttribute("href", "/biz/biz_default/test-plans/plan_login/edit");
  expect(within(row as HTMLElement).getByRole("button", { name: "删除测试计划" }))
    .toBeVisible();
  const actions = (row as HTMLElement).querySelectorAll(
    ".test-plan-row-actions a, .test-plan-row-actions button",
  );
  expect(actions).toHaveLength(3);
  actions.forEach((element) => expect(element).toHaveClass("icon-action"));
});

it("centers case and tag columns and uses distinct colors for types and tags", async () => {
  const newFeaturePlan = {
    ...plans.items[0],
    id: "plan_new_feature",
    name: "新功能验收",
    test_type: "new_feature" as const,
    tags: [
      {
        name: "新功能",
        foreground_color: "#B45309",
        background_color: "#FEF3C7",
        case_count: null,
      },
    ],
  };
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({
        ...plans,
        items: [plans.items[0], newFeaturePlan],
        total: 2,
      })),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/test-plans/tags", () => HttpResponse.json(planTagList)),
  );

  renderApp("/test-plans");

  const regressionRow = (await screen.findByRole("link", {
    name: "登录核心回归",
  })).closest("tr") as HTMLElement;
  const newFeatureRow = screen.getByRole("link", {
    name: "新功能验收",
  }).closest("tr") as HTMLElement;
  expect(within(regressionRow).getByText("回归测试"))
    .toHaveClass("test-plan-type-badge", "regression");
  expect(within(newFeatureRow).getByText("新功能测试"))
    .toHaveClass("test-plan-type-badge", "new-feature");
  const tag = within(newFeatureRow).getByText("新功能");
  expect(tag).toHaveClass("tag", expectedTagToneClass("新功能"));
  expect(tag).not.toHaveClass("registered-tag");
  expect(tag).not.toHaveAttribute("style");
  const coreTag = within(regressionRow).getByText("核心链路");
  const p0Tag = within(regressionRow).getByText("P0");
  expect(coreTag).toHaveClass("tag", expectedTagToneClass("核心链路"));
  expect(p0Tag).toHaveClass("tag", expectedTagToneClass("P0"));
  expect(STYLES).toMatch(
    /\.test-plan-table th:nth-child\(3\),[\s\S]*?\.test-plan-table th:nth-child\(4\)\s*\{[^}]*text-align:\s*center;/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-table td:nth-child\(3\),[\s\S]*?\.test-plan-table td:nth-child\(4\)\s*\{[^}]*text-align:\s*center;/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-table td:nth-child\(4\)\s+\.test-plan-tags\s*\{[^}]*justify-content:\s*center;/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-type-badge\.regression\s*\{[^}]*background:\s*#ecfeff;[^}]*color:\s*#0e7490;/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-type-badge\.new-feature\s*\{[^}]*background:\s*var\(--state-review-bg\);[^}]*color:\s*var\(--state-review-fg\);/s,
  );
});

it("keeps long test plan names compact and supports copying the full name", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
  const longName = "完整链路回归测试计划-这是一个非常长的测试计划名称用于验证列表展示截断和复制完整名称";
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({
        ...plans,
        items: [{ ...plans.items[0], name: longName }],
      })),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
  );

  renderApp("/test-plans");

  const link = await screen.findByRole("link", { name: longName });
  const wrapper = link.closest(".test-plan-name-wrapper") as HTMLElement;
  expect(wrapper).toHaveClass("has-tooltip");
  expect(wrapper).toHaveAttribute("data-full-title", longName);
  expect(link).toHaveAttribute("title", longName);
  expect(STYLES).toMatch(
    /\.test-plan-name-wrapper\s*\{[^}]*max-width:\s*260px;[^}]*position:\s*relative/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-name-wrapper\.has-tooltip::after\s*\{[^}]*background:\s*var\(--mua-card\);[^}]*content:\s*attr\(data-full-title\)/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-name-wrapper\.has-tooltip:hover::after,[\s\S]*?\.test-plan-name-wrapper\.has-tooltip:focus-within::after\s*\{[^}]*opacity:\s*1/s,
  );
  expect(STYLES).toMatch(
    /\.test-plan-name-line\s*\{[^}]*display:\s*inline-flex;[^}]*max-width:\s*260px/s,
  );

  const row = link.closest("tr") as HTMLElement;
  await user.click(within(row).getByRole("button", { name: "复制测试计划名称" }));

  await waitFor(() => expect(writeText).toHaveBeenCalledWith(longName));
});

it("uses only existing plan tags for the plan tag filter", async () => {
  server.use(
    http.get("/api/v1/test-plans", () => HttpResponse.json(plans)),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/tags", () => HttpResponse.json(tagList)),
    http.get("/api/v1/test-plans/tags", () =>
      HttpResponse.json(planTagList)),
  );

  renderApp("/test-plans");

  await user.click(await screen.findByRole("combobox", {
    name: "标签筛选",
  }));

  expect(screen.getByRole("option", { name: "核心链路" })).toBeVisible();
  expect(screen.queryByRole("option", { name: "smoke" }))
    .not.toBeInTheDocument();
});

it("falls back to regression when an existing plan has no test type", async () => {
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({
        ...plans,
        items: plans.items.map((plan) => ({
          ...plan,
          test_type: "" as "regression",
        })),
      })),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/tags", () => HttpResponse.json(tagList)),
  );

  renderApp("/test-plans");

  const row = (await screen.findByRole("link", {
    name: "登录核心回归",
  })).closest("tr");
  expect(row).not.toBeNull();
  expect(within(row as HTMLElement).getByText("回归测试")).toBeVisible();
});

it("filters visible plan rows by tag and test type", async () => {
  const smokePlan = {
    ...plans.items[0],
    id: "plan_smoke",
    name: "冒烟新功能计划",
    test_type: "new_feature" as const,
    tags: [tagList.items[0]],
  };
  server.use(
    http.get("/api/v1/test-plans", ({ request }) => {
      const url = new URL(request.url);
      const tag = url.searchParams.get("tag");
      const testType = url.searchParams.get("test_type");
      const items = testType === "new_feature" || tag === "P0"
        ? [smokePlan]
        : plans.items;
      return HttpResponse.json({
        items,
        total: items.length,
        page: 1,
        page_size: 10,
      });
    }),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/tags", () => HttpResponse.json(tagList)),
  );

  renderApp("/test-plans");

  expect(await screen.findByRole("link", { name: "登录核心回归" }))
    .toBeVisible();
  await user.click(screen.getByRole("combobox", { name: "标签筛选" }));
  await user.click(screen.getByRole("option", { name: "P0" }));

  expect(await screen.findByRole("link", { name: "冒烟新功能计划" }))
    .toBeVisible();
  expect(screen.queryByRole("link", { name: "登录核心回归" }))
    .not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "重置筛选" }));
  expect(await screen.findByRole("link", { name: "登录核心回归" }))
    .toBeVisible();
  await user.click(screen.getByRole("combobox", { name: "测试类型筛选" }));
  await user.click(screen.getByRole("option", { name: "新功能测试" }));

  expect(await screen.findByRole("link", { name: "冒烟新功能计划" }))
    .toBeVisible();
  expect(screen.queryByRole("link", { name: "登录核心回归" }))
    .not.toBeInTheDocument();
});

it("filters visible plan rows by creator", async () => {
  const seenCreators: string[] = [];
  server.use(
    http.get("/api/v1/test-plans", ({ request }) => {
      const creator = new URL(request.url).searchParams.get("created_by");
      seenCreators.push(creator ?? "");
      const items = creator === "alice"
        ? [{ ...plans.items[0], id: "plan_alice", name: "Alice 计划", created_by: "alice" }]
        : plans.items;
      return HttpResponse.json({
        items,
        total: items.length,
        page: 1,
        page_size: 10,
      });
    }),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/test-plans/creators", () =>
      HttpResponse.json({ items: ["admin", "alice"] })),
  );

  renderApp("/test-plans");

  await screen.findByRole("link", { name: "登录核心回归" });
  await user.click(screen.getByRole("combobox", { name: "操作者筛选" }));
  await user.click(screen.getByRole("option", { name: "alice" }));

  await waitFor(() => expect(seenCreators).toContain("alice"));
  expect(await screen.findByRole("link", { name: "Alice 计划" })).toBeVisible();
  expect(screen.getByRole("combobox", { name: "操作者筛选" }))
    .toHaveTextContent("alice");
});

it("confirms and deletes a plan from the list", async () => {
  let deleted = false;
  const invalidateQueries = vi.spyOn(
    QueryClient.prototype,
    "invalidateQueries",
  );
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json(
        deleted ? { ...plans, items: [], total: 0 } : plans,
      )),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/test-plans/tags", () => HttpResponse.json(planTagList)),
    http.delete("/api/v1/test-plans/plan_login", ({ request }) => {
      expectCsrf(request);
      deleted = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );

  renderApp("/test-plans");
  const row = (await screen.findByRole("link", {
    name: "登录核心回归",
  })).closest("tr");
  await user.click(
    within(row as HTMLElement).getByRole("button", { name: "删除测试计划" }),
  );
  expect(screen.getByRole("dialog")).toHaveTextContent(
    "历史报告不会删除",
  );
  await user.click(screen.getByRole("button", { name: "确认删除" }));
  expect(await screen.findByText("暂无测试计划")).toBeVisible();
  expect(invalidateQueries).toHaveBeenCalledTimes(3);
  expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
    queryKey: ["test-plans"],
  });
  expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
    queryKey: ["test-plan-stats"],
  });
  expect(invalidateQueries).toHaveBeenNthCalledWith(3, {
    queryKey: ["task-reports"],
  });
});

it("removes the deleted row and blocks repeat deletion while refetch is pending", async () => {
  let deleted = false;
  let deleteRequests = 0;
  let releaseRefetch: () => void = () => undefined;
  const refetchGate = new Promise<void>((resolve) => {
    releaseRefetch = resolve;
  });
  server.use(
    http.get("/api/v1/test-plans", async () => {
      if (!deleted) return HttpResponse.json(plans);
      await refetchGate;
      return HttpResponse.json({ ...plans, items: [], total: 0 });
    }),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/test-plans/tags", () => HttpResponse.json(planTagList)),
    http.delete("/api/v1/test-plans/plan_login", () => {
      deleteRequests += 1;
      deleted = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );

  renderApp("/test-plans");
  const row = (await screen.findByRole("link", {
    name: "登录核心回归",
  })).closest("tr");
  await user.click(
    within(row as HTMLElement).getByRole("button", { name: "删除测试计划" }),
  );
  await user.click(screen.getByRole("button", { name: "确认删除" }));

  await waitFor(() => expect(deleteRequests).toBe(1));
  expect(
    screen.queryByRole("link", { name: "登录核心回归" }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("dialog")).toBeVisible();
  const pendingDelete = screen.getByRole("button", { name: "正在删除…" });
  expect(pendingDelete).toBeDisabled();
  await user.click(pendingDelete);
  expect(deleteRequests).toBe(1);

  releaseRefetch();
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  );
});

it("does not treat the report plan-filter cache as a paginated plan list", async () => {
  let deleted = false;
  let deleteRequests = 0;
  server.use(
    http.get("/api/v1/test-plans", ({ request }) => {
      const pageSize = Number(
        new URL(request.url).searchParams.get("page_size") ?? 10,
      );
      return HttpResponse.json(
        deleted
          ? { ...plans, items: [], total: 0, page_size: pageSize }
          : { ...plans, page_size: pageSize },
      );
    }),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/test-plans/tags", () => HttpResponse.json(planTagList)),
    http.get("/api/v1/task-reports", () =>
      HttpResponse.json({
        items: [],
        total: 0,
        page: 1,
        page_size: 10,
      })),
    http.get("/api/v1/task-reports/stats", () =>
      HttpResponse.json({
        report_count: 0,
        success_count: 0,
        failure_count: 0,
        average_pass_rate: 0,
      })),
    http.delete("/api/v1/test-plans/plan_login", () => {
      deleteRequests += 1;
      deleted = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );

  renderApp("/task-reports", { browser: true });
  expect(await screen.findByRole("heading", { name: "测试报告" })).toBeVisible();
  expect(
    screen.getByRole("combobox", { name: "测试计划筛选" }),
  ).toHaveTextContent("全部任务");

  await user.click(screen.getByRole("link", { name: "测试计划" }));
  const row = (await screen.findByRole("link", {
    name: "登录核心回归",
  })).closest("tr");
  await user.click(
    within(row as HTMLElement).getByRole("button", { name: "删除测试计划" }),
  );
  await user.click(screen.getByRole("button", { name: "确认删除" }));

  await waitFor(() => expect(deleteRequests).toBe(1));
  expect(await screen.findByText("暂无测试计划")).toBeVisible();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.queryByText("删除失败，请稍后重试。")).not.toBeInTheDocument();
});

it("keeps the delete dialog open when deletion fails", async () => {
  server.use(
    http.get("/api/v1/test-plans", () => HttpResponse.json(plans)),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/tags", () => HttpResponse.json(tagList)),
    http.delete("/api/v1/test-plans/plan_login", () =>
      HttpResponse.json(
        { error: { code: "request_failed", message: "删除失败" } },
        { status: 503 },
      )),
  );

  renderApp("/test-plans");
  const row = (await screen.findByRole("link", {
    name: "登录核心回归",
  })).closest("tr");
  await user.click(
    within(row as HTMLElement).getByRole("button", { name: "删除测试计划" }),
  );
  await user.click(screen.getByRole("button", { name: "确认删除" }));
  expect(await screen.findByRole("dialog")).toHaveTextContent(
    "删除失败，请稍后重试",
  );
});

it("returns to the previous page after deleting its only row", async () => {
  let deleted = false;
  const requestedPages: string[] = [];
  server.use(
    http.get("/api/v1/test-plans", ({ request }) => {
      const page = new URL(request.url).searchParams.get("page") ?? "1";
      requestedPages.push(page);
      return HttpResponse.json(
        deleted || page === "1"
          ? { ...plans, items: [], total: 10, page: Number(page) }
          : { ...plans, total: 11, page: 2 },
      );
    }),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/test-plans/tags", () => HttpResponse.json(planTagList)),
    http.delete("/api/v1/test-plans/plan_login", () => {
      deleted = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );

  renderApp("/test-plans?page=2", { browser: true });
  const row = (await screen.findByRole("link", {
    name: "登录核心回归",
  })).closest("tr");
  await user.click(
    within(row as HTMLElement).getByRole("button", { name: "删除测试计划" }),
  );
  await user.click(screen.getByRole("button", { name: "确认删除" }));

  await waitFor(() => {
    expect(requestedPages).toContain("1");
    expect(window.location.search).not.toContain("page=2");
  });
});

it("synchronizes live search and backend pagination with the URL", async () => {
  const requests: URL[] = [];
  server.use(
    http.get("/api/v1/test-plans", ({ request }) => {
      requests.push(new URL(request.url));
      return HttpResponse.json({
        ...plans,
        total: 25,
        page: Number(new URL(request.url).searchParams.get("page") ?? 1),
        page_size: Number(
          new URL(request.url).searchParams.get("page_size") ?? 10,
        ),
      });
    }),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
    http.get("/api/v1/test-plans/tags", () => HttpResponse.json(planTagList)),
  );

  renderApp("/test-plans?page=2&page_size=20", {
    browser: true,
    strict: true,
  });
  const search = await screen.findByRole("searchbox", { name: "搜索测试计划" });
  expect(await screen.findByRole("table")).toHaveClass("task-table");
  expect(screen.queryByRole("combobox", { name: "每页条数" })).not.toBeInTheDocument();
  await new Promise((resolve) => window.setTimeout(resolve, 300));
  expect(requests.at(-1)?.searchParams.get("page")).toBe("2");
  expect(requests.at(-1)?.searchParams.get("page_size")).toBe("10");
  await user.type(search, "登录");

  await waitFor(() => {
    const latest = requests.at(-1);
    expect(latest?.searchParams.get("search")).toBe("登录");
    expect(latest?.searchParams.get("page")).toBe("1");
  });

  await user.click(screen.getByRole("combobox", { name: "标签筛选" }));
  await user.click(screen.getByRole("option", { name: "P0" }));

  await waitFor(() => {
    const latest = requests.at(-1);
    expect(latest?.searchParams.get("tag")).toBe("P0");
    expect(latest?.searchParams.get("page")).toBe("1");
    expect(new URLSearchParams(window.location.search).get("tag")).toBe("P0");
  });

  await user.click(screen.getByRole("combobox", { name: "测试类型筛选" }));
  await user.click(screen.getByRole("option", { name: "新功能测试" }));

  await waitFor(() => {
    const latest = requests.at(-1);
    expect(latest?.searchParams.get("test_type")).toBe("new_feature");
    expect(latest?.searchParams.get("page")).toBe("1");
    expect(new URLSearchParams(window.location.search).get("test_type"))
      .toBe("new_feature");
  });

  expect(requests.at(-1)?.searchParams.get("page_size")).toBe("10");
});

it("shows loading, retryable error, and empty states", async () => {
  let fail = true;
  server.use(
    http.get("/api/v1/test-plans", async () => {
      await delay(50);
      if (fail) {
        return HttpResponse.json(
          { error: { code: "request_failed", message: "暂时不可用" } },
          { status: 503 },
        );
      }
      return HttpResponse.json({ ...plans, items: [], total: 0 });
    }),
    http.get("/api/v1/test-plans/stats", () => HttpResponse.json(stats)),
  );

  renderApp("/test-plans");
  expect(
    await screen.findByLabelText("正在加载测试计划"),
  ).toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent("暂时不可用");
  fail = false;
  await user.click(screen.getByRole("button", { name: "重新加载" }));
  expect(await screen.findByText("暂无测试计划")).toBeVisible();
  expect(
    screen.getAllByRole("link", { name: "新建测试计划" }).at(-1),
  ).toBeVisible();
});

it("shows and retries test plan statistics errors", async () => {
  let fail = true;
  server.use(
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 10 }),
    ),
    http.get("/api/v1/test-plans/stats", () => {
      if (fail) {
        return HttpResponse.json(
          { error: { code: "request_failed", message: "stats failed" } },
          { status: 503 },
        );
      }
      return HttpResponse.json({
        active_plan_count: 2,
        distinct_case_count: 3,
        execution_count: 4,
        latest_completed_pass_rate: 50,
      });
    }),
  );

  renderApp("/test-plans");
  expect(await screen.findByRole("alert")).toHaveTextContent("统计数据加载失败");
  fail = false;
  await user.click(screen.getByRole("button", { name: "重新加载统计数据" }));
  await waitFor(() =>
    expect(screen.getByTestId("plan-metric-active")).toHaveTextContent("2"),
  );
});
