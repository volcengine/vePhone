import { screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, it } from "vitest";

import { renderApp, server, user } from "./setup";

const businesses = {
  items: [
    {
      id: "biz_default",
      name: "默认业务",
      description: null,
      is_default: true,
      task_concurrency_limit: 4,
      archived_at: null,
      created_by: "system",
    },
    {
      id: "biz_pay",
      name: "支付业务",
      description: null,
      is_default: false,
      task_concurrency_limit: 4,
      archived_at: null,
      created_by: "admin",
    },
  ],
};

it("uses the business id from semantic URLs for API requests", async () => {
  const seenBusinessIds: string[] = [];
  server.use(
    http.get("/api/v1/business-spaces", () => HttpResponse.json(businesses)),
    http.get("/api/v1/tasks", ({ request }) => {
      seenBusinessIds.push(request.headers.get("X-Business-Id") ?? "");
      return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 });
    }),
  );

  renderApp("/biz/biz_pay/tasks");

  expect(await screen.findByText("执行记录")).toBeVisible();
  await waitFor(() => expect(seenBusinessIds).toContain("biz_pay"));
});

it("switches business spaces without falling back to default on refreshable URLs", async () => {
  const seenBusinessIds: string[] = [];
  server.use(
    http.get("/api/v1/business-spaces", () => HttpResponse.json(businesses)),
    http.get("/api/v1/tasks", ({ request }) => {
      seenBusinessIds.push(request.headers.get("X-Business-Id") ?? "");
      return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 });
    }),
  );

  renderApp("/biz/biz_default/tasks", { browser: true });

  await user.click(await screen.findByRole("button", { name: /当前业务：默认业务/ }));
  await user.click(await screen.findByRole("button", { name: "支付业务" }));

  await waitFor(() => {
    expect(window.location.pathname).toBe("/biz/biz_pay/tasks");
  });
  await waitFor(() => expect(seenBusinessIds).toContain("biz_pay"));
});

it("redirects legacy URLs into the last selected business space", async () => {
  localStorage.setItem("mua.currentBusinessId", "biz_pay");
  server.use(
    http.get("/api/v1/business-spaces", () => HttpResponse.json(businesses)),
    http.get("/api/v1/tasks/task_1", () =>
      HttpResponse.json({
        id: "task_1",
        case_id: "case_1",
        script_version_id: null,
        prompt_snapshot: null,
        result_summary: null,
        result_evidence: [],
        runner_type: "mock",
        scenario: "兼容路径任务",
        execution_status: "queued",
        verdict: null,
        failure_type: null,
        version: 1,
        created_at: "2026-07-24T00:00:00Z",
        started_at: null,
        finished_at: null,
        created_by: "admin",
      }),
    ),
  );

  renderApp("/tasks/task_1/trace", { browser: true });

  await waitFor(() => {
    expect(window.location.pathname).toBe("/biz/biz_pay/tasks/task_1/trace");
  });
});
