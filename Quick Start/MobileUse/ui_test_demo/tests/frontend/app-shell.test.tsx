import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { MemoryRouter } from "react-router";
import { expect, it, vi } from "vitest";

import { AppShell } from "../../web/components/app-shell";
import { BusinessProvider } from "../../web/business-context";
import type { User } from "../../web/api/types";
import { server } from "./setup";

const user: User = {
  id: 1,
  username: "admin",
  display_name: null,
  email: null,
  role: "admin",
  status: "active",
  created_at: "2026-07-24T00:00:00Z",
  updated_at: "2026-07-24T00:00:00Z",
  last_login_at: null,
};

it("orders primary navigation and hides the new-task entry", () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AppShell user={user}>
          <div>content</div>
        </AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(screen.queryByText("MUA Test")).not.toBeInTheDocument();
  expect(screen.queryByText("AUTOMATION")).not.toBeInTheDocument();
  expect(screen.getByText("MUA")).toHaveClass("sidebar-brand-name");
  expect(screen.getByText("自动化测试平台")).toHaveClass("sidebar-brand-tag");
  expect(screen.getByRole("button", { name: "当前业务：默认业务" }))
    .toBeInTheDocument();
  expect(document.querySelector(".sidebar-logo-mark")).toBeInTheDocument();

  const navigation = screen.getByRole("navigation", { name: "主导航" });
  expect(within(navigation).queryByRole("link", { name: "新建任务" }))
    .not.toBeInTheDocument();
  expect(within(navigation).getAllByRole("link").map((link) =>
    link.textContent
  )).toEqual([
    "用例库",
    "测试计划",
    "测试报告",
    "执行记录",
    "设备池",
    "用户管理",
    "设置",
  ]);
});

it("hides administrator navigation entries for members", () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AppShell user={{ ...user, role: "member", username: "alice" }}>
          <div>content</div>
        </AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  const navigation = screen.getByRole("navigation", { name: "主导航" });
  expect(within(navigation).getAllByRole("link").map((link) =>
    link.textContent
  )).toEqual([
    "用例库",
    "测试计划",
    "测试报告",
    "执行记录",
    "设备池",
    "设置",
  ]);
  expect(within(navigation).getByRole("link", { name: "设备池" }))
    .toHaveAttribute("href", "/pods");
  expect(within(navigation).queryByRole("link", { name: "用户管理" }))
    .not.toBeInTheDocument();
});

it("closes the business menu when clicking outside", async () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const userEventApi = userEvent.setup();

  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AppShell user={user}>
          <button type="button">外部区域</button>
        </AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await userEventApi.click(screen.getByRole("button", { name: "当前业务：默认业务" }));
  expect(screen.getByRole("dialog", { name: "业务空间" })).toBeInTheDocument();

  await userEventApi.click(screen.getByRole("button", { name: "外部区域" }));
  expect(screen.queryByRole("dialog", { name: "业务空间" })).not.toBeInTheDocument();
});

it("creates a business from a modal and writes its default execution config", async () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const userEventApi = userEvent.setup();
  let settingsPutCalls = 0;

  server.use(
    http.get("/api/v1/business-spaces", () =>
      HttpResponse.json({
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
        ],
      })),
    http.get("/api/v1/business-spaces/product-id-available", ({ request }) => {
      expect(new URL(request.url).searchParams.get("product_id")).toBe("product-pay");
      return HttpResponse.json({ available: true });
    }),
    http.post("/api/v1/business-spaces", async ({ request }) => {
      expect(await request.json()).toEqual({
        name: "支付业务",
        description: "支付回归",
        task_concurrency_limit: 4,
        runner_settings: {
          mode: "mobile_use",
          mobile_use: {
            product_id: "product-pay",
            account_id: "2100000000000000000",
            access_key_id: "AKLT00000000WXYZ",
            secret_access_key: "secret-value",
            tos_bucket: "pay-bucket",
            tos_region: "cn-beijing",
            timeout_seconds: 120,
            max_step: 100,
          },
        },
      });
      return HttpResponse.json(
        {
          id: "biz_pay",
          name: "支付业务",
          description: "支付回归",
          is_default: false,
          task_concurrency_limit: 4,
          archived_at: null,
          created_by: "admin",
        },
        { status: 201 },
      );
    }),
    http.put("/api/v1/settings/runner", () => {
      settingsPutCalls += 1;
      return HttpResponse.json({}, { status: 500 });
    }),
  );

  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <BusinessProvider>
          <AppShell user={user}>
            <div>content</div>
          </AppShell>
        </BusinessProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await userEventApi.click(await screen.findByRole("button", { name: "当前业务：默认业务" }));
  await userEventApi.click(screen.getByRole("button", { name: "新建业务" }));

  const dialog = screen.getByRole("dialog", { name: "新建业务空间" });
  expect(within(dialog).getByLabelText("任务并发上限")).toHaveValue(4);
  await userEventApi.type(within(dialog).getByLabelText("业务名称"), "支付业务");
  await userEventApi.type(within(dialog).getByLabelText("业务描述"), "支付回归");
  await userEventApi.type(within(dialog).getByLabelText("Product ID"), "product-pay");
  await userEventApi.type(within(dialog).getByLabelText("Volcengine AccountId"), "2100000000000000000");
  await userEventApi.type(within(dialog).getByLabelText("Access Key ID"), "AKLT00000000WXYZ");
  await userEventApi.type(within(dialog).getByLabelText("Secret Access Key"), "secret-value");
  await userEventApi.type(within(dialog).getByLabelText("TOS Bucket"), "pay-bucket");
  await userEventApi.type(within(dialog).getByLabelText("TOS Region"), "cn-beijing");
  await userEventApi.click(within(dialog).getByRole("button", { name: "创建业务" }));

  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: "新建业务空间" })).not.toBeInTheDocument(),
  );
  expect(settingsPutCalls).toBe(0);
});

it("allows editing the default business concurrency limit", async () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const userEventApi = userEvent.setup();
  let updatePayload: unknown = null;

  server.use(
    http.patch("/api/v1/business-spaces/biz_default", async ({ request }) => {
      updatePayload = await request.json();
      return HttpResponse.json({
        id: "biz_default",
        name: "默认业务",
        description: null,
        is_default: true,
        task_concurrency_limit: 8,
        archived_at: null,
        created_by: "system",
      });
    }),
  );

  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <BusinessProvider>
          <AppShell user={user}>
            <div>content</div>
          </AppShell>
        </BusinessProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await userEventApi.click(await screen.findByRole("button", { name: "当前业务：默认业务" }));
  await userEventApi.click(screen.getByRole("button", { name: "编辑" }));
  const dialog = screen.getByRole("dialog", { name: "编辑业务空间" });
  const concurrencyInput = within(dialog).getByLabelText("任务并发上限");
  expect(concurrencyInput).toHaveValue(4);

  await userEventApi.clear(concurrencyInput);
  await userEventApi.type(concurrencyInput, "8");
  await userEventApi.click(within(dialog).getByRole("button", { name: "保存修改" }));

  await waitFor(() =>
    expect(updatePayload).toEqual({
      name: "默认业务",
      description: null,
      task_concurrency_limit: 8,
    }),
  );
});

it("does not create a business when default execution config is incomplete", async () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const userEventApi = userEvent.setup();
  let createCalls = 0;

  server.use(
    http.get("/api/v1/business-spaces", () =>
      HttpResponse.json({
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
        ],
      })),
    http.post("/api/v1/business-spaces", () => {
      createCalls += 1;
      return HttpResponse.json({}, { status: 500 });
    }),
  );

  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <BusinessProvider>
          <AppShell user={user}>
            <div>content</div>
          </AppShell>
        </BusinessProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await userEventApi.click(await screen.findByRole("button", { name: "当前业务：默认业务" }));
  await userEventApi.click(screen.getByRole("button", { name: "新建业务" }));
  const dialog = screen.getByRole("dialog", { name: "新建业务空间" });
  await userEventApi.type(within(dialog).getByLabelText("业务名称"), "空配置业务");
  await userEventApi.click(within(dialog).getByRole("button", { name: "创建业务" }));

  expect(await within(dialog).findByText(/默认执行配置必须完整/)).toBeInTheDocument();
  expect(createCalls).toBe(0);
});

it("shows unsupported request header names when creating a business", async () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const userEventApi = userEvent.setup();
  let createCalls = 0;

  server.use(
    http.get("/api/v1/business-spaces", () =>
      HttpResponse.json({
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
        ],
      })),
    http.post("/api/v1/business-spaces", () => {
      createCalls += 1;
      return HttpResponse.json({}, { status: 500 });
    }),
  );

  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <BusinessProvider>
          <AppShell user={user}>
            <div>content</div>
          </AppShell>
        </BusinessProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await userEventApi.click(await screen.findByRole("button", { name: "当前业务：默认业务" }));
  await userEventApi.click(screen.getByRole("button", { name: "新建业务" }));
  const dialog = screen.getByRole("dialog", { name: "新建业务空间" });
  await userEventApi.type(within(dialog).getByLabelText("业务名称"), "Header 业务");
  await userEventApi.type(within(dialog).getByLabelText("Product ID"), "product-header");
  await userEventApi.type(within(dialog).getByLabelText("Access Key ID"), "AKLT00000000WXYZ");
  await userEventApi.type(within(dialog).getByLabelText("Secret Access Key"), "secret-value");
  await userEventApi.type(within(dialog).getByLabelText("TOS Bucket"), "header-bucket");
  await userEventApi.type(within(dialog).getByLabelText("TOS Region"), "cn-beijing");
  fireEvent.change(within(dialog).getByLabelText("请求 Header（JSON 对象）"), {
    target: { value: '{"Authorization":"Bearer token"}' },
  });
  await userEventApi.click(within(dialog).getByRole("button", { name: "创建业务" }));

  expect(
    await within(dialog).findByText("请求 Header 包含不允许覆盖的保留字段：Authorization"),
  ).toBeInTheDocument();
  expect(createCalls).toBe(0);
});

it("does not create a business when product id is already used", async () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const userEventApi = userEvent.setup();
  let createCalls = 0;

  server.use(
    http.get("/api/v1/business-spaces", () =>
      HttpResponse.json({
        items: [
          {
            id: "biz_default",
            name: "默认业务",
            description: null,
            is_default: true,
            archived_at: null,
            created_by: "system",
          },
        ],
      })),
    http.get("/api/v1/business-spaces/product-id-available", ({ request }) => {
      expect(new URL(request.url).searchParams.get("product_id")).toBe("product-used");
      return HttpResponse.json({ available: false });
    }),
    http.post("/api/v1/business-spaces", () => {
      createCalls += 1;
      return HttpResponse.json({}, { status: 500 });
    }),
  );

  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <BusinessProvider>
          <AppShell user={user}>
            <div>content</div>
          </AppShell>
        </BusinessProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await userEventApi.click(await screen.findByRole("button", { name: "当前业务：默认业务" }));
  await userEventApi.click(screen.getByRole("button", { name: "新建业务" }));
  const dialog = screen.getByRole("dialog", { name: "新建业务空间" });
  await userEventApi.type(within(dialog).getByLabelText("业务名称"), "重复业务");
  await userEventApi.type(within(dialog).getByLabelText("Product ID"), "product-used");
  await userEventApi.type(within(dialog).getByLabelText("Access Key ID"), "AKLT00000000WXYZ");
  await userEventApi.type(within(dialog).getByLabelText("Secret Access Key"), "secret-value");
  await userEventApi.type(within(dialog).getByLabelText("TOS Bucket"), "pay-bucket");
  await userEventApi.type(within(dialog).getByLabelText("TOS Region"), "cn-beijing");
  await userEventApi.click(within(dialog).getByRole("button", { name: "创建业务" }));

  expect(await within(dialog).findByText(/Product ID 已被其它业务使用/)).toBeInTheDocument();
  expect(createCalls).toBe(0);
});

it("renames a business from an in-app modal instead of browser prompt", async () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const userEventApi = userEvent.setup();
  const promptSpy = vi.spyOn(window, "prompt").mockReturnValue("不要使用");
  let renamePayload: unknown = null;

  server.use(
    http.get("/api/v1/business-spaces", () =>
      HttpResponse.json({
        items: [
          {
            id: "biz_default",
            name: "默认业务",
            description: null,
            is_default: true,
            archived_at: null,
            created_by: "system",
          },
          {
            id: "biz_12",
            name: "测试12",
            description: "旧描述",
            is_default: false,
            task_concurrency_limit: 6,
            archived_at: null,
            created_by: "admin",
          },
        ],
      })),
    http.patch("/api/v1/business-spaces/biz_12", async ({ request }) => {
      renamePayload = await request.json();
      return HttpResponse.json({
        id: "biz_12",
        name: "支付业务线",
        description: "核心回归业务",
        is_default: false,
        task_concurrency_limit: 8,
        archived_at: null,
        created_by: "admin",
      });
    }),
  );

  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <BusinessProvider>
          <AppShell user={user}>
            <div>content</div>
          </AppShell>
        </BusinessProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await userEventApi.click(await screen.findByRole("button", { name: "当前业务：默认业务" }));
  await userEventApi.click(screen.getByRole("button", { name: "测试12" }));
  await userEventApi.click(await screen.findByRole("button", { name: "当前业务：测试12" }));
  await userEventApi.click(screen.getByRole("button", { name: "编辑" }));

  expect(promptSpy).not.toHaveBeenCalled();
  const dialog = screen.getByRole("dialog", { name: "编辑业务空间" });
  const nameInput = within(dialog).getByLabelText("业务名称");
  const descInput = within(dialog).getByLabelText("业务描述");
  const concurrencyInput = within(dialog).getByLabelText("任务并发上限");
  expect(nameInput).toHaveValue("测试12");
  expect(descInput).toHaveValue("旧描述");
  expect(concurrencyInput).toHaveValue(6);

  await userEventApi.clear(nameInput);
  await userEventApi.type(nameInput, "支付业务线");
  await userEventApi.clear(descInput);
  await userEventApi.type(descInput, "核心回归业务");
  await userEventApi.clear(concurrencyInput);
  await userEventApi.type(concurrencyInput, "8");
  await userEventApi.click(within(dialog).getByRole("button", { name: "保存修改" }));

  await waitFor(() =>
    expect(renamePayload).toEqual({
      name: "支付业务线",
      description: "核心回归业务",
      task_concurrency_limit: 8,
    }),
  );
  expect(screen.queryByRole("dialog", { name: "编辑业务空间" })).not.toBeInTheDocument();
  promptSpy.mockRestore();
});
