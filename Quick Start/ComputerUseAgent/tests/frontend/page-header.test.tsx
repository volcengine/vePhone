import { cleanup, screen, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, it } from "vitest";

import { renderApp, server } from "./setup";

const task = {
  id: "task_header",
  case_id: "case_header",
  script_version_id: null,
  prompt_snapshot: null,
  result_summary: null,
  result_evidence: [],
  runner_type: "mock",
  scenario: "统一头部验证",
  execution_status: "result_ready",
  verdict: "pass",
  failure_type: null,
  version: 1,
  created_at: "2026-07-29T00:00:00Z",
  started_at: "2026-07-29T00:00:00Z",
  finished_at: "2026-07-29T00:01:00Z",
  remote_thread_id: null,
  remote_status_code: null,
  remote_step_id: null,
  recording_url: null,
  result_assets: {},
  created_by: "admin",
};

function expectPageHeader({
  title,
  crumbs,
}: {
  title: string;
  crumbs: string[];
}) {
  const heading = screen.getByRole("heading", { name: title, level: 1 });
  const header = heading.closest(".page-header");
  expect(header).toHaveClass("unified-page-header");

  const breadcrumb = within(header as HTMLElement).getByLabelText("面包屑");
  for (const crumb of crumbs) {
    expect(within(breadcrumb).getByText(crumb)).toBeVisible();
  }
  expect(within(breadcrumb).getByRole("link", { name: "首页" })).toHaveAttribute(
    "href",
    "/biz/biz_default/tasks",
  );
}

it("renders the unified page header on the task list page", async () => {
  renderApp("/tasks");

  expect(await screen.findByRole("heading", { name: "执行记录" })).toBeVisible();
  expectPageHeader({
    title: "执行记录",
    crumbs: ["首页", "执行记录"],
  });
});

it("renders the unified page header on the case library page", async () => {
  server.use(
    http.get("/api/v1/cases", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 10 }),
    ),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: [] })),
  );

  renderApp("/cases");

  expect(await screen.findByRole("heading", { name: "用例库" })).toBeVisible();
  expectPageHeader({
    title: "用例库",
    crumbs: ["首页", "用例库"],
  });
});

it("renders the unified page header on the task detail page", async () => {
  server.use(
    http.get("/api/v1/tasks/task_header", () => HttpResponse.json(task)),
  );

  renderApp("/tasks/task_header");

  expect(await screen.findByRole("heading", { name: "统一头部验证 测试" })).toBeVisible();
  expectPageHeader({
    title: "统一头部验证 测试",
    crumbs: ["首页", "执行记录", "任务详情"],
  });

  cleanup();
});
