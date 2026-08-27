import { screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, it } from "vitest";

import { renderApp, server } from "./setup";

it("renders task creation time in UTC+8 with a stable format", async () => {
  server.use(
    http.get("/api/v1/tasks", () =>
      HttpResponse.json({
        items: [
          {
            id: "task_timezone",
            case_id: "case_1",
            script_version_id: null,
            prompt_snapshot: null,
            result_summary: null,
            result_evidence: [],
            runner_type: "mobile_use",
            scenario: "时区验证",
            created_by: "admin",
            execution_status: "result_ready",
            verdict: "pass",
            failure_type: null,
            version: 1,
            created_at: "2026-07-28T03:35:31Z",
            started_at: "2026-07-28T03:35:31Z",
            finished_at: "2026-07-28T03:38:32Z",
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    ),
  );

  renderApp("/tasks");

  expect(await screen.findByText("2026-07-28 11:35:31")).toBeVisible();
  expect(screen.getByText("执行对象")).toBeVisible();
  expect(screen.getByText("来源")).toBeVisible();
  expect(screen.getByText("耗时")).toBeVisible();
  expect(screen.getByText("操作者")).toBeVisible();
  expect(screen.getAllByText("admin")).toHaveLength(2);
  expect(screen.getByText("3 分 1 秒")).toBeVisible();
  expect(screen.queryByRole("button", { name: "取消任务" })).not.toBeInTheDocument();
});
