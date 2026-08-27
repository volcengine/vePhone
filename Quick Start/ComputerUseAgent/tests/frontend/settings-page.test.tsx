import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SettingsResponse } from "../../web/api/types";
import { expectCsrf, renderApp, server, user } from "./setup";

const configuredSettings: SettingsResponse = {
  mode: "mobile_use",
  mobile_use: {
    access_key_id: { configured: true, hint: "AKLT****WXYZ" },
    secret_access_key: { configured: true },
    product_id: "prod_123",
    account_id: "2100000000000000000",
    sts_role_trn: "trn:iam::2100000000000000000:role/mua-stream-viewer",
    stream_token_ttl_seconds: 600,
    pod_id: "pod_123",
    ark_api_key: { configured: true },
    tos_bucket: "mua-artifacts",
    tos_endpoint: "tos-s3-cn-beijing.volces.com",
    tos_region: "cn-beijing",
    use_base64_screenshot: false,
    max_step: 100,
    timeout_seconds: 120,
    callback_info: null,
    output_schema: null,
    retry_limit: 3,
    system_prompt: null,
    screen_record: false,
    mcp_json: null,
    max_output_tokens: null,
    gps_info: null,
    request_headers: { configured: true, names: ["X-Env"] },
  },
};

function useSettings(settings: SettingsResponse = configuredSettings) {
  server.use(http.get("/api/v1/settings", () => HttpResponse.json(settings)));
}

afterEach(() => {
  localStorage.removeItem("mua-theme-preference");
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-theme-preference");
  vi.unstubAllGlobals();
});

describe("设置页", () => {
  it("按参考设计展示四个设置分区并移除 Runner 模式", async () => {
    useSettings();

    renderApp("/settings");

    expect(await screen.findByRole("heading", { name: "设置" })).toBeVisible();
    const nav = screen.getByLabelText("设置导航");
    expect(within(nav).getByRole("link", { name: "个人资料" })).toHaveAttribute(
      "href",
      "#profile",
    );
    expect(within(nav).getByRole("link", { name: "修改密码" })).toHaveAttribute(
      "href",
      "#password",
    );
    expect(within(nav).queryByRole("link", { name: "通知设置" })).not.toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "CUA 运行配置" })).toHaveAttribute(
      "href",
      "#defaults",
    );
    expect(screen.getByLabelText("姓名")).toHaveValue("admin");
    expect(screen.getByLabelText("邮箱")).toHaveValue("admin@example.com");
    expect(screen.getByRole("radiogroup", { name: "主题偏好" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "通知设置" })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "邮件通知" })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "短信通知" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Mock")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Mobile Use")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重新诊断" })).not.toBeInTheDocument();
  });

  it("本地持久化主题偏好并立即应用深色主题", async () => {
    useSettings();

    renderApp("/settings");

    await screen.findByRole("heading", { name: "设置" });
    await user.click(screen.getByLabelText("深色"));

    expect(localStorage.getItem("mua-theme-preference")).toBe("dark");
    expect(document.documentElement).toHaveAttribute("data-theme-preference", "dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });

  it("跟随系统主题并响应系统主题变化", async () => {
    let changeListener: (event: MediaQueryListEvent) => void = () => undefined;
    let matches = true;
    vi.stubGlobal("matchMedia", vi.fn(() => ({
      matches,
      media: "(prefers-color-scheme: dark)",
      onchange: null,
      addEventListener: vi.fn((event: string, listener: (event: MediaQueryListEvent) => void) => {
        if (event === "change") changeListener = listener;
      }),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })));
    useSettings();

    renderApp("/settings");

    await screen.findByRole("heading", { name: "设置" });
    await user.click(screen.getByLabelText("跟随系统"));

    expect(localStorage.getItem("mua-theme-preference")).toBe("system");
    expect(document.documentElement).toHaveAttribute("data-theme-preference", "system");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");

    matches = false;
    changeListener({ matches: false } as MediaQueryListEvent);

    await waitFor(() =>
      expect(document.documentElement).toHaveAttribute("data-theme", "light"),
    );
  });

  it("不回填密钥并按 CUA 配置保存运行默认值", async () => {
    let updateBody: unknown;
    useSettings();
    server.use(
      http.put("/api/v1/settings/runner", async ({ request }) => {
        expectCsrf(request);
        updateBody = await request.json();
        return HttpResponse.json({
          ...configuredSettings,
          mobile_use: {
            ...configuredSettings.mobile_use,
            product_id: "prod_456",
          },
        });
      }),
    );

    renderApp("/settings");

    await screen.findByRole("heading", { name: "CUA 运行配置" });
    expect(screen.getByText("默认使用 Computer Use Agent。密钥只支持覆盖更新，不会回填原值。")).toBeVisible();
    expect(screen.getByLabelText("Access Key ID")).toHaveValue("");
    expect(screen.getByLabelText("Secret Access Key")).toHaveValue("");
    expect(screen.getByText("已配置：AKLT****WXYZ")).toBeVisible();
    expect(screen.getByText("已配置，留空则保留")).toBeVisible();
    expect(screen.getByText("已配置：X-Env；留空则保留")).toBeVisible();
    expect(screen.getByLabelText("请求 Header（JSON 对象）")).toHaveValue("");
    expect(screen.getByLabelText("请求 Header（JSON 对象）")).toHaveAttribute(
      "placeholder",
      '{"X-Env":"test","X-Request-Source":"cua"}',
    );
    expect(screen.queryByLabelText("Ark API Key")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Product ID")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Pod ID")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("STS RoleTrn")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("推流 Token 有效期（秒）")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("UseBase64Screenshot")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("IsScreenRecord")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("GpsInfo")).not.toBeInTheDocument();
    expect(screen.getByLabelText("CUA AccountId")).toHaveValue("2100000000000000000");
    expect(screen.getByLabelText("任务超时 Timeout（秒）")).toHaveValue("120");

    await user.clear(screen.getByLabelText("CUA AccountId"));
    await user.type(screen.getByLabelText("CUA AccountId"), "2100000000000000001");
    await user.clear(screen.getByLabelText("任务超时 Timeout（秒）"));
    await user.type(screen.getByLabelText("任务超时 Timeout（秒）"), "456");
    fireEvent.change(screen.getByLabelText("请求 Header（JSON 对象）"), {
      target: { value: '{"X-Env":"staging"}' },
    });
    await user.click(screen.getByRole("button", { name: "保存所有更改" }));

    await waitFor(() =>
      expect(updateBody).toEqual({
        mode: "mobile_use",
        mobile_use: {
          account_id: "2100000000000000001",
          timeout_seconds: 456,
          request_headers: { "X-Env": "staging" },
        },
      }),
    );
    expect(screen.getByText("设置已保存。")).toBeVisible();
  });

  it("支持显式清除可选 CUA 运行配置", async () => {
    let updateBody: unknown;
    vi.spyOn(window, "confirm").mockImplementation(() => {
      throw new Error("native confirm should not be used");
    });
    useSettings({
      ...configuredSettings,
      mobile_use: {
        ...configuredSettings.mobile_use,
        callback_info: { url: "https://callback.example.com" },
        output_schema: '{"type":"object"}',
        system_prompt: "custom system prompt",
        mcp_json: '{"mcpServers":{}}',
        max_output_tokens: 2048,
        request_headers: { configured: true, names: ["X-Env"] },
      },
    });
    server.use(
      http.put("/api/v1/settings/runner", async ({ request }) => {
        expectCsrf(request);
        updateBody = await request.json();
        return HttpResponse.json({
          ...configuredSettings,
          mobile_use: {
            ...configuredSettings.mobile_use,
            request_headers: { configured: false, names: [] },
          },
        });
      }),
    );

    renderApp("/settings");

    await screen.findByRole("heading", { name: "CUA 运行配置" });
    async function clearField(label: string) {
      await user.click(screen.getByRole("button", { name: `清除 ${label}` }));
      const dialog = await screen.findByRole("dialog", { name: "清除配置" });
      expect(within(dialog).getByText(`确认清除 ${label}？`)).toBeVisible();
      await user.click(within(dialog).getByRole("button", { name: "清除" }));
    }

    await clearField("MaxOutputTokens");
    await clearField("SystemPrompt");
    await clearField("CallbackInfo");
    await clearField("OutputSchema");
    await clearField("McpJson");
    await clearField("请求 Header（JSON 对象）");
    await user.click(screen.getByRole("button", { name: "保存所有更改" }));

    await waitFor(() =>
      expect(updateBody).toEqual({
        mode: "mobile_use",
        mobile_use: {
          max_output_tokens: null,
          system_prompt: null,
          callback_info: null,
          output_schema: null,
          mcp_json: null,
          request_headers: null,
        },
      }),
    );
  });

  it("保存 CUA 运行配置失败时使用弹窗展示错误", async () => {
    useSettings();
    server.use(
      http.put("/api/v1/settings/runner", async ({ request }) => {
        expectCsrf(request);
        return HttpResponse.json(
          {
            error: {
              code: "runner_config_invalid",
              message: "CUA AccountId 配置无效，请检查后重新保存。",
              request_id: "req-settings-save-42",
              details: { field: "account_id" },
            },
          },
          { status: 400 },
        );
      }),
    );

    renderApp("/settings");

    await screen.findByRole("heading", { name: "CUA 运行配置" });
    await user.clear(screen.getByLabelText("CUA AccountId"));
    await user.type(screen.getByLabelText("CUA AccountId"), "bad-account");
    await user.click(screen.getByRole("button", { name: "保存所有更改" }));

    const dialog = await screen.findByRole("dialog", { name: "保存失败" });
    expect(within(dialog).getByText("CUA AccountId 配置无效，请检查后重新保存。")).toBeVisible();
    expect(within(dialog).getByText(/req-settings-save-42/)).toBeVisible();
    expect(
      document.querySelector(".settings-feedback [role='alert']"),
    ).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "我知道了" }));
    expect(screen.queryByRole("dialog", { name: "保存失败" })).not.toBeInTheDocument();
  });

  it("缺少 CUA 运行配置时只标出三个必填字段", async () => {
    useSettings({
      mode: "mock",
      mobile_use: {
        access_key_id: { configured: false, hint: null },
        secret_access_key: { configured: false },
        product_id: null,
        account_id: null,
        sts_role_trn: null,
        stream_token_ttl_seconds: 600,
        pod_id: null,
        ark_api_key: { configured: false },
        tos_bucket: null,
        tos_endpoint: null,
        tos_region: null,
        use_base64_screenshot: false,
        max_step: 100,
        timeout_seconds: 120,
        callback_info: null,
        output_schema: null,
        retry_limit: 3,
        system_prompt: null,
        screen_record: false,
        mcp_json: null,
        max_output_tokens: null,
        gps_info: null,
        request_headers: { configured: false, names: [] },
      },
    });

    renderApp("/settings");

    await screen.findByRole("heading", { name: "CUA 运行配置" });
    await user.click(screen.getByRole("button", { name: "保存所有更改" }));

    const dialog = await screen.findByRole("dialog", { name: "保存失败" });
    expect(within(dialog).getByText("请补齐 CUA 运行配置。")).toBeVisible();
    expect(screen.getByText("Access Key ID 为必填项")).toBeVisible();
    expect(screen.getByText("Secret Access Key 为必填项")).toBeVisible();
    expect(screen.getByText("CUA AccountId 为必填项")).toBeVisible();
    expect(screen.queryByText("Product ID 为必填项")).not.toBeInTheDocument();
    expect(screen.queryByText("TOS Bucket 为必填项")).not.toBeInTheDocument();
    expect(screen.queryByText("TOS Region 为必填项")).not.toBeInTheDocument();
  });

  it("支持修改密码并发送 CSRF 请求", async () => {
    let passwordBody: unknown;
    useSettings();
    server.use(
      http.post("/api/v1/auth/password", async ({ request }) => {
        expectCsrf(request);
        passwordBody = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderApp("/settings");

    await screen.findByRole("heading", { name: "修改密码" });
    await user.type(screen.getByLabelText("当前密码"), "StrongPassword123!");
    await user.type(screen.getByLabelText("新密码"), "NewStrongPassword123!");
    await user.type(screen.getByLabelText("确认新密码"), "NewStrongPassword123!");
    await user.click(screen.getByRole("button", { name: "更新密码" }));

    await waitFor(() =>
      expect(passwordBody).toEqual({
        current_password: "StrongPassword123!",
        new_password: "NewStrongPassword123!",
        confirm_password: "NewStrongPassword123!",
      }),
    );
    expect(screen.getByText("密码已更新，请重新登录。")).toBeVisible();
  });

  it("普通成员只能看到个人资料和修改密码", async () => {
    server.use(
      http.get("/api/v1/auth/me", () =>
        HttpResponse.json({
          id: 2,
          username: "alice",
          display_name: "Alice",
          email: "alice@example.com",
          role: "member",
          status: "active",
          created_at: "2026-07-25T00:00:00Z",
          updated_at: "2026-07-25T00:00:00Z",
          last_login_at: null,
        })),
    );

    renderApp("/settings");

    expect(await screen.findByRole("heading", { name: "设置" })).toBeVisible();
    const nav = screen.getByLabelText("设置导航");
    expect(within(nav).getByRole("link", { name: "个人资料" })).toBeVisible();
    expect(within(nav).getByRole("link", { name: "修改密码" })).toBeVisible();
    expect(within(nav).queryByRole("link", { name: "CUA 运行配置" }))
      .not.toBeInTheDocument();
    expect(screen.getByLabelText("姓名")).toHaveValue("Alice");
    expect(screen.getByLabelText("邮箱")).toHaveValue("alice@example.com");
    expect(screen.queryByRole("heading", { name: "CUA 运行配置" }))
      .not.toBeInTheDocument();
    expect(screen.queryByLabelText("Access Key ID")).not.toBeInTheDocument();
  });

});
