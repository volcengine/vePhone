import {
  fireEvent,
  screen,
  waitForElementToBeRemoved,
  within,
} from "@testing-library/react";
import { render } from "@testing-library/react";
import { delay, HttpResponse, http } from "msw";
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

  it("自定义配置可绑定 ScriptRun 脚本资产", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
      http.get("/api/v1/agent-run-scripts", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("search_field")).toBe("name");
        return HttpResponse.json({
          items: [
            {
              script_id: 1001,
              name: "open-app",
              description: "打开应用",
              resolution: "1920x1080",
              status: 1,
              created_at: 1785738000,
              updated_at: 1785738600,
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        });
      }),
      http.get("/api/v1/agent-run-scripts/1001", () =>
        HttpResponse.json({
          script_id: 1001,
          name: "open-app",
          description: "打开应用",
          script: "tap(0, 1)",
        }),
      ),
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
    await user.click(screen.getByRole("radio", { name: "ScriptRun 脚本" }));
    const assetPicker = await screen.findByRole("combobox", {
      name: "选择 ScriptRun 脚本资产",
    });
    expect(assetPicker).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByRole("option", { name: "open-app (#1001)" }),
    ).not.toBeInTheDocument();
    await user.click(assetPicker);
    await user.click(await screen.findByRole("option", { name: "open-app (#1001)" }));
    expect(assetPicker).toHaveAttribute("aria-expanded", "false");
    await user.click(screen.getByRole("button", { name: /开始执行/ }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        agent_config_mode: "custom",
        agent_options: expect.objectContaining({
          run_mode: "ScriptRun",
          script_id: 1001,
        }),
      }),
    );
    expect(onConfirm.mock.calls[0][0].agent_options).not.toHaveProperty("chain_id");
  });

  it("切换到 ChainRun 会清空已选 ScriptRun 资产", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
      http.get("/api/v1/agent-run-scripts", () =>
        HttpResponse.json({
          items: [
            {
              script_id: 1001,
              name: "open-app",
              description: null,
              resolution: null,
              status: 1,
              created_at: null,
              updated_at: null,
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      ),
      http.get("/api/v1/agent-run-chains", () =>
        HttpResponse.json({
          items: [
            {
              chain_id: 2001,
              name: "login-check",
              description: "登录检查",
              status: 1,
              created_at: 1785738000,
              updated_at: 1785738600,
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      ),
      http.get("/api/v1/agent-run-scripts/1001", () =>
        HttpResponse.json({
          script_id: 1001,
          name: "open-app",
          description: "打开应用",
          script: "tap(0, 1)",
        }),
      ),
      http.get("/api/v1/agent-run-chains/2001", () =>
        HttpResponse.json({
          chain_id: 2001,
          name: "login-check",
          description: "登录检查",
          nodes: [{ action: "verify-login" }],
        }),
      ),
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
    await user.click(screen.getByRole("radio", { name: "ScriptRun 脚本" }));
    await user.click(
      await screen.findByRole("combobox", { name: "选择 ScriptRun 脚本资产" }),
    );
    await user.click(await screen.findByRole("option", { name: "open-app (#1001)" }));
    await user.click(screen.getByRole("radio", { name: "ChainRun 编排" }));
    await user.click(
      await screen.findByRole("combobox", { name: "选择 ChainRun 编排资产" }),
    );
    await user.click(await screen.findByRole("option", { name: "login-check (#2001)" }));
    const chainDetailRegion = await screen.findByRole("region", {
      name: "资产详情预览",
    });
    expect(chainDetailRegion).toHaveTextContent('"action": "verify-login"');
    const chainNodeCards = within(chainDetailRegion).getAllByTestId(
      "agent-run-asset-chain-node",
    );
    expect(chainNodeCards).toHaveLength(1);
    expect(chainNodeCards[0]).toHaveTextContent("01");
    expect(chainNodeCards[0]).toHaveTextContent("verify-login");
    expect(STYLES).toMatch(
      /\.agent-run-asset-chain-node\s*\{[^}]*grid-template-columns:\s*28px minmax\(0,\s*1fr\);/s,
    );
    await user.click(screen.getByRole("button", { name: /开始执行/ }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        agent_options: expect.objectContaining({
          run_mode: "ChainRun",
          chain_id: 2001,
        }),
      }),
    );
    expect(onConfirm.mock.calls[0][0].agent_options).not.toHaveProperty("script_id");
  });

  it("执行资产列表可继续加载下一页", async () => {
    const firstPageItems = Array.from({ length: 20 }, (_, index) => ({
      script_id: 1001 + index,
      name: `script-${index + 1}`,
      description: null,
      resolution: null,
      status: 1,
      created_at: null,
      updated_at: null,
    }));
    const requestedPages: string[] = [];
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
      http.get("/api/v1/agent-run-scripts", ({ request }) => {
        const url = new URL(request.url);
        requestedPages.push(url.searchParams.get("page") ?? "");
        expect(url.searchParams.get("page_size")).toBe("20");
        if (url.searchParams.get("page") === "2") {
          return HttpResponse.json({
            items: [
              {
                script_id: 1021,
                name: "script-21",
                description: null,
                resolution: null,
                status: 1,
                created_at: null,
                updated_at: null,
              },
            ],
            total: 21,
            page: 2,
            page_size: 20,
          });
        }
        return HttpResponse.json({
          items: firstPageItems,
          total: 21,
          page: 1,
          page_size: 20,
        });
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

    await screen.findByText("Fresh Phone");
    await user.click(screen.getByRole("radio", { name: "自定义本次执行配置" }));
    await user.click(screen.getByRole("radio", { name: "ScriptRun 脚本" }));
    await user.click(
      await screen.findByRole("combobox", { name: "选择 ScriptRun 脚本资产" }),
    );
    expect((await screen.findAllByText("已显示 20 / 21 条"))[0]).toBeVisible();

    await user.click(screen.getByRole("button", { name: "加载更多资产" }));

    await screen.findByRole("option", { name: "script-21 (#1021)" });
    expect(screen.getAllByText("已显示 21 / 21 条")[0]).toBeVisible();
    expect(requestedPages).toContain("2");
  });

  it("可查看已选 ScriptRun 脚本详情", async () => {
    const longScript = Array.from(
      { length: 40 },
      (_, index) => `tap(${index}, ${index + 1})`,
    ).join("\n");
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
      http.get("/api/v1/agent-run-scripts", () =>
        HttpResponse.json({
          items: [
            {
              script_id: 1001,
              name: "open-app",
              description: "打开应用",
              resolution: "1920x1080",
              status: 1,
              created_at: 1785738000,
              updated_at: 1785738600,
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      ),
      http.get("/api/v1/agent-run-scripts/1001", () =>
        HttpResponse.json({
          script_id: 1001,
          name: "open-app",
          description: "打开应用",
          resolution: "1920x1080",
          status: 1,
          created_at: 1785738000,
          updated_at: 1785738600,
          script: longScript,
        }),
      ),
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
    await user.click(screen.getByRole("radio", { name: "自定义本次执行配置" }));
    await user.click(screen.getByRole("radio", { name: "ScriptRun 脚本" }));
    await user.click(
      await screen.findByRole("combobox", { name: "选择 ScriptRun 脚本资产" }),
    );
    await user.click(await screen.findByRole("option", { name: "open-app (#1001)" }));

    const detailRegion = await screen.findByRole("region", {
      name: "资产详情预览",
    });
    expect(within(detailRegion).getByText(/tap\(0, 1\)/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "查看资产详情" }))
      .not.toBeInTheDocument();
    expect(STYLES).toMatch(
      /\.agent-run-asset-detail-body\s*\{[^}]*max-height:\s*[^;]+;[^}]*overflow:\s*auto;/s,
    );
  });

  it("切换到详情加载失败的资产时清除上一资产详情", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
      http.get("/api/v1/agent-run-scripts", () =>
        HttpResponse.json({
          items: [
            {
              script_id: 1001,
              name: "asset-a",
              description: "资产 A",
              resolution: "1920x1080",
              status: 1,
              created_at: null,
              updated_at: null,
            },
            {
              script_id: 1002,
              name: "asset-b",
              description: "资产 B",
              resolution: "1920x1080",
              status: 1,
              created_at: null,
              updated_at: null,
            },
          ],
          total: 2,
          page: 1,
          page_size: 20,
        }),
      ),
      http.get("/api/v1/agent-run-scripts/1001", () =>
        HttpResponse.json({
          script_id: 1001,
          name: "asset-a",
          description: "资产 A",
          resolution: "1920x1080",
          status: 1,
          created_at: null,
          updated_at: null,
          script: "asset-a-unique-detail",
        }),
      ),
      http.get("/api/v1/agent-run-scripts/1002", () =>
        HttpResponse.json({}, { status: 500 }),
      ),
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
    await user.click(screen.getByRole("radio", { name: "自定义本次执行配置" }));
    await user.click(screen.getByRole("radio", { name: "ScriptRun 脚本" }));
    const assetPicker = await screen.findByRole("combobox", {
      name: "选择 ScriptRun 脚本资产",
    });
    await user.click(assetPicker);
    await user.click(await screen.findByRole("option", { name: "asset-a (#1001)" }));
    expect(await screen.findByText("asset-a-unique-detail")).toBeVisible();

    await user.click(assetPicker);
    await user.click(await screen.findByRole("option", { name: "asset-b (#1002)" }));

    expect(await screen.findByRole("button", { name: "详情加载失败，重试" }))
      .toBeVisible();
    expect(screen.queryByText("asset-a-unique-detail")).not.toBeInTheDocument();
  });

  it("不渲染与当前所选资产 ID 不匹配的详情", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
      http.get("/api/v1/agent-run-scripts", () =>
        HttpResponse.json({
          items: [
            {
              script_id: 1001,
              name: "asset-a",
              description: "资产 A",
              resolution: "1920x1080",
              status: 1,
              created_at: null,
              updated_at: null,
            },
            {
              script_id: 1002,
              name: "asset-b",
              description: "资产 B",
              resolution: "1920x1080",
              status: 1,
              created_at: null,
              updated_at: null,
            },
          ],
          total: 2,
          page: 1,
          page_size: 20,
        }),
      ),
      http.get("/api/v1/agent-run-scripts/1001", () =>
        HttpResponse.json({
          script_id: 1001,
          name: "asset-a",
          description: "资产 A",
          resolution: "1920x1080",
          status: 1,
          created_at: null,
          updated_at: null,
          script: "asset-a-identity-detail",
        }),
      ),
      http.get("/api/v1/agent-run-scripts/1002", async () => {
        await delay(50);
        return HttpResponse.json({
          script_id: 1001,
          name: "asset-a",
          description: "资产 A",
          resolution: "1920x1080",
          status: 1,
          created_at: null,
          updated_at: null,
          script: "asset-a-identity-detail",
        });
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

    await screen.findByText("Fresh Phone");
    await user.click(screen.getByRole("radio", { name: "自定义本次执行配置" }));
    await user.click(screen.getByRole("radio", { name: "ScriptRun 脚本" }));
    const assetPicker = await screen.findByRole("combobox", {
      name: "选择 ScriptRun 脚本资产",
    });
    await user.click(assetPicker);
    await user.click(await screen.findByRole("option", { name: "asset-a (#1001)" }));
    expect(await screen.findByText("asset-a-identity-detail")).toBeVisible();

    await user.click(assetPicker);
    await user.click(await screen.findByRole("option", { name: "asset-b (#1002)" }));
    await waitForElementToBeRemoved(
      await screen.findByText("正在加载资产详情..."),
    );

    expect(screen.queryByText("asset-a-identity-detail")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "详情加载失败，重试" }),
    ).toBeVisible();
  });

  it("可清除已选资产并关闭详情", async () => {
    server.use(
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(refreshedPool)),
      http.get("/api/v1/agent-run-scripts", () =>
        HttpResponse.json({
          items: [
            {
              script_id: 1001,
              name: "open-app",
              description: "打开应用",
              resolution: "1920x1080",
              status: 1,
              created_at: null,
              updated_at: null,
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      ),
      http.get("/api/v1/agent-run-scripts/1001", () =>
        HttpResponse.json({
          script_id: 1001,
          name: "open-app",
          description: "打开应用",
          resolution: "1920x1080",
          status: 1,
          created_at: null,
          updated_at: null,
          script: "tap(0, 1)",
        }),
      ),
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
    await user.click(screen.getByRole("radio", { name: "自定义本次执行配置" }));
    await user.click(screen.getByRole("radio", { name: "ScriptRun 脚本" }));
    const assetPicker = await screen.findByRole("combobox", {
      name: "选择 ScriptRun 脚本资产",
    });
    await user.click(assetPicker);
    await user.click(await screen.findByRole("option", { name: "open-app (#1001)" }));
    await screen.findByRole("region", { name: "资产详情预览" });

    await user.click(screen.getByRole("button", { name: "清除已选资产" }));

    expect(assetPicker).toHaveFocus();
    expect(screen.getByText("请选择一个资产")).toBeVisible();
    expect(screen.queryByRole("region", { name: "资产详情预览" }))
      .not.toBeInTheDocument();
  });

  it("用轻量菜单样式展示执行资产候选项", () => {
    expect(STYLES).toMatch(
      /\.agent-run-asset-option-list\s*\{[^}]*max-height:\s*252px;[^}]*overflow:\s*auto;[^}]*scrollbar-gutter:\s*stable;/s,
    );
    expect(STYLES).toMatch(
      /\.agent-run-asset-option\s*\{[^}]*border:\s*0;[^}]*border-left:\s*3px solid transparent;[^}]*min-height:\s*32px;/s,
    );
    expect(STYLES).toMatch(
      /\.agent-run-asset-option \+ \.agent-run-asset-option\s*\{[^}]*border-top:\s*1px solid var\(--mua-neutral-100\);/s,
    );
    expect(STYLES).toMatch(
      /\.agent-run-asset-popover\s*\{[^}]*border:\s*1px solid var\(--mua-input\);[^}]*border-radius:\s*var\(--radius-md\);[^}]*overflow:\s*hidden;/s,
    );
    expect(STYLES).toMatch(
      /\.agent-run-asset-option-list\s*\{[^}]*border:\s*0;[^}]*border-radius:\s*0;/s,
    );
    expect(STYLES).toMatch(
      /\.agent-run-asset-search[^}]*\{[^}]*border:\s*0;[^}]*border-bottom:\s*1px solid var\(--mua-neutral-100\);[^}]*border-radius:\s*0;/s,
    );
  });

  it("使用主从分栏执行资产工作区", () => {
    expect(STYLES).toMatch(
      /\.agent-run-asset-picker\s*\{[^}]*display:\s*grid;[^}]*grid-template-columns:\s*minmax\(280px,\s*340px\) minmax\(0,\s*1fr\);/s,
    );
    expect(STYLES).toMatch(
      /\.agent-run-asset-selection-pane\s*\{[^}]*border-right:\s*1px solid var\(--mua-border\);/s,
    );
    expect(STYLES).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.agent-run-asset-picker\s*\{[^}]*grid-template-columns:\s*1fr;/s,
    );
  });

  it("区分空状态、已选状态和当前选项", () => {
    expect(STYLES).toMatch(
      /\.agent-run-asset-trigger\s*\{[^}]*min-height:\s*48px;/s,
    );
    expect(STYLES).toMatch(
      /\.agent-run-asset-trigger\.has-selection\s*\{[^}]*min-height:\s*64px;/s,
    );
    expect(STYLES).toMatch(
      /\.agent-run-asset-option\.selected\s*\{[^}]*background:\s*var\(--mua-primary-50\);[^}]*border-left-color:\s*var\(--mua-primary\);/s,
    );
    expect(STYLES).toMatch(
      /\.agent-run-asset-option-check\s*\{[^}]*background:\s*var\(--mua-primary-100\);[^}]*border-radius:\s*999px;[^}]*display:\s*inline-flex;/s,
    );
  });

  it("uses a centered CSS checkmark for checked switches", () => {
    expect(STYLES).toMatch(
      /\.checkbox-row \.checkbox-box::after\s*\{[^}]*content:\s*""\s*;/s,
    );
    expect(STYLES).toMatch(
      /\.checkbox-row \.checkbox-box\s*\{[^}]*position:\s*relative;/s,
    );
    expect(STYLES).toMatch(
      /\.checkbox-row \.checkbox-box::after\s*\{[^}]*position:\s*absolute;[^}]*left:\s*50%;[^}]*top:\s*50%;/s,
    );
    expect(STYLES).toMatch(
      /\.checkbox-row \.checkbox-box::after\s*\{[^}]*border-width:\s*0 2px 2px 0;[^}]*transform:\s*translate\(-50%,\s*-58%\) rotate\(45deg\);/s,
    );
    expect(STYLES).toMatch(
      /\.checkbox-row input\[type="checkbox"\]:checked \+ \.checkbox-box::after\s*\{[^}]*opacity:\s*1;/s,
    );
    expect(STYLES).not.toMatch(
      /\.checkbox-row input\[type="checkbox"\]:checked \+ \.checkbox-box::after\s*\{[^}]*content:\s*"[^"]+"/s,
    );
    expect(STYLES).not.toMatch(
      /\.checkbox-row input\[type="checkbox"\]:checked \+ \.checkbox-box::after\s*\{[^}]*transform:\s*none;/s,
    );
  });
});
