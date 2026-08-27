import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, it } from "vitest";

import type { PodPoolResponse, TestCaseListResponse } from "../../web/api/types";
import { expectCsrf, renderApp, server, user } from "./setup";

const cases: TestCaseListResponse = {
  items: [
    {
      id: "case_a",
      title: "登录链路",
      module: "账号",
      content_markdown: "- 登录",
      tags: ["smoke"],
      automation_level: "auto",
      execution_count: 2,
      pass_count: 2,
      fail_count: 0,
      last_executed_at: null,
      created_by: "admin",
      created_at: "2026-07-29T00:00:00Z",
      updated_at: "2026-07-29T00:00:00Z",
    },
    {
      id: "case_b",
      title: "搜索链路",
      module: "搜索",
      content_markdown: "- 搜索",
      tags: ["smoke", "regression"],
      automation_level: "auto",
      execution_count: 1,
      pass_count: 1,
      fail_count: 0,
      last_executed_at: null,
      created_by: "admin",
      created_at: "2026-07-29T00:00:00Z",
      updated_at: "2026-07-29T00:00:00Z",
    },
  ],
  total: 2,
  page: 1,
  page_size: 100,
};

const pool: PodPoolResponse = {
  refreshed_at: "2026-07-29T00:00:00Z",
  items: [
    {
      product_id: "product-1",
      pod_id: "pod-a",
      pod_name: "云机 A",
      pod_status_code: 1,
      stream_status: null,
      discovery_state: "active",
      local_state: "available",
      image_id: null,
      image_name: null,
      aosp_version: "13",
      display_layout_id: null,
      dc_id: null,
      dc_name: null,
      isp_code: null,
      region: null,
      zone_id: null,
      config_code: "g2",
      config_name: "通用型",
      config_type: 1,
      server_type_code: null,
      intranet_ip: null,
      adb_address: null,
      adb_status: null,
      data_size: null,
      data_size_used: null,
      pod_created_at: null,
      last_seen_at: "2026-07-29T00:00:00Z",
      last_checked_at: null,
      request_id: null,
      task_id: null,
      task_status: null,
      task_scenario: null,
      eip_address: null,
    },
  ],
};

it("creates a multi-case batch through the four-step wizard", async () => {
  let payload: Record<string, unknown> | null = null;
  server.use(
    http.get("/api/v1/cases", () => HttpResponse.json(cases)),
    http.get("/api/v1/pod-pool", () => HttpResponse.json(pool)),
    http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(pool)),
    http.post("/api/v1/task-batches", async ({ request }) => {
      expectCsrf(request);
      payload = await request.json() as Record<string, unknown>;
      return HttpResponse.json({
        id: "batch_created",
        name: "回归测试 · 2 个用例",
        test_type: "regression",
        selection_mode: "multi_cases",
        selection_snapshot: { case_ids: ["case_a", "case_b"] },
        device_strategy: "specified",
        pod_ids: ["pod-a"],
        concurrency: 2,
        device_wait_timeout_seconds: 300,
        execution_status: "queued",
        verdict: null,
        created_by: "admin",
        unavailable_since: null,
        cancel_requested_at: null,
        created_at: "2026-07-29T00:00:00Z",
        started_at: null,
        finished_at: null,
        tasks: [],
      }, { status: 201 });
    }),
  );

  renderApp("/tasks/new?step=type");

  const stepper = await screen.findByRole("navigation", { name: "创建任务步骤" });
  expect(within(stepper).getAllByRole("listitem")).toHaveLength(4);
  await user.click(screen.getByRole("radio", { name: /回归测试/ }));
  await user.click(screen.getByRole("button", { name: "下一步：选择用例" }));

  await user.click(screen.getByRole("radio", { name: "多用例" }));
  await user.click(screen.getByRole("checkbox", { name: /登录链路/ }));
  await user.click(screen.getByRole("checkbox", { name: /搜索链路/ }));
  expect(screen.getByText("已选择 2 个用例")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "下一步：设备策略" }));

  await user.click(screen.getByRole("radio", { name: /指定设备/ }));
  await user.clear(screen.getByLabelText("批次设备并发数"));
  await user.type(screen.getByLabelText("批次设备并发数"), "2");
  await user.click(screen.getByRole("checkbox", { name: /云机 A/ }));
  await user.click(screen.getByRole("button", { name: "下一步：确认提交" }));

  expect(screen.getByText("2 个用例")).toBeVisible();
  expect(screen.getAllByText("指定设备").some((item) => item.tagName === "DD")).toBe(true);
  await user.click(screen.getByRole("button", { name: "打开执行配置" }));
  fireEvent.change(
    screen.getByLabelText("设备不可用后最大等待时间（秒）"),
    {
      target: { value: "90" },
    },
  );
  await user.click(screen.getByRole("button", { name: /开始执行/ }));

  await waitFor(() => expect(payload).not.toBeNull());
  expect(payload).toMatchObject({
    test_type: "regression",
    selection_mode: "multi_cases",
    case_ids: ["case_a", "case_b"],
    device_strategy: "specified",
    pod_ids: ["pod-a"],
    concurrency: 2,
    device_wait_timeout_seconds: 90,
  });
  expect(await screen.findByText("batch_created")).toBeVisible();
});
