import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api/client";
import type { PodDetail, PodPoolItem, PodPoolResponse } from "../api/types";
import { BusinessLink as Link } from "../components/business-link";
import { CloudPhoneStreamPanel } from "../components/cloud-phone-stream-panel";
import { PageHeader } from "../components/page-header";

const POD_STATUS_CN: Record<number, { label: string; tone: string; pulse?: boolean }> = {
  1: { label: "创建中", tone: "queued", pulse: true },
  2: { label: "已在线", tone: "success" },
  3: { label: "已在线（占用中）", tone: "info" },
  4: { label: "异常", tone: "danger" },
  5: { label: "升级中", tone: "warning", pulse: true },
  6: { label: "升级失败", tone: "danger" },
  7: { label: "移除中", tone: "warning", pulse: true },
  8: { label: "移除失败", tone: "danger" },
};

const TASK_STATUS_CN: Record<string, { label: string; tone: string; pulse?: boolean }> = {
  queued: { label: "排队中", tone: "queued" },
  running: { label: "执行中", tone: "success", pulse: true },
  result_ready: { label: "已完成", tone: "info" },
  cancelled: { label: "已取消", tone: "danger" },
};

const PAGE_SIZE = 10;
function formatTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString("zh-CN") : "尚未检查";
}

function RefreshIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function SmartphoneIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect width="14" height="20" x="5" y="2" rx="2" ry="2" /><path d="M12 18h.01" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 6 6 18" /><path d="m6 6 12 12" />
    </svg>
  );
}

function StatusBadge({ label, tone, pulse }: { label: string; tone: string; pulse?: boolean }) {
  return (
    <span className={`status-badge ${tone}`}>
      <span className={`dot${pulse ? " inline-pulse" : ""}`} />
      {label}
    </span>
  );
}

function PodStatusBadge({ code, label }: { code: number; label?: string | null }) {
  const info = POD_STATUS_CN[code] ?? { label: "未知", tone: "queued" };
  return <StatusBadge label={label || info.label} tone={info.tone} pulse={info.pulse} />;
}

function providerLabel(value: string | null | undefined): string {
  if (value === "volc_ecs") return "火山引擎 ECS";
  return value ?? "—";
}

function copyText(value: string): void {
  void navigator.clipboard?.writeText(value);
}

function CopyButton({ value, label }: { value: string; label: string }) {
  return (
    <button
      type="button"
      className="copy-button"
      onClick={() => copyText(value)}
      title={`复制${label}`}
      aria-label={`复制${label}`}
    >
      <CopyIcon />
    </button>
  );
}

function hasBoundTask(pod: PodPoolItem): boolean {
  return Boolean(pod.task_id);
}

function isIdleInstance(pod: PodPoolItem): boolean {
  return pod.local_state === "available";
}

function isAbnormalInstance(pod: PodPoolItem): boolean {
  return pod.pod_status_code !== 2 && pod.pod_status_code !== 3;
}

function TaskStatusCell({ pod }: { pod: PodPoolItem }) {
  if (!pod.task_id || !pod.task_status) {
    return (
      <span style={{ fontSize: "0.8rem", color: "var(--mua-neutral-400)" }}>空闲</span>
    );
  }
  const info = TASK_STATUS_CN[pod.task_status] ?? { label: pod.task_status, tone: "queued" };
  return <StatusBadge label={info.label} tone={info.tone} pulse={info.pulse} />;
}

function CurrentTaskCell({ pod }: { pod: PodPoolItem }) {
  if (!pod.task_id) {
    return <span style={{ fontSize: "0.8rem", color: "var(--mua-neutral-400)" }}>—</span>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <Link
        to={`/tasks/${pod.task_id}`}
        className="mono"
        style={{
          fontSize: "0.75rem",
          color: "var(--mua-primary-700)",
          textDecoration: "none",
          whiteSpace: "nowrap",
        }}
        title={pod.task_id}
      >
        {pod.task_id}
      </Link>
      {pod.task_scenario && (
        <span style={{ fontSize: "0.7rem", color: "var(--mua-neutral-500)", whiteSpace: "nowrap" }}>
          {pod.task_scenario}
        </span>
      )}
    </div>
  );
}

function streamDisabledReason(pod: PodDetail): string | null {
  if (pod.pod_status_code === 2 || pod.pod_status_code === 3) return null;
  const status = pod.status_name ?? POD_STATUS_CN[pod.pod_status_code]?.label ?? "未知";
  return `当前状态不支持查看实时画面：${status}`;
}

function DetailModal({ podId, onClose }: { podId: string; onClose: () => void }) {
  const detail = useQuery({
    queryKey: ["pod-detail", podId],
    queryFn: () => api.get<PodDetail>(`/pod-pool/${podId}`),
    enabled: !!podId,
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel pod-detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>设备详情</h3>
          <button className="modal-close" onClick={onClose} type="button" aria-label="关闭">
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body">
          {detail.isPending && <p style={{ color: "var(--mua-neutral-500)" }}>加载中...</p>}
          {detail.isError && (
            <p style={{ color: "var(--state-danger-fg)" }}>
              {detail.error instanceof ApiError ? detail.error.message : "加载失败"}
            </p>
          )}
          {detail.data && <PodDetailContent data={detail.data} />}
        </div>
      </div>
    </div>
  );
}

function PodDetailContent({ data }: { data: PodDetail }) {
  const rows: Array<[string, string | number]> = [
    ["名称", data.pod_name],
    ["实例 ID", data.pod_id],
    ["来源", providerLabel(data.provider)],
    ["Region / 可用区", data.region || data.zone_id ? `${data.region ?? "—"} / ${data.zone_id ?? "—"}` : "—"],
    ["Project", data.project_name ?? "—"],
    ["内网 / 公网 IP", `${data.intranet_ip ?? "—"} / ${data.public_ip ?? data.eip_address ?? "—"}`],
    ["操作系统 / 镜像", `${data.os_name ?? data.image_name ?? "—"} / ${data.image_id ?? "—"}`],
    ["Agent 入口", data.agent_endpoint ?? "—"],
    ["插件 / 脚本版本", `${data.plugin_version ?? "—"} / ${data.script_version ?? "—"}`],
    ["状态", data.status_name ?? POD_STATUS_CN[data.pod_status_code]?.label ?? "未知"],
    ["添加 / 更新时间", `${formatTime(data.pod_created_at)} / ${formatTime(data.node_updated_at)}`],
  ];

  return (
    <div className="detail-sections">
      <div className="detail-section">
        <dl className="detail-grid">
          {rows.map(([k, v]) => (
            <div key={k} className="detail-row">
              <dt>{k}</dt>
              <dd className="mono" style={{ fontSize: "0.78rem" }}>{v}</dd>
            </div>
          ))}
        </dl>
      </div>
      {data.request_id && (
        <p style={{ fontSize: "0.7rem", color: "var(--mua-neutral-400)", marginTop: "0.75rem" }}>
          request_id: <code>{data.request_id}</code>
        </p>
      )}
      <CloudPhoneStreamPanel podId={data.pod_id} disabledReason={streamDisabledReason(data)} />
    </div>
  );
}

export function PodPoolPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [detailPodId, setDetailPodId] = useState<string | null>(null);

  const pool = useQuery({
    queryKey: ["pod-pool"],
    queryFn: () => api.get<PodPoolResponse>("/pod-pool"),
    refetchInterval: 3000,
  });
  const refresh = useMutation({
    mutationFn: () => api.post<PodPoolResponse>("/pod-pool/refresh"),
    onSuccess: (response) => {
      queryClient.setQueryData<PodPoolResponse>(["pod-pool"], response);
    },
  });

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!refresh.isPending) refresh.mutate();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [refresh.isPending, refresh.mutate]);

  const refreshError = refresh.error instanceof ApiError ? refresh.error : null;
  const allItems = pool.data?.items ?? [];

  const kpis = useMemo(() => {
    const total = allItems.length;
    const running = allItems.filter(hasBoundTask).length;
    const idle = allItems.filter(isIdleInstance).length;
    const abnormal = allItems.filter(isAbnormalInstance).length;
    return { total, running, idle, abnormal };
  }, [allItems]);

  const filteredItems = useMemo(() => {
    let items = allItems;
    if (statusFilter !== "all") {
      if (statusFilter === "running") items = items.filter(hasBoundTask);
      else if (statusFilter === "idle") items = items.filter(isIdleInstance);
      else if (statusFilter === "abnormal") items = items.filter(isAbnormalInstance);
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      items = items.filter(
        (p) =>
          p.pod_id.toLowerCase().includes(q) ||
          p.pod_name.toLowerCase().includes(q) ||
          (p.image_id && p.image_id.toLowerCase().includes(q)) ||
          (p.image_name && p.image_name.toLowerCase().includes(q)) ||
          (p.config_name && p.config_name.toLowerCase().includes(q)) ||
          (p.task_id && p.task_id.toLowerCase().includes(q))
      );
    }
    return items;
  }, [allItems, search, statusFilter]);

  useEffect(() => {
    setPage(1);
  }, [search, statusFilter]);

  const pageCount = Math.max(1, Math.ceil(filteredItems.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const pagedItems = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return filteredItems.slice(start, start + PAGE_SIZE);
  }, [filteredItems, safePage]);
  const pageStart = filteredItems.length === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const pageEnd = Math.min(safePage * PAGE_SIZE, filteredItems.length);

  const statusOptions = useMemo(
    () => [
      { value: "all", label: "全部", count: allItems.length },
      { value: "running", label: "运行中", count: allItems.filter(hasBoundTask).length },
      { value: "idle", label: "空闲", count: allItems.filter(isIdleInstance).length },
      { value: "abnormal", label: "异常", count: allItems.filter(isAbnormalInstance).length },
    ],
    [allItems],
  );

  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: "首页", to: "/tasks" }, { label: "设备池" }]}
        title="设备池"
        description="管理用于自动化测试任务执行的 CUA 节点"
        actions={
          <button
            className="secondary-button"
            disabled={refresh.isPending}
            type="button"
            onClick={() => refresh.mutate()}
          >
            <RefreshIcon />
            {refresh.isPending ? "刷新中..." : "刷新"}
          </button>
        }
      />

      {refreshError && (
        <div className="form-feedback error" role="alert">
          <p>{refreshError.message}</p>
          {refreshError.requestId && (
            <p className="request-id">request_id：<code>{refreshError.requestId}</code></p>
          )}
        </div>
      )}

      {pool.isPending && <p className="panel">正在加载设备池...</p>}
      {pool.isError && <p className="panel form-error">设备池加载失败，请稍后重试。</p>}

      {pool.data && (
        <>
          <div className="kpi-grid kpi-grid-flat">
            <div className="kpi-card kpi-card-flat">
              <div className="kpi-body">
                <span className="kpi-label">总实例</span>
                <span className="kpi-value">{kpis.total}</span>
                <span className="kpi-meta">共 {kpis.total} 台节点</span>
              </div>
            </div>
            <div className="kpi-card kpi-card-flat">
              <div className="kpi-body">
                <span className="kpi-label">运行中</span>
                <span className="kpi-value" style={{ color: "var(--state-success)" }}>{kpis.running}</span>
                <span className="kpi-meta">已绑定任务</span>
              </div>
            </div>
            <div className="kpi-card kpi-card-flat">
              <div className="kpi-body">
                <span className="kpi-label">空闲</span>
                <span className="kpi-value" style={{ color: "var(--state-info)" }}>{kpis.idle}</span>
                <span className="kpi-meta">实例运行中且无任务</span>
              </div>
            </div>
            <div className="kpi-card kpi-card-flat">
              <div className="kpi-body">
                <span className="kpi-label">异常</span>
                <span className="kpi-value" style={{ color: "var(--state-warning)" }}>{kpis.abnormal}</span>
                <span className="kpi-meta">非已在线状态</span>
              </div>
            </div>
          </div>

          <div className="device-filter-panel">
            <div className="device-filter-tabs" aria-label="设备状态筛选">
              {statusOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={`device-filter-tab${statusFilter === option.value ? " active" : ""}`}
                  onClick={() => setStatusFilter(option.value)}
                >
                  <span>{option.label}</span>
                  <strong>{option.count}</strong>
                </button>
              ))}
            </div>
            <div className="device-filter-tools">
              <div className="input-with-icon device-search">
                <span className="input-icon"><SearchIcon /></span>
                <input
                  type="text"
                  placeholder="搜索实例名称、ID、镜像或任务ID"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  style={{ paddingLeft: "32px", paddingRight: search ? "28px" : undefined }}
                />
                {search && (
                  <button
                    type="button"
                    className="search-clear-btn"
                    onClick={() => setSearch("")}
                    aria-label="清空搜索"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <circle cx="12" cy="12" r="10" />
                      <path d="m15 9-6 6" />
                      <path d="m9 9 6 6" />
                    </svg>
                  </button>
                )}
              </div>
              <div className="filter-count">
                <strong>{filteredItems.length}</strong> / {allItems.length} 台
              </div>
            </div>
          </div>

          {allItems.length === 0 ? (
            <section className="empty-state">
              <div className="empty-icon"><SmartphoneIcon /></div>
              <h2>尚未发现云机</h2>
              <p className="muted">请先在设置页保存 Computer Use 凭证和 AccountId，再刷新节点列表。</p>
              <Link to="/settings" className="primary-button" style={{ marginTop: "1rem", display: "inline-flex" }}>前往设置</Link>
            </section>
          ) : (
            <>
              <div className="table-card device-table-card">
                <div className="table-wrap">
                  <table className="devices-table">
                    <thead>
                      <tr>
                        <th>名称/ID</th>
                        <th>主 IPv4 地址</th>
                        <th>状态</th>
                        <th>任务状态</th>
                        <th>当前任务</th>
                        <th>CUA 套件</th>
                        <th>镜像</th>
                        <th>规格</th>
                        <th>来源</th>
                        <th>所在位置</th>
                        <th>实例 ID</th>
                        <th>添加时间</th>
                        <th>更新时间</th>
                        <th className="th-right">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pagedItems.length === 0 ? (
                        <tr>
                          <td className="table-empty-cell" colSpan={14}>
                            <div className="table-empty-row">
                              无匹配结果，请调整搜索条件或表头筛选。
                            </div>
                          </td>
                        </tr>
                      ) : pagedItems.map((pod) => (
                        <tr key={`${pod.product_id}:${pod.pod_id}`}>
                          <td>
                            <div className="device-identity">
                              <div className="device-identity-row">
                                <span className="device-name">{pod.pod_name}</span>
                                <CopyButton value={pod.pod_name} label="实例名" />
                              </div>
                              <div className="device-identity-row">
                                <span className="mono device-id">{pod.pod_id}</span>
                                <CopyButton value={pod.pod_id} label="实例ID" />
                              </div>
                            </div>
                          </td>
                          <td>
                            <div><span className="ip-tag">公网</span> {pod.public_ip ?? pod.eip_address ?? "—"}</div>
                            <div><span className="ip-tag">私网</span> {pod.intranet_ip ?? "—"}</div>
                          </td>
                          <td><PodStatusBadge code={pod.pod_status_code} label={pod.status_name} /></td>
                          <td><TaskStatusCell pod={pod} /></td>
                          <td><CurrentTaskCell pod={pod} /></td>
                          <td>{pod.plugin_version ?? "—"}</td>
                          <td>
                            <div style={{ fontSize: "0.82rem", color: "var(--mua-foreground)" }}>
                              {pod.os_name ?? pod.image_name ?? "—"}
                            </div>
                            {pod.image_id && <div className="mono" style={{ fontSize: "0.7rem", color: "var(--mua-neutral-500)", marginTop: "2px" }}>{pod.image_id}</div>}
                          </td>
                          <td>{pod.specification ?? pod.server_type_code ?? "—"}</td>
                          <td>{providerLabel(pod.provider)}</td>
                          <td>{pod.region || pod.zone_id ? `${pod.region ?? "—"} / ${pod.zone_id ?? "—"}` : "—"}</td>
                          <td className="mono">{pod.pod_id}</td>
                          <td>
                            {formatTime(pod.pod_created_at)}
                          </td>
                          <td>{formatTime(pod.node_updated_at ?? null)}</td>
                          <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                            <button
                              className="text-button"
                              type="button"
                              onClick={() => setDetailPodId(pod.pod_id)}
                              style={{ display: "inline-flex", alignItems: "center", gap: "4px", fontSize: "0.78rem" }}
                            >
                              <EyeIcon />
                              详情
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="device-pagination">
                  <span>
                    显示 {pageStart}-{pageEnd}，共 {filteredItems.length} 台
                  </span>
                  <div className="device-pagination-actions">
                    <button
                      type="button"
                      className="secondary-button compact"
                      disabled={safePage <= 1}
                      onClick={() => setPage((current) => Math.max(1, current - 1))}
                    >
                      上一页
                    </button>
                    <span className="device-page-indicator">
                      第 {safePage} / {pageCount} 页
                    </span>
                    <button
                      type="button"
                      className="secondary-button compact"
                      disabled={safePage >= pageCount}
                      onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
                    >
                      下一页
                    </button>
                  </div>
                </div>
              </div>
              {pool.data.refreshed_at && (
                <p style={{ fontSize: "0.75rem", color: "var(--mua-neutral-400)", marginTop: "0.75rem" }}>
                  最近刷新：{formatTime(pool.data.refreshed_at)}
                </p>
              )}
            </>
          )}
        </>
      )}

      {detailPodId && <DetailModal podId={detailPodId} onClose={() => setDetailPodId(null)} />}
    </>
  );
}
