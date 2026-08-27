import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError, api } from "../api/client";
import type { PodDetail, PodPoolItem, PodPoolResponse } from "../api/types";
import { BusinessLink as Link } from "../components/business-link";
import { CloudPhoneStreamPanel } from "../components/cloud-phone-stream-panel";
import { PageHeader } from "../components/page-header";

const POD_STATUS_CN: Record<number, { label: string; tone: string; pulse?: boolean }> = {
  0: { label: "开机中", tone: "queued", pulse: true },
  1: { label: "运行中", tone: "success" },
  2: { label: "已关机", tone: "queued" },
  3: { label: "关机中", tone: "warning", pulse: true },
  4: { label: "重启中", tone: "warning", pulse: true },
};

const TASK_STATUS_CN: Record<string, { label: string; tone: string; pulse?: boolean }> = {
  queued: { label: "排队中", tone: "queued" },
  running: { label: "执行中", tone: "success", pulse: true },
  result_ready: { label: "已完成", tone: "info" },
  cancelled: { label: "已取消", tone: "danger" },
  failed: { label: "失败", tone: "danger" },
  pass: { label: "通过", tone: "success" },
};

const LAYOUT_CN: Record<string, string> = {
  "single-display-landscape": "1080p 横屏",
  "single-display-portrait": "1080p 竖屏",
  "single-display-portrait-720p": "720p 竖屏",
};

const AOSP_CN: Record<string, string> = {
  "10": "AOSP 10",
  "11": "AOSP 11",
  "13": "AOSP 13",
};

const PAGE_SIZE = 10;
const INSTANCE_STATUS_OPTIONS = [1, 0, 3, 2, 4] as const;
const TASK_FILTER_OPTIONS = [
  { value: "idle", label: "空闲" },
  { value: "running", label: "执行中" },
  { value: "queued", label: "排队中" },
  { value: "result_ready", label: "已完成" },
  { value: "failed", label: "失败" },
  { value: "cancelled", label: "已取消" },
];
type HostAction = "reset" | "reboot" | "power_on" | "power_off";

function formatTime(value: string | null): string {
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

function FilterIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 4h18l-7 8v6l-4 2v-8L3 4Z" />
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

function PodStatusBadge({ code }: { code: number }) {
  const info = POD_STATUS_CN[code] ?? { label: "未知", tone: "queued" };
  return <StatusBadge label={info.label} tone={info.tone} pulse={info.pulse} />;
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
  return pod.pod_status_code === 2 || pod.pod_status_code === 3 || pod.pod_status_code === 4;
}

function canRunHostAction(pod: PodPoolItem, action: HostAction): boolean {
  if (action === "reboot") return pod.pod_status_code === 1;
  if (action === "power_off") return [0, 1, 4].includes(pod.pod_status_code);
  if (action === "power_on" || action === "reset") return pod.pod_status_code === 2;
  return false;
}

function taskFilterValue(pod: PodPoolItem): string {
  return pod.task_status ?? "idle";
}

function HeaderFilter({
  label,
  active,
  open,
  options,
  selected,
  onOpen,
  onClose,
  onToggle,
  onReset,
  onConfirm,
}: {
  label: string;
  active: boolean;
  open: boolean;
  options: Array<{ value: string; label: string }>;
  selected: string[];
  onOpen: () => void;
  onClose: () => void;
  onToggle: (value: string) => void;
  onReset: () => void;
  onConfirm: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open, onClose]);

  return (
    <div className="table-filter-header" ref={containerRef}>
      <span>{label}</span>
      <button
        type="button"
        className={`column-filter-button${active ? " active" : ""}`}
        onClick={onOpen}
        aria-label={`${label}筛选`}
      >
        <FilterIcon />
      </button>
      {open && (
        <div className="column-filter-popover">
          <div className="column-filter-options">
            {options.map((option) => (
              <label key={option.value} className="column-filter-option">
                <input
                  type="checkbox"
                  checked={selected.includes(option.value)}
                  onChange={() => onToggle(option.value)}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
          <div className="column-filter-actions">
            <button type="button" className="secondary-button compact" onClick={onReset}>
              重置
            </button>
            <button type="button" className="primary-button compact" onClick={onConfirm}>
              确定
            </button>
          </div>
        </div>
      )}
    </div>
  );
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
        className="monospace"
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
          <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>云机详情</h3>
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
  const displayLayout = LAYOUT_CN[data.display_layout_id ?? ""] ?? data.display_layout_id ?? "—";
  const aospVer = AOSP_CN[data.aosp_version ?? ""] ?? data.aosp_version ?? "—";
  const configType = data.config_type === 1 ? "正式" : data.config_type === 2 ? "试用" : "—";

  const sections: Array<{ title: string; rows: Array<[string, string | number]> }> = [
    {
      title: "基本信息",
      rows: [
        ["实例名称", data.pod_name],
        ["实例 ID", data.pod_id],
        ["业务 ID", data.product_id],
        ["创建时间", formatTime(data.pod_created_at)],
      ],
    },
    {
      title: "状态信息",
      rows: [
        ["实例状态", POD_STATUS_CN[data.pod_status_code]?.label ?? "未知"],
        ["推流状态", data.stream_status != null ? (data.stream_status === 0 ? "空闲" : data.stream_status === 1 ? "推流中" : "就绪") : "—"],
      ],
    },
    {
      title: "镜像与系统",
      rows: [
        ["镜像名称", data.image_name ?? "—"],
        ["镜像 ID", data.image_id ?? "—"],
        ["系统版本", aospVer],
        ["屏幕布局", displayLayout],
      ],
    },
    {
      title: "规格",
      rows: [
        ["规格名称", data.config_name ?? "—"],
        ["规格编码", data.config_code ?? "—"],
        ["规格类型", configType],
        ["云机规格", data.server_type_code ?? "—"],
        ["存储总量", data.data_size ?? "—"],
        ["存储已用", data.data_size_used ?? "—"],
      ],
    },
  ];

  return (
    <div className="detail-sections">
      {sections.map((sec) => (
        <div key={sec.title} className="detail-section">
          <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.8rem", fontWeight: 600, color: "var(--mua-neutral-700)", borderBottom: "1px solid var(--mua-border)", paddingBottom: "0.35rem" }}>
            {sec.title}
          </h4>
          <dl className="detail-grid">
            {sec.rows.map(([k, v]) => (
              <div key={k} className="detail-row">
                <dt>{k}</dt>
                <dd className="mono" style={{ fontSize: "0.78rem" }}>{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
      <CloudPhoneStreamPanel podId={data.pod_id} />
      {data.request_id && (
        <p style={{ fontSize: "0.7rem", color: "var(--mua-neutral-400)", marginTop: "0.75rem" }}>
          request_id: <code>{data.request_id}</code>
        </p>
      )}
    </div>
  );
}

type HostActionState = {
  action: HostAction;
  pod: PodPoolItem;
} | null;

type HostActionResult = {
  action: HostAction;
  product_id: string;
  pod_id: string;
  request_id: string | null;
  remote_task_id: string | null;
};

type HostActionStatus = {
  product_id: string;
  pod_id: string;
  remote_task_id: string;
  request_id: string | null;
  task_action: string | null;
  task_result: number | null;
  task_message: string | null;
  status: "running" | "succeeded" | "failed";
  jobs: Array<Record<string, unknown>>;
};

type RunningHostAction = {
  action: HostAction;
  pod: PodPoolItem;
  result: HostActionResult;
};

function hostActionLabel(action: HostAction) {
  if (action === "reset") return "重置";
  if (action === "reboot") return "重启";
  if (action === "power_on") return "开机";
  return "关机";
}

function hostActionProgressTitle(
  action: HostAction,
  pending: boolean,
  result: HostActionResult | null,
  status: HostActionStatus | undefined,
) {
  const label = hostActionLabel(action);
  if (!result) return pending ? `正在提交${label}请求` : `确认${label}实例`;
  if (status?.status === "succeeded") return `${label}完成`;
  if (status?.status === "failed") return `${label}失败`;
  return `正在${label}实例`;
}

function HostActionDialog({
  target,
  pending,
  result,
  status,
  error,
  onCancel,
  onConfirm,
}: {
  target: NonNullable<HostActionState>;
  pending: boolean;
  result: HostActionResult | null;
  status: HostActionStatus | undefined;
  error: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const label = hostActionLabel(target.action);
  const title = `${label}实例`;
  const progressTitle = hostActionProgressTitle(
    target.action,
    pending,
    result,
    status,
  );
  return (
    <div className="modal-overlay" onClick={pending ? undefined : onCancel}>
      <div
        className="modal-panel pod-action-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="modal-header">
          <h3>{title}</h3>
          <button
            className="modal-close"
            onClick={onCancel}
            type="button"
            aria-label="关闭"
            disabled={pending}
          >
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body">
          <div
            className={`pod-action-progress ${
              status?.status === "succeeded"
                ? "done"
                : status?.status === "failed"
                  ? "failed"
                  : pending || result
                    ? "pending"
                    : ""
            }`}
          >
            <span className="pod-action-progress-dot" aria-hidden="true" />
            <div>
              <strong>{progressTitle}</strong>
              <p>{target.pod.pod_name || target.pod.pod_id}</p>
            </div>
          </div>
          {!result && !pending && (
            <p className="form-hint">提交后将显示操作进展。</p>
          )}
          {result && (
            <dl className="pod-action-result">
              <div>
                <dt>request_id</dt>
                <dd>{result.request_id ?? "-"}</dd>
              </div>
              <div>
                <dt>remote_task_id</dt>
                <dd>{result.remote_task_id ?? "-"}</dd>
              </div>
              <div>
                <dt>进展</dt>
                <dd>{status?.task_result == null ? "查询中" : status.task_result}</dd>
              </div>
            </dl>
          )}
          {error && <p className="form-error" role="alert">{error}</p>}
        </div>
        <div className="modal-footer">
          {result ? (
            <button type="button" className="primary-button" onClick={onCancel}>
              关闭
            </button>
          ) : (
            <>
              <button
                type="button"
                className="secondary-button"
                onClick={onCancel}
                disabled={pending}
              >
                取消
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={onConfirm}
                disabled={pending}
              >
                {pending ? "提交中..." : `确认${label}`}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export function PodPoolPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [instanceStatusFilter, setInstanceStatusFilter] = useState<string[]>([]);
  const [taskStatusFilter, setTaskStatusFilter] = useState<string[]>([]);
  const [draftInstanceStatusFilter, setDraftInstanceStatusFilter] = useState<string[]>([]);
  const [draftTaskStatusFilter, setDraftTaskStatusFilter] = useState<string[]>([]);
  const [openColumnFilter, setOpenColumnFilter] = useState<"instance" | "task" | null>(null);
  const [page, setPage] = useState(1);
  const [detailPodId, setDetailPodId] = useState<string | null>(null);
  const [actionTarget, setActionTarget] = useState<HostActionState>(null);
  const [runningHostAction, setRunningHostAction] = useState<RunningHostAction | null>(null);
  const [actionError, setActionError] = useState("");

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
  const hostAction = useMutation({
    mutationFn: ({ pod, action }: { pod: PodPoolItem; action: HostAction }) =>
      api.post<HostActionResult>(`/pod-pool/${pod.pod_id}/${action.replace("_", "-")}`),
    onMutate: () => {
      setActionError("");
    },
    onSuccess: (response, variables) => {
      setRunningHostAction({
        action: response.action,
        pod: variables.pod,
        result: response,
      });
      void queryClient.invalidateQueries({ queryKey: ["pod-pool"] });
      refresh.mutate();
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "设备操作提交失败");
    },
  });
  const hostActionStatus = useQuery({
    enabled: Boolean(runningHostAction?.result.remote_task_id),
    queryKey: [
      "pod-host-action",
      runningHostAction?.pod.pod_id,
      runningHostAction?.result.remote_task_id,
    ],
    queryFn: () =>
      api.get<HostActionStatus>(
        `/pod-pool/${runningHostAction!.pod.pod_id}/host-actions/${runningHostAction!.result.remote_task_id}`,
      ),
    refetchInterval: (query) =>
      query.state.data?.status === "succeeded"
      || query.state.data?.status === "failed"
        ? false
        : 1000,
  });

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!refresh.isPending) refresh.mutate();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [refresh.isPending, refresh.mutate]);

  useEffect(() => {
    if (runningHostAction) return;
    const pod = (pool.data?.items ?? []).find((item) => item.active_host_action);
    if (!pod?.active_host_action) return;
    setRunningHostAction({
      action: pod.active_host_action.action,
      pod,
      result: {
        action: pod.active_host_action.action,
        product_id: pod.product_id,
        pod_id: pod.pod_id,
        request_id: pod.active_host_action.request_id,
        remote_task_id: pod.active_host_action.remote_task_id,
      },
    });
  }, [pool.data?.items, runningHostAction]);

  useEffect(() => {
    if (
      hostActionStatus.data?.status === "succeeded"
      || hostActionStatus.data?.status === "failed"
    ) {
      void queryClient.invalidateQueries({ queryKey: ["pod-pool"] });
    }
  }, [hostActionStatus.data?.status, queryClient]);

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
    if (instanceStatusFilter.length > 0) {
      items = items.filter((p) => instanceStatusFilter.includes(String(p.pod_status_code)));
    }
    if (taskStatusFilter.length > 0) {
      items = items.filter((p) => taskStatusFilter.includes(taskFilterValue(p)));
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
  }, [allItems, instanceStatusFilter, search, statusFilter, taskStatusFilter]);

  useEffect(() => {
    setPage(1);
  }, [instanceStatusFilter, search, statusFilter, taskStatusFilter]);

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

  function submitHostAction(pod: PodPoolItem, action: HostAction) {
    if (!canRunHostAction(pod, action)) return;
    setActionError("");
    if (hostActionStatus.data?.status === "succeeded" || hostActionStatus.data?.status === "failed") {
      setRunningHostAction(null);
    }
    setActionTarget({ pod, action });
  }

  function activeHostAction(pod: PodPoolItem): HostAction | null {
    if (hostAction.isPending && actionTarget?.pod.pod_id === pod.pod_id) {
      return actionTarget.action;
    }
    if (runningHostAction?.pod.pod_id === pod.pod_id) {
      const terminal = hostActionStatus.data?.status === "succeeded"
        || hostActionStatus.data?.status === "failed";
      return terminal ? null : runningHostAction.action;
    }
    return pod.active_host_action?.status === "running"
      ? pod.active_host_action.action
      : null;
  }

  function closeHostActionDialog() {
    if (hostAction.isPending) return;
    setActionTarget(null);
    setActionError("");
  }

  const dialogResult = actionTarget
    && runningHostAction?.pod.pod_id === actionTarget.pod.pod_id
    && runningHostAction.action === actionTarget.action
    ? runningHostAction.result
    : null;
  const dialogStatus = dialogResult ? hostActionStatus.data : undefined;

  const toggleDraftInstanceStatus = (value: string) => {
    setDraftInstanceStatusFilter((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    );
  };

  const toggleDraftTaskStatus = (value: string) => {
    setDraftTaskStatusFilter((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    );
  };

  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: "首页", to: "/tasks" }, { label: "设备池" }]}
        title="设备池"
        description="管理用于自动化测试任务执行的云手机实例"
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
      {actionError && (
        <div className="form-feedback error" role="alert">
          <p>{actionError}</p>
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
                <span className="kpi-meta">共 {kpis.total} 台云机</span>
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
                <span className="kpi-meta">关机中/已关机/重启中</span>
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
              <p className="muted">请先在设置页保存 Mobile Use 凭证和 Product ID，再刷新云机列表。</p>
              <Link to="/settings" className="primary-button" style={{ marginTop: "1rem", display: "inline-flex" }}>前往设置</Link>
            </section>
          ) : (
            <>
              <div className={`table-card device-table-card${openColumnFilter ? " filter-open" : ""}`}>
                <div className="table-wrap">
                  <table className="devices-table">
                    <thead>
                      <tr>
                        <th>实例名/ID</th>
                        <th>
                          <HeaderFilter
                            label="实例状态"
                            active={instanceStatusFilter.length > 0}
                            open={openColumnFilter === "instance"}
                            options={INSTANCE_STATUS_OPTIONS.map((value) => ({
                              value: String(value),
                              label: POD_STATUS_CN[value].label,
                            }))}
                            selected={draftInstanceStatusFilter}
                            onOpen={() => {
                              setDraftInstanceStatusFilter(instanceStatusFilter);
                              setOpenColumnFilter((current) => current === "instance" ? null : "instance");
                            }}
                            onClose={() => setOpenColumnFilter(null)}
                            onToggle={toggleDraftInstanceStatus}
                            onReset={() => {
                              setDraftInstanceStatusFilter([]);
                              setInstanceStatusFilter([]);
                              setOpenColumnFilter(null);
                            }}
                            onConfirm={() => {
                              setInstanceStatusFilter(draftInstanceStatusFilter);
                              setOpenColumnFilter(null);
                            }}
                          />
                        </th>
                        <th>
                          <HeaderFilter
                            label="任务状态"
                            active={taskStatusFilter.length > 0}
                            open={openColumnFilter === "task"}
                            options={TASK_FILTER_OPTIONS}
                            selected={draftTaskStatusFilter}
                            onOpen={() => {
                              setDraftTaskStatusFilter(taskStatusFilter);
                              setOpenColumnFilter((current) => current === "task" ? null : "task");
                            }}
                            onClose={() => setOpenColumnFilter(null)}
                            onToggle={toggleDraftTaskStatus}
                            onReset={() => {
                              setDraftTaskStatusFilter([]);
                              setTaskStatusFilter([]);
                              setOpenColumnFilter(null);
                            }}
                            onConfirm={() => {
                              setTaskStatusFilter(draftTaskStatusFilter);
                              setOpenColumnFilter(null);
                            }}
                          />
                        </th>
                        <th>当前任务</th>
                        <th>镜像ID/名称</th>
                        <th>系统/屏幕</th>
                        <th>云机规格</th>
                        <th>创建时间</th>
                        <th className="th-right sticky-actions-column">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pagedItems.length === 0 ? (
                        <tr>
                          <td className="table-empty-cell" colSpan={9}>
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
                            <PodStatusBadge code={pod.pod_status_code} />
                          </td>
                          <td><TaskStatusCell pod={pod} /></td>
                          <td><CurrentTaskCell pod={pod} /></td>
                          <td>
                            <div style={{ fontSize: "0.82rem", color: "var(--mua-foreground)" }}>
                              {pod.image_id ?? pod.image_name ?? "—"}
                            </div>
                            {pod.image_name && pod.image_id && (
                              <div className="mono" style={{ fontSize: "0.7rem", color: "var(--mua-neutral-500)", marginTop: "2px" }}>
                                {pod.image_name}
                              </div>
                            )}
                          </td>
                          <td>
                            <div className="system-screen-cell">
                              {AOSP_CN[pod.aosp_version ?? ""] ?? pod.aosp_version ?? "—"}
                              {pod.display_layout_id && (
                                <span> / {LAYOUT_CN[pod.display_layout_id] ?? pod.display_layout_id}</span>
                              )}
                            </div>
                          </td>
                          <td>
                            <div style={{ fontSize: "0.82rem", color: "var(--mua-foreground)" }}>
                              {pod.config_name ?? "—"}
                              {pod.config_type === 2 && (
                                <span style={{
                                  marginLeft: "4px",
                                  fontSize: "0.65rem",
                                  padding: "1px 5px",
                                  borderRadius: "3px",
                                  background: "var(--state-queued-bg)",
                                  color: "var(--state-queued-fg)",
                                }}>试用</span>
                              )}
                            </div>
                            {pod.server_type_code && (
                              <div className="mono" style={{ fontSize: "0.7rem", color: "var(--mua-neutral-500)", marginTop: "2px" }}>
                                {pod.server_type_code}
                              </div>
                            )}
                          </td>
                          <td style={{ fontSize: "0.78rem", color: "var(--mua-neutral-500)", whiteSpace: "nowrap" }}>
                            {formatTime(pod.pod_created_at)}
                          </td>
                          <td className="device-actions-cell sticky-actions-column">
                            <div className="device-actions">
                              <button
                                className="text-button"
                                type="button"
                                onClick={() => submitHostAction(pod, "reset")}
                                disabled={!canRunHostAction(pod, "reset") || Boolean(activeHostAction(pod))}
                                aria-label="重置设备"
                              >
                                重置
                              </button>
                              <button
                                className="text-button"
                                type="button"
                                onClick={() => submitHostAction(pod, "power_on")}
                                disabled={!canRunHostAction(pod, "power_on") || Boolean(activeHostAction(pod))}
                                aria-label="开机设备"
                              >
                                开机
                              </button>
                              <button
                                className="text-button"
                                type="button"
                                onClick={() => submitHostAction(pod, "power_off")}
                                disabled={!canRunHostAction(pod, "power_off") || Boolean(activeHostAction(pod))}
                                aria-label="关机设备"
                              >
                                关机
                              </button>
                              <button
                                className="text-button"
                                type="button"
                                onClick={() => submitHostAction(pod, "reboot")}
                                disabled={!canRunHostAction(pod, "reboot") || Boolean(activeHostAction(pod))}
                                aria-label="重启设备"
                              >
                                重启
                              </button>
                              <button
                                className="text-button"
                                type="button"
                                onClick={() => setDetailPodId(pod.pod_id)}
                              >
                                详情
                              </button>
                            </div>
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
      {actionTarget && (
        <HostActionDialog
          target={actionTarget}
          pending={hostAction.isPending}
          result={dialogResult}
          status={dialogStatus}
          error={actionError}
          onCancel={closeHostActionDialog}
          onConfirm={() =>
            hostAction.mutate({
              pod: actionTarget.pod,
              action: actionTarget.action,
            })}
        />
      )}
    </>
  );
}
