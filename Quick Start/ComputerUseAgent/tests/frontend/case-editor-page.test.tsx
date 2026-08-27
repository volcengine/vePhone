import { screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

import type { CaseBoundTestPlanListResponse, TestCase } from "../../web/api/types";
import { expectCsrf, renderApp, server, user } from "./setup";

const STYLES = readFileSync("web/styles.css", "utf8");

function savedCase(overrides: Partial<TestCase> = {}): TestCase {
  return {
    id: "case_saved",
    title: "新建链路",
    module: "登录",
    content_markdown: "## 执行任务\n打开首页",
    tags: [],
    automation_level: "auto",
    execution_count: 0,
    pass_count: 0,
    fail_count: 0,
    last_executed_at: null,
    created_by: "admin",
    created_at: "2026-07-28T03:00:00Z",
    updated_at: "2026-07-28T03:00:00Z",
    ...overrides,
  };
}

function boundPlans(): CaseBoundTestPlanListResponse {
  return {
    total: 2,
    page: 1,
    page_size: 5,
    items: [
      {
        id: "plan_idle",
        name: "冒烟计划",
        test_type: "regression",
        case_count: 3,
        has_active_execution: false,
        created_by: "admin",
        updated_at: "2026-08-07T00:00:00Z",
      },
      {
        id: "plan_running",
        name: "运行中计划",
        test_type: "new_feature",
        case_count: 2,
        has_active_execution: true,
        created_by: "admin",
        updated_at: "2026-08-07T00:00:00Z",
      },
    ],
  };
}

it("新建用例页不展示自动化等级并按默认自动执行保存", async () => {
  let submitted: unknown;
  server.use(
    http.get("/api/v1/cases/template", () =>
      HttpResponse.json({ template: "## 执行任务\n打开首页" })),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: [] })),
    http.post("/api/v1/cases", async ({ request }) => {
      expectCsrf(request);
      submitted = await request.json();
      return HttpResponse.json(savedCase(), { status: 201 });
    }),
    http.get("/api/v1/cases/case_saved", () => HttpResponse.json(savedCase())),
    http.get("/api/v1/cases/case_saved/tasks", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
  );

  renderApp("/cases/new");

  expect(await screen.findByRole("heading", { name: "新建用例" })).toBeVisible();
  expect(screen.queryByText("自动化等级")).not.toBeInTheDocument();
  expect(screen.queryByRole("combobox", { name: "自动化等级" })).not.toBeInTheDocument();
  expect(screen.getByText("所属模块").closest(".case-metadata-row")).toBeInTheDocument();
  expect(STYLES).toMatch(
    /\.case-metadata-row\s*\{[^}]*margin-bottom:\s*1\.25rem;/s,
  );

  await user.type(
    screen.getByPlaceholderText("例如：打开抖音APP查看3个视频"),
    "新建链路",
  );
  await user.type(
    screen.getByPlaceholderText("例如：登录注册、首页、商品"),
    "登录",
  );
  await user.click(screen.getByRole("button", { name: "保存" }));

  await waitFor(() =>
    expect(submitted).toEqual(
      expect.objectContaining({
        title: "新建链路",
        module: "登录",
        automation_level: "auto",
      }),
    ),
  );
});

it("shows bound test plans and removes the case from an idle plan", async () => {
  let plans = boundPlans();
  let removed = false;
  server.use(
    http.get("/api/v1/cases/case_saved", () => HttpResponse.json(savedCase())),
    http.get("/api/v1/cases/case_saved/tasks", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
    http.get("/api/v1/cases/case_saved/test-plans", () =>
      HttpResponse.json(plans)),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: [] })),
    http.delete("/api/v1/test-plans/plan_idle/cases/case_saved", ({ request }) => {
      expectCsrf(request);
      removed = true;
      plans = {
        total: 1,
        page: 1,
        page_size: 5,
        items: plans.items.filter((item) => item.id !== "plan_idle"),
      };
      return new HttpResponse(null, { status: 204 });
    }),
  );

  renderApp("/cases/case_saved/edit");

  expect(await screen.findByRole("heading", { name: "编辑用例" })).toBeVisible();
  const section = await screen.findByLabelText("已绑定测试计划");
  expect(within(section).getByText("该用例被 2 个有效测试计划引用。")).toBeVisible();
  expect(within(section).getByText("冒烟计划")).toBeVisible();
  expect(within(section).getByText("运行中计划")).toBeVisible();
  expect(within(section).getByRole("button", { name: "移除 运行中计划" })).toBeDisabled();

  await user.click(within(section).getByRole("button", { name: "移除 冒烟计划" }));
  expect(screen.getByRole("dialog", { name: "从测试计划中移除用例" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "确认移除" }));

  await waitFor(() => expect(removed).toBe(true));
  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: "从测试计划中移除用例" }))
      .not.toBeInTheDocument(),
  );
  expect(await screen.findByText("该用例被 1 个有效测试计划引用。")).toBeVisible();
  expect(screen.queryByText("冒烟计划")).not.toBeInTheDocument();
});

it("paginates bound test plans", async () => {
  const requests: URL[] = [];
  function pageItems(page: number) {
    const start = (page - 1) * 5;
    return Array.from({ length: page === 1 ? 5 : 2 }, (_, index) => {
      const number = start + index + 1;
      return {
        id: `plan_${number}`,
        name: `分页计划 ${number}`,
        test_type: "regression" as const,
        case_count: number,
        has_active_execution: false,
        created_by: "admin",
        updated_at: "2026-08-07T00:00:00Z",
      };
    });
  }
  server.use(
    http.get("/api/v1/cases/case_saved", () => HttpResponse.json(savedCase())),
    http.get("/api/v1/cases/case_saved/tasks", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
    http.get("/api/v1/cases/case_saved/test-plans", ({ request }) => {
      const url = new URL(request.url);
      requests.push(url);
      const page = Number(url.searchParams.get("page") ?? "1");
      return HttpResponse.json({
        total: 7,
        page,
        page_size: 5,
        items: pageItems(page),
      });
    }),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: [] })),
  );

  renderApp("/cases/case_saved/edit");

  const section = await screen.findByLabelText("已绑定测试计划");
  expect(within(section).getByText("分页计划 1")).toBeVisible();
  expect(within(section).queryByText("分页计划 6")).not.toBeInTheDocument();
  expect(requests.at(-1)?.searchParams.get("page")).toBe("1");
  expect(requests.at(-1)?.searchParams.get("page_size")).toBe("5");

  await user.click(within(section).getByRole("button", { name: "下一页" }));

  await waitFor(() => expect(requests.at(-1)?.searchParams.get("page")).toBe("2"));
  expect(await within(section).findByText("分页计划 6")).toBeVisible();
});

it("opens the default execution config dialog immediately when enabling it", async () => {
  server.use(
    http.get("/api/v1/cases/case_saved", () => HttpResponse.json(savedCase())),
    http.get("/api/v1/cases/case_saved/tasks", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 })),
    http.get("/api/v1/cases/case_saved/test-plans", () =>
      HttpResponse.json({ total: 0, page: 1, page_size: 5, items: [] })),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: [] })),
  );

  renderApp("/cases/case_saved/edit");

  expect(await screen.findByRole("heading", { name: "编辑用例" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "启用配置" }));

  const dialog = await screen.findByRole("dialog", {
    name: "编辑用例默认执行配置",
  });
  expect(dialog).toBeVisible();
  expect(within(dialog).getByText("运行控制")).toBeVisible();
});
