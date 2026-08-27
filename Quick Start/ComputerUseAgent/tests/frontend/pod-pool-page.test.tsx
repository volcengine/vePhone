import { readFileSync } from "node:fs";

import { screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PodPoolResponse } from "../../web/api/types";
import { expectCsrf, renderApp, server, user } from "./setup";

const STYLES = readFileSync("web/styles.css", "utf8");

const sdkStart = vi.fn(async () => ({ width: 1080, height: 1920 }));
const sdkStop = vi.fn(async () => undefined);
const sdkDestroy = vi.fn(async () => undefined);

vi.mock("@volcengine/vephone", () => ({
  default: vi.fn().mockImplementation(() => ({
    start: sdkStart,
    stop: sdkStop,
    destroy: sdkDestroy,
  })),
}));

const baseItem = {
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
  node_id: null,
  provider: null,
  project_name: null,
  public_ip: null,
  os_type: null,
  os_name: null,
  instance_type: null,
  vcpu: null,
  memory_gib: null,
  specification: null,
  agent_endpoint: null,
  plugin_version: null,
  script_version: null,
  status_name: null,
  status_message: null,
  last_heartbeat_at: null,
  node_updated_at: null,
};

const initialPool: PodPoolResponse = {
  refreshed_at: "2026-07-26T08:00:00Z",
  items: [
    {
      ...baseItem,
      product_id: "product-alpha",
      pod_id: "pod-alpha",
      pod_name: "AI-OpenClaw-0LRt-000",
      pod_status_code: 2,
      public_ip: "115.191.65.249",
      intranet_ip: "172.31.0.38",
      provider: "volc_ecs",
      project_name: "default",
      region: "cn-beijing",
      zone_id: "cn-beijing-a",
      image_id: "image-z0dpqndnmy8rpzcad9rz",
      os_name: "Ubuntu 24.04 with OpenClaw 64 bit",
      specification: "ecs.e-c1m2.xlarge 4vCPU 8GiB",
      agent_endpoint: "http://115.191.65.249:8910",
      plugin_version: "0.0.3",
      script_version: "0.0.3",
      status_name: "已在线",
      pod_created_at: "2026-07-22T10:22:30Z",
      node_updated_at: "2026-07-26T08:01:00Z",
      discovery_state: "active",
      local_state: "available",
      last_seen_at: "2026-07-26T08:00:00Z",
      last_checked_at: "2026-07-26T08:00:01Z",
      task_id: null,
      task_status: null,
      task_scenario: null,
    },
    {
      ...baseItem,
      product_id: "product-alpha",
      pod_id: "pod-leased",
      pod_name: "Leased Phone",
      pod_status_code: 3,
      discovery_state: "active",
      local_state: "leased",
      last_seen_at: "2026-07-26T08:00:00Z",
      last_checked_at: "2026-07-26T08:00:01Z",
      task_id: "task-running",
      task_status: "running",
      task_scenario: "test-scenario",
    },
    {
      ...baseItem,
      product_id: "product-alpha",
      pod_id: "pod-stale-running",
      pod_name: "Stale Running Phone",
      pod_status_code: 4,
      discovery_state: "stale",
      local_state: "stale",
      last_seen_at: "2026-07-26T07:00:00Z",
      last_checked_at: null,
      task_id: null,
      task_status: null,
      task_scenario: null,
    },
  ],
};

const refreshedPool: PodPoolResponse = {
  refreshed_at: "2026-07-26T09:00:00Z",
  items: [
    {
      ...baseItem,
      product_id: "product-beta",
      pod_id: "pod-beta",
      pod_name: "Beta Phone",
      pod_status_code: 4,
      discovery_state: "stale",
      local_state: "stale",
      last_seen_at: "2026-07-26T09:00:00Z",
      last_checked_at: null,
      task_id: null,
      task_status: null,
      task_scenario: null,
    },
  ],
};

describe("设备池页面", () => {
  beforeEach(() => {
    sdkStart.mockClear();
    sdkStop.mockClear();
    sdkDestroy.mockClear();
  });

  it("自动刷新远端设备池并更新空闲数量", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let refreshRequests = 0;
    const busyPool: PodPoolResponse = {
      refreshed_at: "2026-07-26T08:00:00Z",
      items: [
        {
          ...baseItem,
          product_id: "product-alpha",
          pod_id: "pod-auto",
          pod_name: "Auto Phone",
          pod_status_code: 3,
          discovery_state: "active",
          local_state: "leased",
          last_seen_at: "2026-07-26T08:00:00Z",
          last_checked_at: "2026-07-26T08:00:01Z",
          task_id: "task-running",
          task_status: "running",
          task_scenario: "auto-scenario",
        },
      ],
    };
    const idlePool: PodPoolResponse = {
      refreshed_at: "2026-07-26T08:00:03Z",
      items: [
        {
          ...baseItem,
          product_id: "product-alpha",
          pod_id: "pod-auto",
          pod_name: "Auto Phone",
          pod_status_code: 2,
          discovery_state: "active",
          local_state: "available",
          last_seen_at: "2026-07-26T08:00:03Z",
          last_checked_at: "2026-07-26T08:00:04Z",
          task_id: null,
          task_status: null,
          task_scenario: null,
        },
      ],
    };
    server.use(
      http.get("/api/v1/pod-pool", () => HttpResponse.json(busyPool)),
      http.post("/api/v1/pod-pool/refresh", ({ request }) => {
        expectCsrf(request);
        refreshRequests += 1;
        return HttpResponse.json(idlePool);
      }),
    );

    renderApp("/pods");

    expect(await screen.findByRole("row", { name: /pod-auto/ })).toBeVisible();
    expect(screen.getByText("显示 1-1，共 1 台")).toBeVisible();
    let idleMetric = screen.getAllByText("空闲")
      .find((element) => element.classList.contains("kpi-label"))
      ?.closest(".kpi-card") as HTMLElement;
    expect(within(idleMetric).getByText("0")).toBeVisible();

    await vi.advanceTimersByTimeAsync(3000);

    await waitFor(() => expect(refreshRequests).toBeGreaterThanOrEqual(1));
    idleMetric = screen.getAllByText("空闲")
      .find((element) => element.classList.contains("kpi-label"))
      ?.closest(".kpi-card") as HTMLElement;
    expect(within(idleMetric).getByText("1")).toBeVisible();
    expect(screen.getAllByText("pod-auto").length).toBeGreaterThan(0);

    vi.useRealTimers();
  });

  it("展示实例状态、任务状态、当前任务并刷新缓存", async () => {
    let refreshRequests = 0;
    server.use(
      http.get("/api/v1/pod-pool", () => HttpResponse.json(initialPool)),
      http.post("/api/v1/pod-pool/refresh", ({ request }) => {
        expectCsrf(request);
        refreshRequests += 1;
        return HttpResponse.json(refreshedPool);
      }),
    );

    renderApp("/pods");

    expect(await screen.findByRole("heading", { name: "设备池" })).toBeVisible();
    expect(screen.getByText("管理用于自动化测试任务执行的 CUA 节点")).toBeVisible();
    expect(await screen.findByRole("columnheader", { name: "名称/ID" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "主 IPv4 地址" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "状态" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "任务状态" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "当前任务" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "CUA 套件" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "镜像" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "规格" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "来源" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "所在位置" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "实例 ID" })).toBeVisible();
    expect(screen.queryByRole("combobox", { name: "按云机规格筛选" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "申请新实例" })).not.toBeInTheDocument();
    const alphaRow = await screen.findByRole("row", { name: /AI-OpenClaw-0LRt-000/ });
    expect(within(alphaRow).getByText("115.191.65.249")).toBeVisible();
    expect(within(alphaRow).getByText("172.31.0.38")).toBeVisible();
    expect(within(alphaRow).getByText("0.0.3")).toBeVisible();
    expect(within(alphaRow).getByText("Ubuntu 24.04 with OpenClaw 64 bit")).toBeVisible();
    expect(within(alphaRow).getByText("ecs.e-c1m2.xlarge 4vCPU 8GiB")).toBeVisible();
    expect(within(alphaRow).getByText("火山引擎 ECS")).toBeVisible();
    expect(within(alphaRow).getByText("cn-beijing / cn-beijing-a")).toBeVisible();
    expect(within(alphaRow).getByText("已在线").closest(".status-badge")).toHaveClass("success");
    expect(within(alphaRow).getAllByText("pod-alpha").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "复制实例ID" }).length).toBeGreaterThan(0);
    expect(screen.getByText("显示 1-3，共 3 台")).toBeVisible();
    const idleMetric = screen.getAllByText("空闲")
      .find((element) => element.classList.contains("kpi-label"))
      ?.closest(".kpi-card") as HTMLElement;
    expect(within(idleMetric).getByText("1")).toBeVisible();
    expect(screen.getByText("已在线")).toBeVisible();
    expect(screen.getByText("已在线（占用中）")).toBeVisible();
    expect(screen.getAllByText("异常").length).toBeGreaterThan(0);
    const leasedRow = screen.getByRole("row", { name: /Leased Phone/ });
    expect(within(leasedRow).getByText("执行中")).toBeVisible();
    expect(within(leasedRow).getByRole("link", { name: "task-running" }))
      .toHaveAttribute("href", "/biz/biz_default/tasks/task-running");
    expect(within(leasedRow).getByText("test-scenario")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /删除|重启|关机/ }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "刷新" }));

    expect(await screen.findByRole("row", { name: /pod-beta/ })).toBeVisible();
    expect(screen.getAllByText("异常").length).toBeGreaterThan(0);
    expect(screen.queryByRole("row", { name: /pod-alpha/ })).not.toBeInTheDocument();
    expect(refreshRequests).toBe(1);
  });

  it("CUA 节点列表保留基础行展示", async () => {
    server.use(
      http.get("/api/v1/pod-pool", () =>
        HttpResponse.json({
          refreshed_at: "2026-07-26T08:00:00Z",
          items: [
            {
              ...baseItem,
              product_id: "product-alpha",
              pod_id: "pod-queued",
              pod_name: "Queued Phone",
              pod_status_code: 2,
              discovery_state: "active",
              local_state: "leased",
              last_seen_at: "2026-07-26T08:00:00Z",
              last_checked_at: "2026-07-26T08:00:01Z",
              task_id: "task-queued",
              task_status: "queued",
              task_scenario: "queue-scenario",
            },
          ],
        }),
      ),
    );

    renderApp("/pods");

    const row = await screen.findByRole("row", { name: /pod-queued/ });
    expect(within(row).getByText("Queued Phone")).toBeVisible();
  });

  it("按 CUA 节点状态码展示统一状态", async () => {
    server.use(
      http.get("/api/v1/pod-pool", () =>
        HttpResponse.json({
          refreshed_at: "2026-07-26T08:00:00Z",
          items: [1, 2, 3, 4, 5, 6, 7, 8].map((code) => ({
            ...baseItem,
            product_id: "product-alpha",
            pod_id: `pod-status-${code}`,
            pod_name: `Status ${code}`,
            pod_status_code: code,
            discovery_state: "active",
            local_state: "available",
            last_seen_at: "2026-07-26T08:00:00Z",
            last_checked_at: "2026-07-26T08:00:01Z",
            task_id: null,
            task_status: null,
            task_scenario: null,
          })),
        }),
      ),
    );

    renderApp("/pods");

    expect(await screen.findByText("创建中")).toBeVisible();
    expect(screen.getByText("已在线")).toBeVisible();
    expect(screen.getByText("已在线（占用中）")).toBeVisible();
    expect(screen.getAllByText("异常").length).toBeGreaterThan(0);
    expect(screen.getByText("升级中")).toBeVisible();
    expect(screen.getByText("升级失败")).toBeVisible();
    expect(screen.getByText("移除中")).toBeVisible();
    expect(screen.getByText("移除失败")).toBeVisible();
    const abnormalMetric = screen.getAllByText("异常")
      .find((element) => element.classList.contains("kpi-label"))
      ?.closest(".kpi-card") as HTMLElement;
    expect(within(abnormalMetric).getByText("6")).toBeVisible();
  });

  it("设备详情展示 CUA 节点字段并保留实时画面入口", async () => {
    server.use(
      http.get("/api/v1/pod-pool", () => HttpResponse.json(initialPool)),
      http.get("/api/v1/pod-pool/pod-alpha", () =>
        HttpResponse.json(initialPool.items[0]),
      ),
    );

    renderApp("/pods");

    const row = await screen.findByRole("row", { name: /pod-alpha/ });
    await user.click(within(row).getByRole("button", { name: "详情" }));
    const dialogTitle = await screen.findByRole("heading", { name: "设备详情" });
    expect(dialogTitle).toBeVisible();
    const dialog = dialogTitle.closest(".modal-panel") as HTMLElement;
    expect(dialog).toHaveClass("pod-detail-modal");

    expect(within(dialog).getByText("AI-OpenClaw-0LRt-000")).toBeVisible();
    expect(within(dialog).getByText("pod-alpha")).toBeVisible();
    expect(within(dialog).getByText("火山引擎 ECS")).toBeVisible();
    expect(within(dialog).getByText("cn-beijing / cn-beijing-a")).toBeVisible();
    expect(within(dialog).getByText("default")).toBeVisible();
    expect(within(dialog).getByText("172.31.0.38 / 115.191.65.249")).toBeVisible();
    expect(within(dialog).getByText("Ubuntu 24.04 with OpenClaw 64 bit / image-z0dpqndnmy8rpzcad9rz")).toBeVisible();
    expect(within(dialog).getByText("http://115.191.65.249:8910")).toBeVisible();
    expect(within(dialog).getByText("0.0.3 / 0.0.3")).toBeVisible();
    expect(within(dialog).getByText("已在线")).toBeVisible();
    expect(within(dialog).getByLabelText("CUA noVNC 实时画面")).toBeVisible();
    expect(within(dialog).getByRole("button", { name: "查看画面" })).toBeVisible();
    expect(sdkStart).not.toHaveBeenCalled();
  });

  it("非在线 CUA 节点禁用实时画面入口", async () => {
    const failedNode = {
      ...initialPool.items[0],
      pod_id: "pod-upgrade-failed",
      pod_name: "Upgrade Failed Node",
      pod_status_code: 6,
      status_name: "升级失败",
    };
    server.use(
      http.get("/api/v1/pod-pool", () =>
        HttpResponse.json({
          refreshed_at: "2026-07-26T08:00:00Z",
          items: [failedNode],
        }),
      ),
      http.get("/api/v1/pod-pool/pod-upgrade-failed", () =>
        HttpResponse.json(failedNode),
      ),
    );

    renderApp("/pods");

    const row = await screen.findByRole("row", { name: /pod-upgrade-failed/ });
    await user.click(within(row).getByRole("button", { name: "详情" }));
    const dialogTitle = await screen.findByRole("heading", { name: "设备详情" });
    const dialog = dialogTitle.closest(".modal-panel") as HTMLElement;

    expect(within(dialog).getByText("当前状态不支持查看实时画面：升级失败")).toBeVisible();
    expect(within(dialog).getByRole("button", { name: "查看画面" })).toBeDisabled();
  });

  it("实时画面播放器使用桌面横屏比例", () => {
    expect(STYLES).toMatch(/\.status-badge\.info\s*\{[^}]*background:\s*var\(--state-info-bg\);[^}]*color:\s*var\(--state-info-fg\);/);
    expect(STYLES).toMatch(
      /\.pod-detail-modal\s*\{[\s\S]*width:\s*min\(920px, calc\(100vw - 32px\)\);/,
    );
    expect(STYLES).toMatch(
      /\.cloud-phone-player\s*\{[\s\S]*aspect-ratio:\s*16 \/ 9;[\s\S]*max-width:\s*960px;[\s\S]*width:\s*min\(100%, 960px\);/,
    );
    expect(STYLES).toMatch(
      /\.cloud-phone-stream-fullscreen\s*\{[\s\S]*position:\s*fixed;[\s\S]*inset:\s*0;[\s\S]*z-index:\s*1200;/,
    );
    expect(STYLES).toMatch(
      /\.cloud-phone-stream-fullscreen\s+\.cloud-phone-player\s*\{[\s\S]*height:\s*auto;[\s\S]*max-height:\s*calc\(100vh - 96px\);[\s\S]*width:\s*min\(calc\(100vw - 48px\), calc\(\(100vh - 96px\) \* 16 \/ 9\)\);/,
    );
    expect(STYLES).toMatch(
      /\.cloud-phone-stream-fullscreen\s+\.cloud-phone-stream-header p,\s*\.cloud-phone-stream-fullscreen\s+\.stream-status-text\s*\{[^}]*display:\s*none;/,
    );
  });

  it("设备池列表使用更高的内部滚动区", async () => {
    server.use(
      http.get("/api/v1/pod-pool", () => HttpResponse.json(initialPool)),
    );

    renderApp("/pods");

    const table = await screen.findByRole("table");
    expect(table.closest(".device-table-card")).not.toBeNull();
    expect(STYLES).toMatch(
      /\.device-table-card\s*\{[^}]*display:\s*flex;[^}]*flex-direction:\s*column;[^}]*min-height:\s*min\(640px, calc\(100vh - 300px\)\);/,
    );
    expect(STYLES).toMatch(
      /\.device-table-card\s+\.table-wrap\s*\{[^}]*flex:\s*1;[^}]*min-height:\s*520px;[^}]*overflow:\s*auto;/,
    );
  });

  it("搜索无结果时保留列头并支持重新选择筛选值", async () => {
    server.use(
      http.get("/api/v1/pod-pool", () => HttpResponse.json(initialPool)),
    );

    renderApp("/pods");

    expect(await screen.findByRole("columnheader", { name: "状态" })).toBeVisible();
    await user.type(screen.getByPlaceholderText("搜索实例名称、ID、镜像或任务ID"), "不存在");

    expect(screen.getByText("无匹配结果，请调整搜索条件或表头筛选。")).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "状态" })).toBeVisible();

    await user.click(screen.getByLabelText("清空搜索"));
    expect(await screen.findByRole("row", { name: /AI-OpenClaw-0LRt-000/ })).toBeVisible();
  });

  it("在空池、加载失败和刷新失败时给出明确反馈", async () => {
    let refreshRequests = 0;
    server.use(
      http.get("/api/v1/pod-pool", () =>
        HttpResponse.json({ items: [], refreshed_at: null }),
      ),
      http.post("/api/v1/pod-pool/refresh", () => {
        refreshRequests += 1;
        return HttpResponse.json(
          {
            error: {
              code: "pod_pool_discovery_failed",
              message: "Pod pool discovery failed",
              request_id: "req-refresh-failed",
              details: {},
            },
          },
          { status: 502 },
        );
      }),
    );

    renderApp("/pods");

    expect(await screen.findByText("尚未发现云机")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "刷新" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Pod pool discovery failed",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("req-refresh-failed");
    expect(screen.getByText("尚未发现云机")).toBeVisible();
    await waitFor(() => expect(refreshRequests).toBe(1));
  });
});
