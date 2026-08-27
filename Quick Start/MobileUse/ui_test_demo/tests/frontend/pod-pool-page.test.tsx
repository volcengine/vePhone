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
  active_host_action: null,
};

const initialPool: PodPoolResponse = {
  refreshed_at: "2026-07-26T08:00:00Z",
  items: [
    {
      ...baseItem,
      product_id: "product-alpha",
      pod_id: "pod-alpha",
      pod_name: "Alpha Phone",
      pod_status_code: 1,
      discovery_state: "active",
      local_state: "available",
      last_seen_at: "2026-07-26T08:00:00Z",
      last_checked_at: "2026-07-26T08:00:01Z",
      task_id: null,
      task_status: null,
      task_scenario: null,
      active_host_action: null,
    },
    {
      ...baseItem,
      product_id: "product-alpha",
      pod_id: "pod-leased",
      pod_name: "Leased Phone",
      pod_status_code: 1,
      discovery_state: "active",
      local_state: "leased",
      last_seen_at: "2026-07-26T08:00:00Z",
      last_checked_at: "2026-07-26T08:00:01Z",
      task_id: "task-running",
      task_status: "running",
      task_scenario: "test-scenario",
      active_host_action: null,
    },
    {
      ...baseItem,
      product_id: "product-alpha",
      pod_id: "pod-stale-running",
      pod_name: "Stale Running Phone",
      pod_status_code: 1,
      discovery_state: "stale",
      local_state: "stale",
      last_seen_at: "2026-07-26T07:00:00Z",
      last_checked_at: null,
      task_id: null,
      task_status: null,
      task_scenario: null,
      active_host_action: null,
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
      pod_status_code: 2,
      discovery_state: "stale",
      local_state: "stale",
      last_seen_at: "2026-07-26T09:00:00Z",
      last_checked_at: null,
      task_id: null,
      task_status: null,
      task_scenario: null,
      active_host_action: null,
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
          pod_status_code: 1,
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
          pod_status_code: 1,
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
    expect(within(screen.getByRole("row", { name: /pod-auto/ })).getByText("空闲")).toBeVisible();

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
    expect(screen.getByText("管理用于自动化测试任务执行的云手机实例")).toBeVisible();
    expect(await screen.findByRole("columnheader", { name: "实例状态" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "当前任务" })).toBeVisible();
    expect(screen.queryByRole("combobox", { name: "按云机规格筛选" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "实例状态筛选" }));
    expect(screen.getByLabelText("已关机")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "任务状态筛选" }));
    expect(screen.getByLabelText("执行中")).toBeVisible();
    expect(screen.queryByRole("button", { name: "申请新实例" })).not.toBeInTheDocument();
    expect(within(await screen.findByRole("row", { name: /pod-alpha/ })).getByText("空闲")).toBeVisible();
    expect(screen.getByText("pod-alpha")).toBeVisible();
    expect(screen.getAllByRole("button", { name: "复制实例ID" }).length).toBeGreaterThan(0);
    expect(screen.getByText("显示 1-3，共 3 台")).toBeVisible();
    const idleMetric = screen.getAllByText("空闲")
      .find((element) => element.classList.contains("kpi-label"))
      ?.closest(".kpi-card") as HTMLElement;
    expect(within(idleMetric).getByText("1")).toBeVisible();
    expect(screen.getByRole("link", { name: "task-running" })).toHaveAttribute(
      "href",
      "/biz/biz_default/tasks/task-running",
    );
    expect(screen.getByText("test-scenario")).toBeVisible();
    expect(screen.getAllByText("运行中").length).toBeGreaterThan(0);
    const alphaRow = within(screen.getByRole("row", { name: /pod-alpha/ }));
    expect(alphaRow.getByRole("button", { name: "重置设备" })).toBeDisabled();
    expect(alphaRow.getByRole("button", { name: "开机设备" })).toBeDisabled();
    expect(alphaRow.getByRole("button", { name: "关机设备" })).not.toBeDisabled();
    expect(alphaRow.getByRole("button", { name: "重启设备" })).not.toBeDisabled();
    const detailButton = alphaRow.getByRole("button", { name: "详情" });
    expect(detailButton).toBeVisible();
    expect(detailButton.querySelector("svg")).not.toBeInTheDocument();
    expect(STYLES).toContain(".devices-table .device-actions-cell");
    expect(STYLES).toContain("justify-content: center;");
    expect(STYLES).toContain(".devices-table .sticky-actions-column");
    expect(STYLES).toContain("right: 0;");
    expect(STYLES).toContain("width: var(--device-actions-column-width);");
    expect(STYLES).toMatch(/\.devices-table thead th:not\(:first-child\):not\(\.sticky-actions-column\)\s*{[^}]*z-index:\s*1;/);
    expect(STYLES).toMatch(/\.devices-table th:first-child\s*{[^}]*z-index:\s*12;/);
    expect(STYLES).toMatch(/\.devices-table thead \.sticky-actions-column\s*{[^}]*z-index:\s*13;/);

    await user.click(screen.getByRole("button", { name: "刷新" }));

    expect(await screen.findByRole("row", { name: /pod-beta/ })).toBeVisible();
    expect(screen.getByText("已关机")).toBeVisible();
    expect(screen.queryByRole("row", { name: /pod-alpha/ })).not.toBeInTheDocument();
    expect(refreshRequests).toBe(1);
  });

  it("操作列支持重置和重启实例", async () => {
    const actions: string[] = [];
    let resetPollCount = 0;
    let rebootPollCount = 0;
    const operationPool: PodPoolResponse = {
      ...initialPool,
      items: [
        {
          ...initialPool.items[0],
          pod_id: "pod-offline",
          pod_name: "Offline Phone",
          pod_status_code: 2,
          local_state: "unavailable",
        },
        initialPool.items[0],
      ],
    };
    server.use(
      http.get("/api/v1/pod-pool", () => HttpResponse.json(operationPool)),
      http.post("/api/v1/pod-pool/refresh", () => HttpResponse.json(operationPool)),
      http.post("/api/v1/pod-pool/pod-offline/reset", ({ request }) => {
        expectCsrf(request);
        actions.push("reset");
        return HttpResponse.json({
          action: "reset",
          product_id: "product-alpha",
          pod_id: "pod-offline",
          request_id: "req-reset",
          remote_task_id: "task-reset",
        });
      }),
      http.get("/api/v1/pod-pool/pod-offline/host-actions/task-reset", () => {
        resetPollCount += 1;
        return HttpResponse.json({
          product_id: "product-alpha",
          pod_id: "pod-offline",
          remote_task_id: "task-reset",
          request_id: "req-task-reset",
          task_action: "ResetPod",
          task_result: resetPollCount > 1 ? 100 : 10,
          task_message: "",
          status: resetPollCount > 1 ? "succeeded" : "running",
          jobs: [{ PodId: "pod-alpha", Status: resetPollCount > 1 ? 100 : 10 }],
        });
      }),
      http.post("/api/v1/pod-pool/pod-alpha/reboot", ({ request }) => {
        expectCsrf(request);
        actions.push("reboot");
        return HttpResponse.json({
          action: "reboot",
          product_id: "product-alpha",
          pod_id: "pod-alpha",
          request_id: "req-reboot",
          remote_task_id: "task-reboot",
        });
      }),
      http.get("/api/v1/pod-pool/pod-alpha/host-actions/task-reboot", () => {
        rebootPollCount += 1;
        return HttpResponse.json({
          product_id: "product-alpha",
          pod_id: "pod-alpha",
          remote_task_id: "task-reboot",
          request_id: "req-task-reboot",
          task_action: "RebootPod",
          task_result: 100,
          task_message: "",
          status: "succeeded",
          jobs: [{ PodId: "pod-alpha", Status: 100 }],
        });
      }),
    );

    renderApp("/pods");

    const offlineRow = await screen.findByRole("row", { name: /pod-offline/ });
    await user.click(within(offlineRow).getByRole("button", { name: "重置设备" }));
    const resetDialog = await screen.findByRole("dialog", { name: "重置实例" });
    expect(within(resetDialog).getByText("Offline Phone")).toBeVisible();
    expect(within(resetDialog).getByText("提交后将显示操作进展。")).toBeVisible();
    await user.click(within(resetDialog).getByRole("button", { name: "确认重置" }));
    expect(await within(resetDialog).findByText("正在重置实例")).toBeVisible();
    expect(within(offlineRow).getByText("已关机")).toBeVisible();
    expect(within(offlineRow).getByRole("button", { name: "重置设备" })).toBeDisabled();
    expect(within(offlineRow).getByRole("button", { name: "重启设备" })).toBeDisabled();
    expect(within(resetDialog).getByText("req-reset")).toBeVisible();
    await user.click(within(resetDialog).getAllByRole("button", { name: "关闭" }).at(-1)!);
    expect(screen.queryByRole("dialog", { name: "重置实例" })).not.toBeInTheDocument();
    expect(within(offlineRow).getByText("已关机")).toBeVisible();
    expect(within(offlineRow).getByRole("button", { name: "重置设备" })).toBeDisabled();
    expect(within(offlineRow).getByRole("button", { name: "重启设备" })).toBeDisabled();
    await waitFor(() =>
      expect(within(offlineRow).getByRole("button", { name: "重置设备" })).not.toBeDisabled(),
    );
    expect(within(offlineRow).getByRole("button", { name: "重启设备" })).toBeDisabled();

    const runningRow = within(screen.getByRole("row", { name: /pod-alpha/ }));
    await user.click(runningRow.getByRole("button", { name: "重启设备" }));
    const rebootDialog = await screen.findByRole("dialog", { name: "重启实例" });
    expect(within(rebootDialog).getByText("Alpha Phone")).toBeVisible();
    await user.click(within(rebootDialog).getByRole("button", { name: "确认重启" }));
    expect(await within(rebootDialog).findByText("重启完成")).toBeVisible();

    await waitFor(() => expect(actions).toEqual(["reset", "reboot"]));
    expect(resetPollCount).toBeGreaterThanOrEqual(2);
    expect(rebootPollCount).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText(/请求已提交。 request_id/)).not.toBeInTheDocument();
  });

  it("使用后端持久化的操作记录禁用重置和重启按钮", async () => {
    server.use(
      http.get("/api/v1/pod-pool", () =>
        HttpResponse.json({
          ...initialPool,
          items: [
            {
              ...initialPool.items[0],
              active_host_action: {
                action: "reboot",
                request_id: "req-existing-reboot",
                remote_task_id: "task-existing-reboot",
                status: "running",
                task_result: null,
                task_message: null,
              },
            },
          ],
        }),
      ),
      http.get("/api/v1/pod-pool/pod-alpha/host-actions/task-existing-reboot", () =>
        HttpResponse.json({
          product_id: "product-alpha",
          pod_id: "pod-alpha",
          remote_task_id: "task-existing-reboot",
          request_id: "req-existing-reboot-status",
          task_action: "RebootPod",
          task_result: 10,
          task_message: "",
          status: "running",
          jobs: [{ PodId: "pod-alpha", Status: 10 }],
        }),
      ),
    );

    renderApp("/pods");

    const row = await screen.findByRole("row", { name: /pod-alpha/ });
    expect(within(row).getByText("运行中")).toBeVisible();
    expect(within(row).getByRole("button", { name: "重置设备" })).toBeDisabled();
    expect(within(row).getByRole("button", { name: "开机设备" })).toBeDisabled();
    expect(within(row).getByRole("button", { name: "关机设备" })).toBeDisabled();
    expect(within(row).getByRole("button", { name: "重启设备" })).toBeDisabled();
  });

  it("根据实例状态启用开机、关机、重启和重置按钮", async () => {
    server.use(
      http.get("/api/v1/pod-pool", () =>
        HttpResponse.json({
          ...initialPool,
          items: [
            {
              ...initialPool.items[0],
              pod_id: "pod-running",
              pod_name: "Running Phone",
              pod_status_code: 1,
              local_state: "available",
            },
            {
              ...initialPool.items[0],
              pod_id: "pod-offline",
              pod_name: "Offline Phone",
              pod_status_code: 2,
              local_state: "unavailable",
            },
            {
              ...initialPool.items[0],
              pod_id: "pod-booting",
              pod_name: "Booting Phone",
              pod_status_code: 0,
              local_state: "unavailable",
            },
            {
              ...initialPool.items[0],
              pod_id: "pod-rebooting",
              pod_name: "Rebooting Phone",
              pod_status_code: 4,
              local_state: "unavailable",
            },
          ],
        }),
      ),
    );

    renderApp("/pods");

    const running = within(await screen.findByRole("row", { name: /pod-running/ }));
    expect(running.getByRole("button", { name: "重置设备" })).toBeDisabled();
    expect(running.getByRole("button", { name: "开机设备" })).toBeDisabled();
    expect(running.getByRole("button", { name: "关机设备" })).not.toBeDisabled();
    expect(running.getByRole("button", { name: "重启设备" })).not.toBeDisabled();

    const offline = within(screen.getByRole("row", { name: /pod-offline/ }));
    expect(offline.getByRole("button", { name: "重置设备" })).not.toBeDisabled();
    expect(offline.getByRole("button", { name: "开机设备" })).not.toBeDisabled();
    expect(offline.getByRole("button", { name: "关机设备" })).toBeDisabled();
    expect(offline.getByRole("button", { name: "重启设备" })).toBeDisabled();

    const booting = within(screen.getByRole("row", { name: /pod-booting/ }));
    expect(booting.getByRole("button", { name: "关机设备" })).not.toBeDisabled();
    expect(booting.getByRole("button", { name: "开机设备" })).toBeDisabled();
    expect(booting.getByRole("button", { name: "重启设备" })).toBeDisabled();
    expect(booting.getByRole("button", { name: "重置设备" })).toBeDisabled();

    const rebooting = within(screen.getByRole("row", { name: /pod-rebooting/ }));
    expect(rebooting.getByRole("button", { name: "关机设备" })).not.toBeDisabled();
    expect(rebooting.getByRole("button", { name: "开机设备" })).toBeDisabled();
    expect(rebooting.getByRole("button", { name: "重启设备" })).toBeDisabled();
    expect(rebooting.getByRole("button", { name: "重置设备" })).toBeDisabled();
  });

  it("排队中任务状态使用统一徽章样式", async () => {
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
              pod_status_code: 1,
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
    const queuedBadge = within(row).getByText("排队中");
    expect(queuedBadge).toHaveClass("status-badge", "queued");
    expect(queuedBadge).not.toHaveAttribute("style");
    expect(queuedBadge.querySelector(".dot")).toBeInTheDocument();
  });

  it("在云机详情中打开实时画面并在关闭时释放 SDK", async () => {
    server.use(
      http.get("/api/v1/pod-pool", () => HttpResponse.json(initialPool)),
      http.get("/api/v1/pod-pool/pod-alpha", () =>
        HttpResponse.json(initialPool.items[0]),
      ),
      http.post("/api/v1/pod-pool/pod-alpha/stream-session", ({ request }) => {
        expectCsrf(request);
        return HttpResponse.json({
          account_id: "2100000000000000000",
          product_id: "product-alpha",
          pod_id: "pod-alpha",
          user_id: "mua-admin",
          token: {
            AccessKeyID: "AKTP_TEMP",
            SecretAccessKey: "temporary-secret",
            SessionToken: "session-token",
            CurrentTime: "2026-08-03T10:00:00+08:00",
            ExpiredTime: "2026-08-03T10:10:00+08:00",
          },
        });
      }),
    );

    renderApp("/pods");

    const row = await screen.findByRole("row", { name: /pod-alpha/ });
    await user.click(within(row).getByRole("button", { name: "详情" }));
    expect(await screen.findByRole("heading", { name: "云机详情" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "云机详情" }).closest(".modal-panel"))
      .toHaveClass("pod-detail-modal");
    await user.click(screen.getByRole("button", { name: "查看画面" }));

    expect(await screen.findByText("实时画面已连接")).toBeVisible();
    const streamPanel = screen.getByLabelText("云手机实时画面");
    const player = document.querySelector(".cloud-phone-player");
    expect(streamPanel).not.toHaveClass("cloud-phone-stream-fullscreen");
    expect(sdkStart).toHaveBeenCalledWith({
      productId: "product-alpha",
      podId: "pod-alpha",
      token: {
        AccessKeyID: "AKTP_TEMP",
        SecretAccessKey: "temporary-secret",
        SessionToken: "session-token",
        CurrentTime: "2026-08-03T10:00:00+08:00",
        ExpiredTime: "2026-08-03T10:10:00+08:00",
      },
      rotation: "portrait",
      mute: true,
      audioAutoPlay: true,
    });

    await user.click(screen.getByRole("button", { name: "放大实时画面" }));
    expect(streamPanel).toHaveClass("cloud-phone-stream-fullscreen");
    expect(player).toBe(document.querySelector(".cloud-phone-player"));
    expect(screen.getByRole("button", { name: "退出全屏" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "关闭画面" }));

    await waitFor(() => expect(sdkStop).toHaveBeenCalledTimes(1));
    expect(sdkDestroy).toHaveBeenCalledTimes(1);
  });

  it("实时画面播放器使用竖屏手机比例", () => {
    expect(STYLES).toMatch(
      /\.pod-detail-modal\s*\{[\s\S]*width:\s*min\(920px, calc\(100vw - 32px\)\);/,
    );
    expect(STYLES).toMatch(
      /\.cloud-phone-player\s*\{[\s\S]*aspect-ratio:\s*9 \/ 16;[\s\S]*max-width:\s*360px;[\s\S]*width:\s*min\(100%, 360px\);/,
    );
    expect(STYLES).toMatch(
      /\.cloud-phone-stream-fullscreen\s*\{[\s\S]*position:\s*fixed;[\s\S]*inset:\s*0;[\s\S]*z-index:\s*1200;/,
    );
    expect(STYLES).toMatch(
      /\.cloud-phone-stream-fullscreen\s+\.cloud-phone-player\s*\{[\s\S]*height:\s*min\(calc\(100vh - 96px\), 900px\);[\s\S]*max-width:\s*calc\(100vw - 48px\);/,
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

  it("筛选无结果时保留列头并支持重新选择筛选值", async () => {
    server.use(
      http.get("/api/v1/pod-pool", () => HttpResponse.json(initialPool)),
    );

    renderApp("/pods");

    expect(await screen.findByRole("columnheader", { name: "实例状态" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "实例状态筛选" }));
    await user.click(screen.getByLabelText("重启中"));
    await user.click(screen.getByRole("button", { name: "确定" }));

    expect(screen.getByText("无匹配结果，请调整搜索条件或表头筛选。")).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "实例状态" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "实例状态筛选" }));
    expect(screen.getByLabelText("运行中")).toBeVisible();
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
