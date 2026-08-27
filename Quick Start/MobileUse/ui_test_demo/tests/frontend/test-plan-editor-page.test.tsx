import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

import type {
  TagOptionListResponse,
  TestCase,
  TestCaseListResponse,
  TestPlan,
} from "../../web/api/types";
import appSource from "../../web/app.tsx?raw";
import mainSource from "../../web/main.tsx?raw";
import editorSource from "../../web/pages/test-plan-editor-page.tsx?raw";
import { expectCsrf, renderApp, server, user } from "./setup";

const STYLES = readFileSync("web/styles.css", "utf8");

function makeCase(index: number): TestCase {
  return {
    id: `case_${String(index).padStart(2, "0")}`,
    title: `计划用例 ${String(index).padStart(2, "0")}`,
    module: index % 2 ? "登录" : "支付",
    content_markdown: `## 执行任务\n验证 ${index}`,
    tags: index % 2 ? ["P0"] : ["smoke"],
    automation_level: "auto",
    execution_count: index,
    pass_count: index,
    fail_count: 0,
    last_executed_at: "2026-07-29T12:03:00Z",
    created_by: "admin",
    created_at: "2026-07-28T00:00:00Z",
    updated_at: "2026-07-29T12:03:00Z",
  };
}

const tagList: TagOptionListResponse = {
  items: [
    {
      name: "P0",
      foreground_color: "#4338CA",
      background_color: "#4338CA1A",
      case_count: 8,
    },
    {
      name: "smoke",
      foreground_color: "#0F766E",
      background_color: "#0F766E1A",
      case_count: 6,
    },
    {
      name: "核心链路",
      foreground_color: "#92400E",
      background_color: "#92400E1A",
      case_count: 3,
    },
  ],
  total: 3,
  page: 1,
  page_size: 100,
};

function installSharedHandlers(cases: TestCase[] = [makeCase(1)]) {
  server.use(
    http.get("/api/v1/tags", () => HttpResponse.json(tagList)),
    http.get("/api/v1/cases/modules", () =>
      HttpResponse.json({ items: ["登录", "支付"] }),
    ),
    http.get("/api/v1/cases", ({ request }) => {
      const url = new URL(request.url);
      return HttpResponse.json<TestCaseListResponse>({
        items: cases,
        total: cases.length,
        page: Number(url.searchParams.get("page") ?? 1),
        page_size: Number(url.searchParams.get("page_size") ?? 10),
      });
    }),
  );
}

it("uses the official Data Router blocker instead of a popstate guard", () => {
  expect(mainSource).toContain("createBrowserRouter");
  expect(mainSource).toContain("RouterProvider");
  expect(editorSource).toContain("useBlocker");
  expect(editorSource).not.toContain("popstate");
  expect(editorSource).not.toContain("historyIndexRef");
});

it("keeps test plan and report routes in the main bundle", () => {
  expect(appSource).not.toContain("lazy(");
  expect(appSource).not.toContain("import(\"./pages/test-plan");
  expect(appSource).not.toContain("import(\"./pages/task-report-list-page");
  expect(appSource).not.toContain("import(\"./pages/plan-execution-report-page");
});

it("aligns basic info inputs in a wide name and compact metadata row", () => {
  expect(STYLES).toMatch(
    /\.plan-basic-grid\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+160px\s+260px;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-tag-input-area\s*\{[^}]*min-height:\s*36px;/s,
  );
  expect(STYLES).toMatch(
    /\.plan-tag-input-area \.tag-list\.editable\s*\{[^}]*align-items:\s*center;/s,
  );
});

it("validates, sends repeated candidate tags, saves ordered cases, and returns", async () => {
  const seenTags: string[][] = [];
  let savedBody: Record<string, unknown> | null = null;
  installSharedHandlers();
  server.use(
    http.get("/api/v1/cases", ({ request }) => {
      const url = new URL(request.url);
      seenTags.push(url.searchParams.getAll("tag"));
      return HttpResponse.json<TestCaseListResponse>({
        items: [makeCase(1)],
        total: 1,
        page: 1,
        page_size: 10,
      });
    }),
    http.post("/api/v1/test-plans", async ({ request }) => {
      expectCsrf(request);
      savedBody = await request.json() as Record<string, unknown>;
      return HttpResponse.json(
        {
          id: "plan_created",
          ...savedBody,
          tags: [],
          case_count: 1,
          execution_count: 0,
          latest_execution: null,
          created_by: "admin",
          created_at: "2026-07-30T00:00:00Z",
          updated_at: "2026-07-30T00:00:00Z",
        },
        { status: 201 },
      );
    }),
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 10 }),
    ),
    http.get("/api/v1/test-plans/tags", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 1 }),
    ),
    http.get("/api/v1/test-plans/stats", () =>
      HttpResponse.json({
        active_plan_count: 0,
        distinct_case_count: 0,
        execution_count: 0,
        latest_completed_pass_rate: 0,
      }),
    ),
  );

  renderApp("/test-plans/new");
  expect(await screen.findByRole("heading", { name: "新建测试计划" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "保存测试计划" }));
  expect(await screen.findByText("请输入测试计划名称")).toBeVisible();
  expect(screen.getByLabelText("测试计划名称")).toHaveFocus();

  await user.type(screen.getByLabelText("测试计划名称"), "核心回归");
  await user.click(screen.getByRole("combobox", { name: "测试类型" }));
  await user.click(screen.getByRole("option", { name: "新功能测试" }));
  await user.type(screen.getByLabelText("计划标签输入"), "自定义计划标签{enter}");
  await user.click(screen.getByRole("combobox", { name: "候选标签" }));
  await user.click(screen.getByRole("option", { name: /P0/ }));
  await user.click(screen.getByRole("option", { name: /smoke/ }));

  await waitFor(() =>
    expect(seenTags.some((tags) =>
      tags.length === 2 && tags.includes("P0") && tags.includes("smoke"),
    )).toBe(true),
  );
  await user.click(await screen.findByRole("checkbox", { name: "选择 计划用例 01" }));
  await user.click(screen.getByRole("button", { name: "保存测试计划" }));

  await waitFor(() => expect(savedBody).not.toBeNull());
  expect(savedBody).toMatchObject({
    name: "核心回归",
    test_type: "new_feature",
    tags: ["自定义计划标签"],
    case_ids: ["case_01"],
  });
  expect(await screen.findByRole("heading", { name: "测试计划" })).toBeVisible();
});

it("loads every selected-case page and keeps global order when moving across pages", async () => {
  const cases = Array.from({ length: 12 }, (_, index) => makeCase(index + 1));
  const requestedPages: number[] = [];
  let savedOrder: string[] = [];
  const plan: TestPlan = {
    id: "plan_12",
    name: "十二用例回归",
    description: "验证跨页顺序",
    test_type: "regression",
    tags: [tagList.items[2]],
    case_ids: cases.map((item) => item.id),
    case_count: 12,
    execution_count: 0,
    latest_execution: null,
    created_by: "admin",
    created_at: "2026-07-29T00:00:00Z",
    updated_at: "2026-07-29T00:00:00Z",
  };
  installSharedHandlers([]);
  server.use(
    http.get("/api/v1/test-plans/plan_12", () => HttpResponse.json(plan)),
    http.get("/api/v1/test-plans/plan_12/cases", ({ request }) => {
      const url = new URL(request.url);
      const page = Number(url.searchParams.get("page") ?? 1);
      const pageSize = Number(url.searchParams.get("page_size") ?? 10);
      requestedPages.push(page);
      const start = (page - 1) * pageSize;
      return HttpResponse.json({
        items: cases.slice(start, start + pageSize),
        total: cases.length,
        page,
        page_size: pageSize,
      });
    }),
    http.put("/api/v1/test-plans/plan_12", async ({ request }) => {
      expectCsrf(request);
      const body = await request.json() as { case_ids: string[] };
      savedOrder = body.case_ids;
      return HttpResponse.json(plan);
    }),
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 10 }),
    ),
    http.get("/api/v1/test-plans/tags", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 1 }),
    ),
    http.get("/api/v1/test-plans/stats", () =>
      HttpResponse.json({
        active_plan_count: 1,
        distinct_case_count: 12,
        execution_count: 0,
        latest_completed_pass_rate: 0,
      }),
    ),
  );

  renderApp("/test-plans/plan_12/edit");
  expect(await screen.findByRole("heading", { name: "编辑测试计划" })).toBeVisible();
  expect(await screen.findByText("已选用例（12）")).toBeVisible();
  expect(requestedPages).toEqual(expect.arrayContaining([1, 2]));

  const selectedSection = screen.getByText("已选用例（12）").closest("section");
  expect(selectedSection).not.toBeNull();
  await user.click(
    within(selectedSection as HTMLElement).getByRole("button", { name: "下一页" }),
  );
  const case12 = await within(selectedSection as HTMLElement).findByText("case_12");
  const case12Row = case12.closest("tr");
  expect(case12Row).not.toBeNull();
  await user.click(
    within(case12Row as HTMLElement).getByRole("button", { name: "置顶 case_12" }),
  );

  expect(
    within(selectedSection as HTMLElement).getByText("case_12").closest("tr"),
  ).toHaveTextContent("1");
  await user.click(screen.getByRole("button", { name: "保存测试计划" }));
  await waitFor(() => expect(savedOrder[0]).toBe("case_12"));
});

it("shows stable API errors without dropping the form state", async () => {
  installSharedHandlers([makeCase(1)]);
  server.use(
    http.post("/api/v1/test-plans", () =>
      HttpResponse.json(
        {
          error: {
            code: "test_plan_name_conflict",
            message: "name conflict",
          },
        },
        { status: 409 },
      ),
    ),
  );
  renderApp("/test-plans/new");
  await user.type(await screen.findByLabelText("测试计划名称"), "重复计划");
  await user.click(screen.getByRole("checkbox", { name: "选择 计划用例 01" }));
  await user.click(screen.getByRole("button", { name: "保存测试计划" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "已有同名测试计划",
  );
  expect(screen.getByLabelText("测试计划名称")).toHaveValue("重复计划");
});

it("loads every candidate tag page so tag selection is not capped at one hundred", async () => {
  const allTags = Array.from({ length: 101 }, (_, index) => ({
    name: `标签${String(index + 1).padStart(3, "0")}`,
    foreground_color: "#4338CA",
    background_color: "#4338CA1A",
    case_count: 0,
  }));
  const requestedPages: number[] = [];
  server.use(
    http.get("/api/v1/tags", ({ request }) => {
      const url = new URL(request.url);
      const page = Number(url.searchParams.get("page") ?? 1);
      const pageSize = Number(url.searchParams.get("page_size") ?? 100);
      requestedPages.push(page);
      const start = (page - 1) * pageSize;
      return HttpResponse.json({
        items: allTags.slice(start, start + pageSize),
        total: allTags.length,
        page,
        page_size: pageSize,
      });
    }),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 10 }),
    ),
  );

  renderApp("/test-plans/new");
  await user.click(
    await screen.findByRole("combobox", { name: "候选标签" }),
  );

  expect(await screen.findByRole("option", { name: /标签101/ })).toBeVisible();
  expect(requestedPages).toEqual(expect.arrayContaining([1, 2]));
});

it("retries candidate-case loading without discarding form input", async () => {
  let fail = true;
  server.use(
    http.get("/api/v1/tags", () => HttpResponse.json(tagList)),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases", () => {
      if (fail) {
        return HttpResponse.json(
          { error: { code: "request_failed", message: "candidate failed" } },
          { status: 503 },
        );
      }
      return HttpResponse.json({
        items: [makeCase(1)],
        total: 1,
        page: 1,
        page_size: 10,
      });
    }),
  );

  renderApp("/test-plans/new");
  await user.type(await screen.findByLabelText("测试计划名称"), "保留输入");
  expect(await screen.findByRole("alert")).toHaveTextContent("候选用例加载失败");
  fail = false;
  await user.click(
    screen.getByRole("button", { name: "重新加载候选用例" }),
  );

  expect(
    await screen.findByRole("checkbox", { name: "选择 计划用例 01" }),
  ).toBeVisible();
  expect(screen.getByLabelText("测试计划名称")).toHaveValue("保留输入");
});

it("confirms before leaving a dirty editor through the sidebar", async () => {
  installSharedHandlers([]);
  server.use(
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: [] })),
  );
  renderApp("/test-plans/new");
  await user.type(await screen.findByLabelText("测试计划名称"), "未保存计划");
  const navigation = screen.getByRole("navigation", { name: "主导航" });
  await user.click(within(navigation).getByRole("link", { name: "用例库" }));

  expect(
    await screen.findByRole("dialog", { name: "离开编辑页面" }),
  ).toBeVisible();
  expect(screen.getByRole("heading", { name: "新建测试计划" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "确认离开" }));
  expect(await screen.findByRole("heading", { name: "用例库" })).toBeVisible();
});

it("confirms browser back navigation and supports cancel then confirm", async () => {
  installSharedHandlers([]);
  server.use(
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: [] })),
  );
  window.history.replaceState(
    { idx: 0, key: "cases", usr: null },
    "",
    "/cases",
  );
  window.history.pushState(
    { idx: 1, key: "editor", usr: null },
    "",
    "/test-plans/new",
  );

  try {
    renderApp("/test-plans/new", { browser: true });
    await user.type(
      await screen.findByLabelText("测试计划名称"),
      "浏览器回退保护",
    );

    window.history.back();
    expect(
      await screen.findByRole("dialog", { name: "离开编辑页面" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "新建测试计划" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "新建测试计划" })).toBeVisible();

    window.history.back();
    await screen.findByRole("dialog", { name: "离开编辑页面" });
    await user.click(screen.getByRole("button", { name: "确认离开" }));
    expect(await screen.findByRole("heading", { name: "用例库" })).toBeVisible();
  } finally {
    window.history.replaceState(
      { idx: 0, key: "root", usr: null },
      "",
      "/",
    );
  }
});

it("confirms browser forward navigation and supports cancel then confirm", async () => {
  installSharedHandlers([]);
  server.use(
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: [] })),
  );
  window.history.replaceState(
    { idx: 0, key: "editor", usr: null },
    "",
    "/test-plans/new",
  );
  window.history.pushState(
    { idx: 1, key: "cases", usr: null },
    "",
    "/cases",
  );
  window.history.back();
  await waitFor(() =>
    expect(window.location.pathname).toBe("/test-plans/new")
  );

  try {
    renderApp("/test-plans/new", { browser: true });
    await user.type(
      await screen.findByLabelText("测试计划名称"),
      "浏览器前进保护",
    );

    window.history.forward();
    expect(
      await screen.findByRole("dialog", { name: "离开编辑页面" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "新建测试计划" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "新建测试计划" })).toBeVisible();

    window.history.forward();
    await screen.findByRole("dialog", { name: "离开编辑页面" });
    await user.click(screen.getByRole("button", { name: "确认离开" }));
    expect(await screen.findByRole("heading", { name: "用例库" })).toBeVisible();
  } finally {
    window.history.replaceState(
      { idx: 0, key: "root", usr: null },
      "",
      "/",
    );
  }
});

it("locks every editor control while save is pending", async () => {
  const cases = [makeCase(1), makeCase(2)];
  installSharedHandlers(cases);
  let releaseRequest: (() => void) | undefined;
  let savedBody: { name: string; case_ids: string[] } | null = null;
  const requestGate = new Promise<void>((resolve) => {
    releaseRequest = resolve;
  });
  server.use(
    http.post("/api/v1/test-plans", async ({ request }) => {
      savedBody = await request.json() as {
        name: string;
        case_ids: string[];
      };
      await requestGate;
      return HttpResponse.json(
        {
          id: "plan_pending",
          ...savedBody,
          description: null,
          tags: [],
          case_count: savedBody.case_ids.length,
          execution_count: 0,
          latest_execution: null,
          created_by: "admin",
          created_at: "2026-07-30T00:00:00Z",
          updated_at: "2026-07-30T00:00:00Z",
        },
        { status: 201 },
      );
    }),
    http.get("/api/v1/test-plans", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 10 }),
    ),
    http.get("/api/v1/test-plans/tags", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 1 }),
    ),
    http.get("/api/v1/test-plans/stats", () =>
      HttpResponse.json({
        active_plan_count: 1,
        distinct_case_count: 2,
        execution_count: 0,
        latest_completed_pass_rate: 0,
      }),
    ),
  );

  renderApp("/test-plans/new");
  const name = await screen.findByLabelText("测试计划名称");
  await user.type(name, "保存中的计划");
  await user.click(screen.getByRole("checkbox", { name: "选择 计划用例 01" }));
  await user.click(screen.getByRole("checkbox", { name: "选择 计划用例 02" }));
  await user.click(screen.getByRole("button", { name: "保存测试计划" }));

  await waitFor(() =>
    expect(screen.getByRole("button", { name: "保存测试计划" })).toBeDisabled()
  );
  expect(name).toBeDisabled();
  expect(screen.getByLabelText("计划描述")).toBeDisabled();
  expect(screen.getByLabelText("搜索候选用例")).toBeDisabled();
  expect(screen.getByLabelText("计划标签输入")).toBeDisabled();
  expect(screen.getByRole("combobox", { name: "候选模块" })).toBeDisabled();
  expect(screen.getByRole("checkbox", { name: "选择 计划用例 01" }))
    .toBeDisabled();
  expect(screen.getByRole("link", { name: "取消" })).toHaveAttribute(
    "aria-disabled",
    "true",
  );

  const selectedSection = screen.getByText("已选用例（2）").closest("section");
  const firstRow = within(selectedSection as HTMLElement)
    .getByText("case_01").closest("tr");
  expect(
    within(firstRow as HTMLElement).getByRole("button", {
      name: "下移 case_01",
    }),
  ).toBeDisabled();
  fireEvent.change(name, { target: { value: "不应写入" } });
  expect(name).toHaveValue("保存中的计划");

  releaseRequest?.();
  expect(await screen.findByRole("heading", { name: "测试计划" })).toBeVisible();
  expect(savedBody).toMatchObject({
    name: "保存中的计划",
    case_ids: ["case_01", "case_02"],
  });
});

it("blocks history navigation silently while saving and restores dirty confirmation after failure", async () => {
  installSharedHandlers([makeCase(1)]);
  let releaseRequest: (() => void) | undefined;
  const requestGate = new Promise<void>((resolve) => {
    releaseRequest = resolve;
  });
  server.use(
    http.post("/api/v1/test-plans", async () => {
      await requestGate;
      return HttpResponse.json(
        {
          error: {
            code: "request_failed",
            message: "forced save failure",
          },
        },
        { status: 503 },
      );
    }),
  );
  window.history.replaceState(
    { idx: 0, key: "cases", usr: null },
    "",
    "/cases",
  );
  window.history.pushState(
    { idx: 1, key: "editor", usr: null },
    "",
    "/test-plans/new",
  );

  try {
    renderApp("/test-plans/new", { browser: true });
    await user.type(
      await screen.findByLabelText("测试计划名称"),
      "失败后保持脏状态",
    );
    await user.click(
      screen.getByRole("checkbox", { name: "选择 计划用例 01" }),
    );
    await user.click(screen.getByRole("button", { name: "保存测试计划" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "保存测试计划" })).toBeDisabled()
    );

    window.history.back();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "新建测试计划" }),
      ).toBeVisible()
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    releaseRequest?.();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "forced save failure",
    );
    window.history.back();
    expect(
      await screen.findByRole("dialog", { name: "离开编辑页面" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "新建测试计划" })).toBeVisible();
  } finally {
    releaseRequest?.();
    window.history.replaceState(
      { idx: 0, key: "root", usr: null },
      "",
      "/",
    );
  }
});

it("clears stale validation messages when the related value changes", async () => {
  installSharedHandlers([makeCase(1)]);
  renderApp("/test-plans/new");

  await user.click(
    await screen.findByRole("button", { name: "保存测试计划" }),
  );
  expect(screen.getByText("请输入测试计划名称")).toBeVisible();
  await user.type(screen.getByLabelText("测试计划名称"), "有效名称");
  expect(screen.queryByText("请输入测试计划名称")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "保存测试计划" }));
  expect(screen.getByRole("alert")).toHaveTextContent("请至少选择 1 个测试用例");
  await user.click(screen.getByRole("checkbox", { name: "选择 计划用例 01" }));
  expect(
    screen.queryByText("请至少选择 1 个测试用例"),
  ).not.toBeInTheDocument();
});

it("allows modified link clicks because they do not leave the editor", async () => {
  installSharedHandlers([]);
  renderApp("/test-plans/new");
  await user.type(await screen.findByLabelText("测试计划名称"), "未保存计划");
  const navigation = screen.getByRole("navigation", { name: "主导航" });
  const preventNativeNavigation = (event: MouseEvent) =>
    event.preventDefault();
  document.addEventListener("click", preventNativeNavigation);
  try {
    fireEvent.click(
      within(navigation).getByRole("link", { name: "用例库" }),
      { metaKey: true },
    );
  } finally {
    document.removeEventListener("click", preventNativeNavigation);
  }

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "新建测试计划" })).toBeVisible();
});

it("shows and retries tag or module metadata errors", async () => {
  let fail = true;
  server.use(
    http.get("/api/v1/tags", () => {
      if (fail) {
        return HttpResponse.json(
          { error: { code: "request_failed", message: "tags failed" } },
          { status: 503 },
        );
      }
      return HttpResponse.json(tagList);
    }),
    http.get("/api/v1/cases/modules", () =>
      HttpResponse.json({ items: ["登录"] }),
    ),
    http.get("/api/v1/cases", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 10 }),
    ),
  );

  renderApp("/test-plans/new");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "筛选数据加载失败",
  );
  fail = false;
  await user.click(screen.getByRole("button", { name: "重新加载筛选数据" }));
  await user.click(screen.getByRole("combobox", { name: "候选标签" }));
  expect(await screen.findByRole("option", { name: /P0/ })).toBeVisible();
});

it("disables unselected candidates after reaching the one-hundred-case limit", async () => {
  const selected = Array.from({ length: 100 }, (_, index) =>
    makeCase(index + 1)
  );
  const extra = makeCase(101);
  const plan: TestPlan = {
    id: "plan_100",
    name: "百用例计划",
    description: null,
    test_type: "regression",
    tags: [],
    case_ids: selected.map((item) => item.id),
    case_count: 100,
    execution_count: 0,
    latest_execution: null,
    created_by: "admin",
    created_at: "2026-07-29T00:00:00Z",
    updated_at: "2026-07-29T00:00:00Z",
  };
  installSharedHandlers([extra]);
  server.use(
    http.get("/api/v1/test-plans/plan_100", () => HttpResponse.json(plan)),
    http.get("/api/v1/test-plans/plan_100/cases", ({ request }) => {
      const url = new URL(request.url);
      const page = Number(url.searchParams.get("page") ?? 1);
      const pageSize = Number(url.searchParams.get("page_size") ?? 10);
      const start = (page - 1) * pageSize;
      return HttpResponse.json({
        items: selected.slice(start, start + pageSize),
        total: selected.length,
        page,
        page_size: pageSize,
      });
    }),
  );

  renderApp("/test-plans/plan_100/edit");
  expect(await screen.findByText("已选 100 / 100")).toBeVisible();
  expect(
    await screen.findByRole("checkbox", { name: "选择 计划用例 101" }),
  ).toBeDisabled();
});
