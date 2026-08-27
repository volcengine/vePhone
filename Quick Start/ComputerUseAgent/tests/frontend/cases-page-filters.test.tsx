import { screen, waitFor, within } from "@testing-library/react";
import { delay, HttpResponse, http } from "msw";
import { readFileSync } from "node:fs";
import { expect, it, vi } from "vitest";

import type { TestCase, TestCaseListResponse } from "../../web/api/types";
import { expectCsrf, renderApp, server, user } from "./setup";

const STYLES = readFileSync("web/styles.css", "utf8");

it("does not apply read-only cursor styles to case selection checkboxes", () => {
  expect(STYLES).not.toMatch(/input:read-only,\s*input\[readonly\]\s*\{/);
  expect(STYLES).toMatch(
    /input:not\(\[type="checkbox"\]\):not\(\[type="radio"\]\):read-only,\s*input:not\(\[type="checkbox"\]\):not\(\[type="radio"\]\)\[readonly\]\s*\{[^}]*cursor:\s*not-allowed;/s,
  );
});

it("keeps bulk execution configuration sections visually separated", () => {
  expect(STYLES).toMatch(
    /\.execute-dialog-panel\.wide\s+\.modal-body\s*>\s*\.plan-run-section\s*\+\s*\.plan-run-section\s*\{[^}]*margin-top:\s*1\.25rem;/s,
  );
  expect(STYLES).toMatch(
    /\.execute-dialog-panel\.wide\s+\.modal-body\s*>\s*\.execution-config-fields\s*\{[^}]*margin-top:\s*1\.25rem;/s,
  );
});

function makeCase(overrides: Partial<TestCase>): TestCase {
  const item = {
    id: "case_alpha",
    title: "示例用例",
    module: "登录",
    content_markdown: "## 执行任务\n打开",
    tags: ["P0", "smoke"],
    automation_level: "auto" as const,
    execution_count: 0,
    pass_count: 0,
    fail_count: 0,
    last_executed_at: null,
    bound_plan_count: 0,
    created_by: "admin",
    created_at: "2026-07-28T03:00:00Z",
    updated_at: "2026-07-28T03:00:00Z",
    ...overrides,
  };
  return {
    ...item,
    bound_plan_count: item.bound_plan_count ?? 0,
  };
}

function listOf(items: TestCase[]): TestCaseListResponse {
  return { total: items.length, page: 1, page_size: 10, items };
}

it("never derives case KPIs from a filtered list", async () => {
  server.use(
    http.get("/api/v1/cases/stats", async () => {
      await delay("infinite");
      return HttpResponse.json({});
    }),
    http.get("/api/v1/cases/tags", () =>
      HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases/modules", () =>
      HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases", ({ request }) => {
      const filtered = Boolean(
        new URL(request.url).searchParams.get("search"),
      );
      return HttpResponse.json({
        items: filtered ? [] : [makeCase({ id: "case_global" })],
        total: filtered ? 0 : 7,
        page: 1,
        page_size: 10,
      });
    }),
  );

  renderApp("/cases");
  await screen.findByRole("link", { name: "示例用例" });
  expect(screen.getByTestId("case-metric-total")).toHaveTextContent("0");
  await user.type(
    screen.getByRole("searchbox", { name: "搜索用例" }),
    "missing",
  );

  expect(await screen.findByText(
    "无匹配结果，请调整搜索条件或表头筛选",
  )).toBeVisible();
  expect(screen.getByTestId("case-metric-total")).toHaveTextContent("0");
  expect(screen.queryByRole("link", { name: "创建第一个用例" }))
    .not.toBeInTheDocument();
});

it("filters by clicking a tag in the case row and drops the automation column", async () => {
  const seenTags: string[] = [];
  const seenModules: string[] = [];
  server.use(
    http.get("/api/v1/cases/stats", () =>
      HttpResponse.json({
        total: 3,
        auto_count: 3,
        today_executions: 2,
        total_executions: 22,
        pass_rate: 73,
      })),
    http.get("/api/v1/cases", ({ request }) => {
      const url = new URL(request.url);
      const tag = url.searchParams.get("tag");
      const module = url.searchParams.get("module");
      seenTags.push(tag ?? "");
      seenModules.push(module ?? "");
      if (tag === "smoke") {
        return HttpResponse.json(listOf([makeCase({ id: "case_alpha", title: "示例用例" })]));
      }
      return HttpResponse.json(
        listOf([
          makeCase({ id: "case_alpha", title: "示例用例", tags: ["P0", "smoke"] }),
          makeCase({ id: "case_beta", title: "另一个用例", tags: ["P0"] }),
        ]),
      );
    }),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0", "smoke"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["登录"] })),
  );

  renderApp("/cases");

  await screen.findByRole("link", { name: "示例用例" });
  // The automation column header should be gone.
  expect(screen.queryByRole("columnheader", { name: "自动化" })).not.toBeInTheDocument();
  expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
    "用例ID",
    "用例名称",
    "模块",
    "标签",
    "关联计划",
    "执行次数",
    "通过率",
    "最近执行",
    "创建人",
    "更新时间",
    "操作",
  ]);
  expect(screen.getByRole("table")).toHaveClass("task-table");
  expect(screen.getByText("第 1 / 1 页")).toBeVisible();
  expect(screen.getByRole("button", { name: "上一页" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled();
  expect(screen.queryByRole("combobox", { name: "每页条数" })).not.toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "用例ID" }))
    .toHaveClass("case-sticky-header");
  expect(screen.getByTestId("case-metric-total").closest(".metric-grid"))
    .toHaveClass("case-metric-grid");
  expect(screen.queryByText("可自动化")).not.toBeInTheDocument();
  expect(screen.queryByText(/自动化率/)).not.toBeInTheDocument();
  expect(screen.getByTestId("case-metric-today")).toHaveTextContent("今日执行");
  expect(screen.getByTestId("case-metric-today")).toHaveTextContent("2");
  expect(screen.getByTestId("case-metric-today")).toHaveTextContent("中国时区今日");
  expect(document.querySelector(".cases-page .page-content"))
    .toHaveClass("case-content-compact");
  expect(document.querySelector(".case-action-message")).not.toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "操作" }))
    .toHaveClass("case-actions-cell");

  const row = screen.getByRole("link", { name: "示例用例" }).closest("tr") as HTMLElement;
  expect(within(row).getByRole("link", { name: "示例用例" }))
    .toHaveClass("case-name-link-neutral");
  expect(within(row).getByText("admin")).toHaveClass("case-owner-text");
  expect(within(row).getAllByRole("cell").at(-1)).toHaveClass("case-actions-cell");
  expect(within(row).getByLabelText("执行用例").closest(".row-actions"))
    .toHaveClass("case-row-actions");
  const p0Tag = within(row).getByRole("button", { name: "P0" });
  const smokeTag = within(row).getByRole("button", { name: "smoke" });
  expect(p0Tag.className).toMatch(/tag-tone-\d/);
  expect(smokeTag.className).toMatch(/tag-tone-\d/);
  expect(p0Tag.className).not.toBe(smokeTag.className);

  await user.click(screen.getByRole("combobox", { name: "模块筛选" }));
  await user.click(screen.getByRole("option", { name: "登录" }));
  await waitFor(() => expect(seenModules).toContain("登录"));

  // Click the "smoke" tag button inside the first row.
  const filteredRow = screen.getByRole("link", { name: "示例用例" }).closest("tr") as HTMLElement;
  await user.click(within(filteredRow).getByRole("button", { name: "smoke" }));

  await waitFor(() => expect(seenTags).toContain("smoke"));
});

it("keeps long case names compact while exposing the full name on hover and focus", async () => {
  const longTitle = "完整链路验证-这是一个非常长的用例名称用于验证悬浮时可以查看完整标题且不挤压模块列";
  server.use(
    http.get("/api/v1/cases/stats", () =>
      HttpResponse.json({
        total: 1,
        auto_count: 1,
        today_executions: 0,
        total_executions: 0,
        pass_rate: 0,
      })),
    http.get("/api/v1/cases", () =>
      HttpResponse.json(listOf([makeCase({ id: "case_long_name", title: longTitle, module: "E2E" })]))),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["E2E"] })),
  );

  renderApp("/cases");

  const link = await screen.findByRole("link", { name: longTitle });
  const wrapper = link.closest(".case-name-wrapper") as HTMLElement;
  expect(wrapper).toHaveAttribute("data-full-title", longTitle);
  expect(link).not.toHaveAttribute("title");
  expect(STYLES).toMatch(
    /\.case-name-wrapper\s*\{[^}]*max-width:\s*280px;[^}]*position:\s*relative/s,
  );
  expect(STYLES).toMatch(
    /\.case-name-wrapper::after\s*\{[^}]*content:\s*attr\(data-full-title\)/s,
  );
  expect(STYLES).toMatch(
    /\.case-name-wrapper::after\s*\{[^}]*bottom:\s*calc\(100% \+ 6px\)/s,
  );
  expect(STYLES).not.toMatch(
    /\.case-name-wrapper::after\s*\{[^}]*top:\s*calc\(100% \+ 6px\)/s,
  );
  expect(STYLES).toMatch(
    /\.case-name-wrapper::after\s*\{[^}]*background:\s*var\(--mua-card\);[^}]*color:\s*var\(--mua-neutral-800\)/s,
  );
  expect(STYLES).not.toMatch(
    /\.case-name-wrapper::after\s*\{[^}]*background:\s*var\(--mua-neutral-900\)/s,
  );
  expect(STYLES).toMatch(
    /\.case-name-wrapper:hover::after,[\s\S]*?\.case-name-wrapper:focus-within::after\s*\{[^}]*opacity:\s*1/s,
  );
  expect(STYLES).toMatch(
    /\.case-name-link\s*\{[^}]*max-width:\s*280px;[^}]*overflow:\s*hidden;[^}]*text-overflow:\s*ellipsis/s,
  );
});

it("uses task-list style live search and removes automation level filtering", async () => {
  const seenQueries: string[] = [];
  server.use(
    http.get("/api/v1/cases", ({ request }) => {
      seenQueries.push(new URL(request.url).search);
      return HttpResponse.json(listOf([makeCase({ id: "case_prefix", title: "打开抖音 APP" })]));
    }),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0", "smoke"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["登录"] })),
  );

  renderApp("/cases");

  const search = await screen.findByLabelText("搜索用例");
  expect(search.closest(".case-filter-search")).toHaveClass("task-search");
  expect(STYLES).toMatch(
    /\.case-filter-search\s*\{[^}]*flex:\s*0 1 280px;[^}]*max-width:\s*280px;[^}]*min-width:\s*260px;/s,
  );
  expect(screen.getByRole("combobox", { name: "标签筛选" }).closest(".single-select"))
    .not.toHaveClass("case-tag-filter");
  expect(STYLES).not.toMatch(/\.case-tag-filter \.single-select-menu/);
  expect(screen.queryByRole("button", { name: "搜索" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "清空搜索" })).not.toBeInTheDocument();
  expect(screen.queryByRole("combobox", { name: "自动化等级筛选" })).not.toBeInTheDocument();

  await user.type(search, "打开抖音");

  await waitFor(() =>
    expect(seenQueries.some((query) =>
      query.includes("search=%E6%89%93%E5%BC%80%E6%8A%96%E9%9F%B3"),
    )).toBe(true),
  );
});

it("filters cases by creator", async () => {
  const seenCreators: string[] = [];
  server.use(
    http.get("/api/v1/cases", ({ request }) => {
      const creator = new URL(request.url).searchParams.get("created_by");
      seenCreators.push(creator ?? "");
      return HttpResponse.json(listOf([
        makeCase({ id: "case_creator", title: "创建人筛选用例", created_by: creator || "admin" }),
      ]));
    }),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases/creators", () =>
      HttpResponse.json({ items: ["admin", "alice"] })),
  );

  renderApp("/cases");

  await screen.findByRole("link", { name: "创建人筛选用例" });
  await user.click(screen.getByRole("combobox", { name: "创建人筛选" }));
  await user.click(screen.getByRole("option", { name: "alice" }));

  await waitFor(() => expect(seenCreators).toContain("alice"));
  expect(screen.getByRole("combobox", { name: "创建人筛选" }))
    .toHaveTextContent("alice");
});

it("copies the full case id via the copy button", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  server.use(
    http.get("/api/v1/cases", () => HttpResponse.json(listOf([makeCase({ id: "case_copy_me" })]))),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["登录"] })),
  );

  renderApp("/cases");

  // Full id shown (not truncated placeholder).
  expect(await screen.findByText("case_copy_me")).toBeVisible();

  const row = screen.getByText("case_copy_me").closest("tr") as HTMLElement;
  await user.click(within(row).getByRole("button", { name: "复制用例ID" }));

  await waitFor(() => expect(writeText).toHaveBeenCalledWith("case_copy_me"));
});

it("shows execution count and pass rate in separate columns", async () => {
  server.use(
    http.get("/api/v1/cases", () =>
      HttpResponse.json(listOf([
        makeCase({
          id: "case_rate",
          execution_count: 4,
          pass_count: 3,
          fail_count: 1,
        }),
      ])),
    ),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["登录"] })),
  );

  renderApp("/cases");

  const row = (await screen.findByText("case_rate")).closest("tr") as HTMLElement;
  const cells = within(row).getAllByRole("cell");
  expect(cells[5]).toHaveTextContent("4");
  expect(cells[6]).toHaveTextContent("75%");
});

it("shows bound test plan count in the case list", async () => {
  server.use(
    http.get("/api/v1/cases", () =>
      HttpResponse.json(listOf([
        makeCase({ id: "case_bound", title: "有关联计划", bound_plan_count: 3 }),
        makeCase({ id: "case_unbound", title: "无关联计划", bound_plan_count: 0 }),
      ])),
    ),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["登录"] })),
  );

  renderApp("/cases");

  const boundRow = (await screen.findByRole("link", { name: "有关联计划" }))
    .closest("tr") as HTMLElement;
  const unboundRow = screen.getByRole("link", { name: "无关联计划" })
    .closest("tr") as HTMLElement;

  expect(screen.getByRole("columnheader", { name: "关联计划" })).toBeVisible();
  expect(within(boundRow).getAllByRole("cell")[4]).toHaveTextContent("3");
  expect(within(unboundRow).getAllByRole("cell")[4]).toHaveTextContent("-");
});

it("copies a case and refreshes the list", async () => {
  let items = [makeCase({ id: "case_source", title: "登录核心链路" })];
  server.use(
    http.get("/api/v1/cases", () => HttpResponse.json(listOf(items))),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["登录"] })),
    http.post("/api/v1/cases/case_source/copy", ({ request }) => {
      expectCsrf(request);
      const copied = makeCase({
        ...items[0],
        id: "case_copy",
        title: "登录核心链路 副本",
      });
      items = [items[0], copied];
      return HttpResponse.json(copied, { status: 201 });
    }),
  );

  renderApp("/cases");

  const row = (await screen.findByText("case_source")).closest("tr") as HTMLElement;
  await user.click(within(row).getByRole("button", { name: "复制用例" }));

  expect(await screen.findByRole("link", { name: "登录核心链路 副本" })).toBeVisible();
});

it("confirms deletion before removing a case", async () => {
  let items = [makeCase({ id: "case_delete", title: "待删除用例" })];
  let deleteRequests = 0;
  server.use(
    http.get("/api/v1/cases", () => HttpResponse.json(listOf(items))),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["登录"] })),
    http.delete("/api/v1/cases/case_delete", ({ request }) => {
      expectCsrf(request);
      deleteRequests += 1;
      items = [];
      return new HttpResponse(null, { status: 204 });
    }),
  );

  renderApp("/cases");

  const row = (await screen.findByText("case_delete")).closest("tr") as HTMLElement;
  await user.click(within(row).getByRole("button", { name: "删除用例" }));
  expect(screen.getByRole("dialog", { name: "删除用例" })).toBeVisible();
  expect(deleteRequests).toBe(0);

  await user.click(screen.getByRole("button", { name: "确认删除" }));

  await waitFor(() => expect(deleteRequests).toBe(1));
  await waitFor(() => expect(screen.queryByText("case_delete")).not.toBeInTheDocument());
});

it("explains when a single case delete is blocked by a test plan", async () => {
  const items = [makeCase({ id: "case_bound", title: "已绑定计划用例" })];
  server.use(
    http.get("/api/v1/cases", () => HttpResponse.json(listOf(items))),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["登录"] })),
    http.delete("/api/v1/cases/case_bound", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json(
        {
          error: {
            code: "case_has_test_plans",
            message: "Test case is bound to an active test plan",
          },
        },
        { status: 409 },
      );
    }),
  );

  renderApp("/cases");

  const row = (await screen.findByText("case_bound")).closest("tr") as HTMLElement;
  await user.click(within(row).getByRole("button", { name: "删除用例" }));
  await user.click(screen.getByRole("button", { name: "确认删除" }));

  const dialog = await screen.findByRole("dialog", { name: "删除用例" });
  expect(within(dialog).getByRole("alert")).toHaveTextContent(
    "该用例已绑定测试计划，请先从测试计划中移除后再删除。",
  );
});

it("supports bulk action bar, export and delete confirmation", async () => {
  let items = [
    makeCase({ id: "case_bulk_a", title: "批量用例 A", tags: ["P0"] }),
    makeCase({ id: "case_bulk_b", title: "批量用例 B", tags: ["smoke"] }),
    makeCase({ id: "case_bulk_c", title: "批量用例 C", tags: ["reg"] }),
  ];
  const createObjectURL = vi.fn(() => "blob:case-export");
  const revokeObjectURL = vi.fn();
  const clickAnchor = vi
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
  let deleteRequests = 0;
  server.use(
    http.get("/api/v1/cases", () => HttpResponse.json(listOf(items))),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0", "smoke", "reg"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["登录"] })),
    http.post("/api/v1/cases/batch-delete", async ({ request }) => {
      expectCsrf(request);
      deleteRequests += 1;
      const payload = await request.json() as { case_ids: string[] };
      items = items.filter((item) => !payload.case_ids.includes(item.id));
      return HttpResponse.json({
        deleted_count: payload.case_ids.length,
        failed_count: 0,
        items: payload.case_ids.map((caseId) => ({
          case_id: caseId,
          status: "deleted",
          code: null,
          message: null,
        })),
      });
    }),
  );

  renderApp("/cases");

  await screen.findByRole("link", { name: "批量用例 A" });
  expect(screen.queryByText("已选择 2 个用例")).not.toBeInTheDocument();

  await user.click(screen.getByRole("checkbox", { name: /批量用例 A/ }));
  await user.click(screen.getByRole("checkbox", { name: /批量用例 B/ }));

  expect(screen.getByText("已选择 2 个用例")).toBeVisible();
  expect(screen.getByRole("button", { name: "批量执行" })).toBeVisible();
  expect(screen.getByRole("button", { name: "批量导出" })).toBeVisible();
  expect(screen.getByRole("button", { name: "批量删除" })).toBeVisible();

  await user.click(screen.getByRole("button", { name: "批量导出" }));
  expect(createObjectURL).toHaveBeenCalled();
  expect(clickAnchor).toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: "批量删除" }));
  expect(screen.getByRole("dialog", { name: "批量删除用例" })).toBeVisible();
  expect(screen.getByText("将尝试删除已选择的 2 个用例。")).toBeVisible();
  expect(screen.getByText(/排队中、运行中或正在生成脚本/)).toBeVisible();
  expect(screen.getByText(/删除后用例将从用例库和测试计划候选列表中隐藏/)).toBeVisible();
  expect(deleteRequests).toBe(0);
  await user.click(screen.getByRole("button", { name: "确认删除" }));

  await waitFor(() => expect(deleteRequests).toBe(1));
  await waitFor(() => expect(screen.queryByText("case_bulk_a")).not.toBeInTheDocument());
});

it("keeps bulk delete failures inside the confirmation dialog", async () => {
  const items = [
    makeCase({ id: "case_bulk_blocked", title: "批量删除失败用例", tags: ["P0"] }),
  ];
  server.use(
    http.get("/api/v1/cases", () => HttpResponse.json(listOf(items))),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["登录"] })),
    http.post("/api/v1/cases/batch-delete", async ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json({
        deleted_count: 0,
        failed_count: 1,
        items: [{
          case_id: "case_bulk_blocked",
          status: "failed",
          code: "case_has_test_plans",
          message: "Test case is bound to an active test plan",
        }],
      });
    }),
  );

  renderApp("/cases");

  await screen.findByRole("link", { name: "批量删除失败用例" });
  await user.click(screen.getByRole("checkbox", { name: /批量删除失败用例/ }));
  await user.click(screen.getByRole("button", { name: "批量删除" }));
  await user.click(screen.getByRole("button", { name: "确认删除" }));

  const dialog = await screen.findByRole("dialog", { name: "批量删除用例" });
  expect(within(dialog).getByRole("alert")).toHaveTextContent(
    "部分用例删除失败：case_bulk_blocked: 已绑定测试计划",
  );
  expect(screen.queryByText("已删除 0 个用例，1 个删除失败。")).not.toBeInTheDocument();
  expect(screen.queryByText((content, element) =>
    element?.classList.contains("error-banner") === true
      && content.includes("部分用例删除失败"),
  )).not.toBeInTheDocument();
});

it("creates a task batch from selected cases", async () => {
  const items = [
    makeCase({ id: "case_batch_a", title: "批量执行 A" }),
    makeCase({ id: "case_batch_b", title: "批量执行 B" }),
  ];
  let batchPayload: unknown = null;
  server.use(
    http.get("/api/v1/cases", () => HttpResponse.json(listOf(items))),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: ["P0"] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: ["登录"] })),
    http.post("/api/v1/pod-pool/refresh", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json({
        refreshed_at: "2026-07-28T03:30:00Z",
        items: [1, 2].map((index) => ({
          product_id: "2103274899",
          pod_id: `i-online-${index}`,
          pod_name: `CUA Online ${index}`,
          pod_status_code: 2,
          stream_status: null,
          discovery_state: "active",
          local_state: "available",
          image_id: null,
          image_name: null,
          aosp_version: null,
          display_layout_id: null,
          dc_id: null,
          dc_name: null,
          isp_code: null,
          region: null,
          zone_id: null,
          config_code: null,
          config_name: null,
          config_type: null,
          server_type_code: null,
          intranet_ip: null,
          adb_address: null,
          adb_status: null,
          data_size: null,
          data_size_used: null,
          pod_created_at: null,
          last_seen_at: "2026-07-28T03:30:00Z",
          last_checked_at: "2026-07-28T03:30:01Z",
          request_id: null,
          task_id: null,
          task_status: null,
          task_scenario: null,
          eip_address: null,
        })),
      });
    }),
    http.post("/api/v1/task-batches", async ({ request }) => {
      expectCsrf(request);
      batchPayload = await request.json();
      return HttpResponse.json({
        id: "batch_bulk",
        name: "批量执行 2 个用例",
        test_type: "regression",
        selection_mode: "multi_cases",
        selection_snapshot: { case_ids: ["case_batch_a", "case_batch_b"] },
        device_strategy: "automatic",
        pod_ids: [],
        concurrency: 2,
        device_wait_timeout_seconds: 300,
        execution_status: "queued",
        verdict: null,
        created_by: "admin",
        unavailable_since: null,
        cancel_requested_at: null,
        created_at: "2026-08-07T00:00:00Z",
        started_at: null,
        finished_at: null,
        tasks: [],
      });
    }),
  );

  renderApp("/cases");

  await screen.findByRole("link", { name: "批量执行 A" });
  await user.click(screen.getByRole("checkbox", { name: /批量执行 A/ }));
  await user.click(screen.getByRole("checkbox", { name: /批量执行 B/ }));
  await user.click(screen.getByRole("button", { name: "批量执行" }));
  await user.click(await screen.findByRole("radio", { name: "指定设备" }));
  const waitInput = screen.getByLabelText("设备不可用后最大等待时间（秒）");
  await user.clear(waitInput);
  await user.type(waitInput, "90");
  await user.click(screen.getByRole("checkbox", { name: /CUA Online 1.*i-online-1/ }));
  await user.click(screen.getByRole("checkbox", { name: /CUA Online 2.*i-online-2/ }));
  await user.click(screen.getByRole("button", { name: "开始执行" }));

  await waitFor(() => expect(batchPayload).toMatchObject({
    selection_mode: "multi_cases",
    case_ids: ["case_batch_a", "case_batch_b"],
    device_strategy: "specified",
    pod_ids: ["i-online-1", "i-online-2"],
    concurrency: 2,
    device_wait_timeout_seconds: 90,
  }));
});

it("restores case filters and pagination from the URL", async () => {
  const seenQueries: string[] = [];
  server.use(
    http.get("/api/v1/cases", ({ request }) => {
      seenQueries.push(new URL(request.url).search);
      return HttpResponse.json({
        items: [makeCase({ id: "case_deep_link" })],
        total: 11,
        page: 2,
        page_size: 10,
      });
    }),
    http.get("/api/v1/cases/tags", () =>
      HttpResponse.json({ items: ["smoke"] })),
    http.get("/api/v1/cases/modules", () =>
      HttpResponse.json({ items: ["登录"] })),
    http.get("/api/v1/cases/creators", () =>
      HttpResponse.json({ items: ["admin", "alice"] })),
  );

  renderApp("/cases?page=2&search=示例&module=登录&tag=smoke&created_by=alice");

  expect(await screen.findByText("case_deep_link")).toBeVisible();
  expect(screen.getByLabelText("搜索用例")).toHaveValue("示例");
  expect(screen.getByRole("combobox", { name: "模块筛选" })).toHaveTextContent("登录");
  expect(screen.getByRole("combobox", { name: "标签筛选" })).toHaveTextContent("smoke");
  expect(screen.getByRole("combobox", { name: "创建人筛选" })).toHaveTextContent("alice");
  expect(screen.queryByRole("combobox", { name: "自动化等级筛选" })).not.toBeInTheDocument();
  expect(screen.getByText("第 2 / 2 页")).toBeVisible();
  expect(seenQueries.some((query) =>
    query.includes("page=2")
    && query.includes("search=%E7%A4%BA%E4%BE%8B")
    && query.includes("module=%E7%99%BB%E5%BD%95")
    && query.includes("tag=smoke")
    && query.includes("created_by=alice"),
  )).toBe(true);
  expect(seenQueries.every((query) => !query.includes("automation_level"))).toBe(true);
});
