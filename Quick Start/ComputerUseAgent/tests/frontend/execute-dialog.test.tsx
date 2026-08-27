import { fireEvent, screen, within } from "@testing-library/react";
import { render } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";

import type { PodPoolResponse } from "../../web/api/types";
import { ExecuteDialog } from "../../web/components/execute-dialog";
import { expectCsrf, server, user } from "./setup";

const STYLES = readFileSync("web/styles.css", "utf8");

const basePod = {
  stream_status: null,
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
  request_id: null,
  eip_address: null,
};

const refreshedPool: PodPoolResponse = {
  refreshed_at: "2026-07-28T03:30:00Z",
  items: [
    {
      ...basePod,
      product_id: "product-alpha",
      pod_id: "pod-fresh",
      pod_name: "Fresh Phone",
      pod_status_code: 2,
      discovery_state: "active",
      local_state: "available",
      last_seen_at: "2026-07-28T03:30:00Z",
      last_checked_at: "2026-07-28T03:30:01Z",
      task_id: null,
      task_status: null,
      task_scenario: null,
    },
  ],
};

const noOnlinePool: PodPoolResponse = {
  refreshed_at: "2026-07-28T03:30:00Z",
  items: [
    {
      ...refreshedPool.items[0],
      pod_id: "pod-abnormal",
      pod_name: "Abnormal CUA Node",
      pod_status_code: 4,
      local_state: "unavailable",
      task_id: null,
      task_status: null,
    },
  ],
};

describe("ExecuteDialog", () => {
  it("执行配置不再单独展示外层超时时间", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
    );

    render(
      <ExecuteDialog
        open
        caseTitle="打开抖音APP"
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    await screen.findByText("Fresh Phone");
    expect(screen.queryByLabelText("执行超时时间")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("设备不可用后最大等待时间（秒）"))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "执行超时时间" }))
      .not.toBeInTheDocument();
  });

  it("提交期间禁止通过关闭按钮或遮罩关闭", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
    );
    const onClose = vi.fn();

    render(
      <ExecuteDialog
        open
        caseTitle="打开抖音APP"
        onClose={onClose}
        onConfirm={vi.fn()}
        isPending
      />,
    );

    const dialog = screen.getByRole("dialog", { name: "执行配置" });
    const closeButton = screen.getByRole("button", { name: "关闭" });
    expect(closeButton).toBeDisabled();

    fireEvent.click(closeButton);
    fireEvent.click(dialog.parentElement as HTMLElement);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("打开时刷新设备池并展示刷新后的空闲设备", async () => {
    let refreshRequests = 0;
    let cachedListRequests = 0;
    server.use(
      http.get("/api/v1/pod-pool", () => {
        cachedListRequests += 1;
        return HttpResponse.json({ items: [], refreshed_at: null });
      }),
      http.post("/api/v1/pod-pool/refresh", ({ request }) => {
        expectCsrf(request);
        refreshRequests += 1;
        return HttpResponse.json(refreshedPool);
      }),
    );

    render(
      <ExecuteDialog
        open
        caseTitle="打开抖音APP"
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    const targetSelect = screen.getAllByRole("combobox")[0];
    await screen.findByText("暂无空闲设备");
    expect(within(targetSelect).getByRole("option", { name: /Fresh Phone/ })).toBeVisible();
    expect(refreshRequests).toBe(1);
    expect(cachedListRequests).toBe(0);
  });

  it("自动分配无已在线 CUA 节点时阻止提交", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(noOnlinePool)),
    );
    const onConfirm = vi.fn();

    render(
      <ExecuteDialog
        open
        caseTitle="打开抖音APP"
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    await screen.findByText("暂无空闲设备");
    await user.click(screen.getByRole("button", { name: /开始执行/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "当前没有可用的已在线 CUA 节点，请检查设备池状态或稍后重试。",
    );
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("自定义配置会解析为 agent_options", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
    );
    const onConfirm = vi.fn();

    render(
      <ExecuteDialog
        open
        caseTitle="打开抖音APP"
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    await screen.findByText("Fresh Phone");
    await user.click(screen.getByRole("radio", { name: "自定义本次执行配置" }));
    await user.type(screen.getByLabelText("ThreadId"), "thread-dialog");
    fireEvent.change(screen.getByLabelText("最大步骤数 MaxStep"), { target: { value: "123" } });
    fireEvent.change(screen.getByLabelText("任务超时 Timeout（秒）"), { target: { value: "456" } });
    fireEvent.change(screen.getByLabelText("重试次数 RetryLimit"), { target: { value: "7" } });
    expect(screen.queryByLabelText(/UseBase64Screenshot/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/IsScreenRecord/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("GpsInfo")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("TosBucket"), "custom-bucket");
    await user.type(screen.getByLabelText("TosEndpoint"), "tos-s3-cn-beijing.volces.com");
    await user.clear(screen.getByLabelText("TosRegion"));
    await user.type(screen.getByLabelText("TosRegion"), "cn-beijing");
    await user.type(screen.getByLabelText("SystemPrompt"), "custom system prompt");
    fireEvent.change(screen.getByLabelText("CallbackInfo（JSON 对象）"), { target: { value: '{"url":"https://callback.example.com"}' } });
    fireEvent.change(screen.getByLabelText("OutputSchema（JSON 字符串）"), { target: { value: '{"type":"object"}' } });
    fireEvent.change(screen.getByLabelText("McpJson（JSON 字符串）"), { target: { value: '{"mcpServers":{"amap":{"url":"https://mcp.example.com"}}}' } });
    const headers = screen.getByLabelText("请求 Header（JSON 对象）");
    expect(headers).toHaveAttribute(
      "placeholder",
      '{"X-Env":"test","X-Request-Source":"cua"}',
    );
    fireEvent.change(headers, { target: { value: '{"X-Env":"test"}' } });
    await user.click(screen.getByRole("button", { name: /开始执行/ }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        agent_config_mode: "custom",
        timeout_seconds: 456,
        agent_options: expect.objectContaining({
          thread_id: "thread-dialog",
          max_step: 123,
          timeout_seconds: 456,
          callback_info: { url: "https://callback.example.com" },
          output_schema: '{"type":"object"}',
          retry_limit: 7,
          system_prompt: "custom system prompt",
          tos_bucket: "custom-bucket",
          tos_endpoint: "tos-s3-cn-beijing.volces.com",
          tos_region: "cn-beijing",
          mcp_json: '{"mcpServers":{"amap":{"url":"https://mcp.example.com"}}}',
          request_headers: { "X-Env": "test" },
        }),
      }),
    );
    expect(onConfirm.mock.calls[0][0].agent_options).not.toHaveProperty("use_base64_screenshot");
    expect(onConfirm.mock.calls[0][0].agent_options).not.toHaveProperty("screen_record");
    expect(onConfirm.mock.calls[0][0].agent_options).not.toHaveProperty("gps_info");
  });

  it("拒绝保留请求 Header", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
    );
    const onConfirm = vi.fn();

    render(
      <ExecuteDialog
        open
        caseTitle="打开抖音APP"
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    await screen.findByText("Fresh Phone");
    await user.click(screen.getByRole("radio", { name: "自定义本次执行配置" }));
    fireEvent.change(screen.getByLabelText("请求 Header（JSON 对象）"), {
      target: { value: '{"Authorization":"Bearer blocked"}' },
    });
    await user.click(screen.getByRole("button", { name: /开始执行/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "请求 Header 包含不允许覆盖的保留字段：Authorization",
    );
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("允许时展示用例默认配置选项并提交 case_default 模式", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
    );
    const onConfirm = vi.fn();

    render(
      <ExecuteDialog
        open
        caseTitle="打开抖音APP"
        onClose={vi.fn()}
        onConfirm={onConfirm}
        allowCaseDefault
      />,
    );

    await screen.findByText("Fresh Phone");
    await user.click(screen.getByRole("radio", { name: "用例默认配置" }));
    await user.click(screen.getByRole("button", { name: /开始执行/ }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        agent_config_mode: "case_default",
        timeout_seconds: null,
        agent_options: null,
      }),
    );
  });

  it("默认使用全局配置并展示只读摘要而非空白", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
    );

    render(
      <ExecuteDialog
        open
        caseTitle="打开抖音APP"
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    await screen.findByText("Fresh Phone");
    const globalRadio = screen.getByRole("radio", { name: "使用全局配置" });
    expect(globalRadio).toBeChecked();
    expect(screen.getByText("将套用的全局配置")).toBeVisible();
    expect(screen.queryByLabelText("最大步骤数 MaxStep")).not.toBeInTheDocument();
  });

  it("代理任务配置用分段控件而非下拉承载", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
    );

    render(
      <ExecuteDialog
        open
        caseTitle="打开抖音APP"
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    await screen.findByText("Fresh Phone");
    expect(
      screen.queryByRole("combobox", { name: "代理任务配置" }),
    ).not.toBeInTheDocument();
    const group = screen.getByRole("radiogroup", { name: "代理任务配置" });
    expect(within(group).getByRole("radio", { name: "使用全局配置" })).toBeVisible();
    expect(
      within(group).getByRole("radio", { name: "自定义本次执行配置" }),
    ).toBeVisible();
  });

  it("未勾选的开关不显示勾号", () => {
    expect(STYLES).toMatch(
      /\.checkbox-row \.checkbox-box::after\s*\{[^}]*content:\s*""\s*;/s,
    );
    expect(STYLES).toMatch(
      /\.checkbox-row input\[type="checkbox"\]:checked \+ \.checkbox-box::after\s*\{[^}]*content:\s*"[^"]+"/s,
    );
  });
});
