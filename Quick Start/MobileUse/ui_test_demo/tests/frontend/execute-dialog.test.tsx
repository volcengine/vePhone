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
      pod_status_code: 1,
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
    await user.click(screen.getByRole("radio", { name: "重置设备" }));
    await user.type(screen.getByLabelText("ThreadId"), "thread-dialog");
    fireEvent.change(screen.getByLabelText("最大步骤数 MaxStep"), { target: { value: "123" } });
    fireEvent.change(screen.getByLabelText("任务超时 Timeout（秒）"), { target: { value: "456" } });
    fireEvent.change(screen.getByLabelText("重试次数 RetryLimit"), { target: { value: "7" } });
    await user.click(screen.getByLabelText(/UseBase64Screenshot/));
    await user.click(screen.getByLabelText(/IsScreenRecord/));
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
      '{"X-Env":"test","X-Request-Source":"mua"}',
    );
    fireEvent.change(headers, { target: { value: '{"X-Env":"test"}' } });
    await user.type(screen.getByLabelText("GpsInfo"), "116.397128,39.916527,50,0,0,10");
    await user.click(screen.getByRole("button", { name: /开始执行/ }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        agent_config_mode: "custom",
        timeout_seconds: 456,
        agent_options: expect.objectContaining({
          device_prepare_action: "reset",
          thread_id: "thread-dialog",
          use_base64_screenshot: true,
          max_step: 123,
          timeout_seconds: 456,
          callback_info: { url: "https://callback.example.com" },
          output_schema: '{"type":"object"}',
          retry_limit: 7,
          system_prompt: "custom system prompt",
          tos_bucket: "custom-bucket",
          tos_endpoint: "tos-s3-cn-beijing.volces.com",
          tos_region: "cn-beijing",
          screen_record: true,
          mcp_json: '{"mcpServers":{"amap":{"url":"https://mcp.example.com"}}}',
          request_headers: { "X-Env": "test" },
          gps_info: "116.397128,39.916527,50,0,0,10",
        }),
      }),
    );
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
    expect(screen.queryByText("设备启动前处理")).not.toBeInTheDocument();
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
    expect(screen.queryByText("设备启动前处理")).not.toBeInTheDocument();
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
