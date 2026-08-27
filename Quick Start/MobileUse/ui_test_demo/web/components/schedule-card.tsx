import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, scheduleApi } from "../api/client";
import type {
  ScheduleEvent,
  TestPlanSchedule,
} from "../api/types";
import { formatChinaDateTime } from "../utils/time";
import { useBusinessNavigate } from "../business-context";
import { CronInput } from "./cron-input";
import { ConfirmDialog } from "./confirm-dialog";
import { PaginationControls } from "./pagination-controls";
import { BusinessLink } from "./business-link";
import { DeviceStrategySelector, type DeviceStrategy } from "./device-strategy-selector";
import {
  buildExecuteConfig,
  createExecutionConfigDraft,
  createExecutionConfigDraftFromOptions,
  DeviceWaitTimeoutField,
  ExecutionConfigFields,
  type ExecutionConfigDraft,
} from "./execution-config-form";

const TIMEZONE_OPTIONS = [
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Asia/Singapore",
  "UTC",
  "America/Los_Angeles",
  "America/New_York",
  "Europe/London",
  "Europe/Berlin",
];

const TRIGGER_TYPE_LABELS: Record<string, string> = {
  scheduled: "定时",
  manual: "手动",
  catchup: "补跑",
};

const TRIGGER_TYPE_STYLES: Record<string, { bg: string; color: string }> = {
  scheduled: { bg: "#eff6ff", color: "#2563eb" },
  manual: { bg: "#f3f4f6", color: "#6b7280" },
  catchup: { bg: "#fef3c7", color: "#92400e" },
};

function eventStatusInfo(event: ScheduleEvent): {
  label: string;
  color: string;
} {
  if (event.event_type === "triggered")
    return { label: "成功", color: "#16a34a" };
  if (event.event_type === "failed")
    return { label: "失败", color: "#dc2626" };
  return { label: "跳过", color: "#d97706" };
}

function formatPodIdentity(pod: { pod_name?: string; pod_id: string }): string {
  const name = pod.pod_name?.trim();
  return name && name !== pod.pod_id ? `${name} · ${pod.pod_id}` : pod.pod_id;
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      width="12"
      height="12"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 6l4 4 4-4" />
    </svg>
  );
}

function ScheduleEvents({ planId }: { planId: string }) {
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState(true);
  const events = useQuery({
    queryKey: ["schedule-events", planId, page],
    queryFn: () => scheduleApi.events(planId, page, 20),
    refetchInterval: 5000,
  });

  if (events.isLoading) {
    return (
      <div>
        <div className="schedule-history-toggle">
          <span className="schedule-history-title">触发历史</span>
        </div>
        <div className="plan-inline-skeleton" />
      </div>
    );
  }
  if (events.isError || !events.data) return null;
  if (events.data.total === 0) {
    return (
      <div>
        <div className="schedule-history-toggle">
          <span className="schedule-history-title">触发历史</span>
        </div>
        <div className="plan-case-empty">暂无触发记录</div>
      </div>
    );
  }

  return (
    <div>
      <button
        type="button"
        className="schedule-history-toggle"
        aria-expanded={expanded}
        aria-controls={`schedule-history-body-${planId}`}
        onClick={() => setExpanded((value) => !value)}
      >
        <ChevronDownIcon
          className={`schedule-history-chevron ${expanded ? "expanded" : ""}`}
        />
        <span className="schedule-history-title">触发历史</span>
        <span className="schedule-history-count">{events.data.total}</span>
      </button>
      {expanded && (
        <div id={`schedule-history-body-${planId}`}>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>触发时间</th>
                  <th style={{ textAlign: "center" }}>类型</th>
                  <th style={{ textAlign: "center" }}>状态</th>
                  <th style={{ textAlign: "center" }}>执行报告</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>
                {events.data.items.map((event) => {
                  const status = eventStatusInfo(event);
                  const triggerStyle =
                    TRIGGER_TYPE_STYLES[event.trigger_type]
                    || TRIGGER_TYPE_STYLES.scheduled;
                  return (
                    <tr key={event.id}>
                      <td>{formatChinaDateTime(event.fired_at)}</td>
                      <td style={{ textAlign: "center" }}>
                        <span
                          style={{
                            fontSize: 11,
                            padding: "1px 6px",
                            borderRadius: 4,
                            background: triggerStyle.bg,
                            color: triggerStyle.color,
                          }}
                        >
                          {TRIGGER_TYPE_LABELS[event.trigger_type]
                            || event.trigger_type}
                        </span>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <span style={{ color: status.color }}>
                          ● {status.label}
                        </span>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        {event.plan_execution_id ? (
                          <BusinessLink
                            to={`/task-reports/${event.plan_execution_id}`}
                            className="text-button"
                          >
                            查看报告
                          </BusinessLink>
                        ) : (
                          <span style={{ color: "#9ca3af" }}>—</span>
                        )}
                      </td>
                      <td style={{ fontSize: 12, color: "#6b7280" }}>
                        {event.skip_reason || event.error_message || "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {events.data.total > 20 && (
            <PaginationControls
              page={page}
              pageSize={20}
              total={events.data.total}
              onPageChange={setPage}
              onPageSizeChange={() => {}}
              showPageSize={false}
            />
          )}
        </div>
      )}
    </div>
  );
}

type ScheduleFormProps = {
  planId: string;
  existing?: TestPlanSchedule;
  onSave: () => void;
  onCancel: () => void;
};

function draftFromSchedule(
  existing?: TestPlanSchedule,
): ExecutionConfigDraft {
  if (!existing) return createExecutionConfigDraft();
  const cfg = existing.execution_config;
  const mode = (cfg.agent_config_mode ?? "global") as ExecutionConfigDraft["agent_config_mode"];
  if (mode === "custom" && cfg.agent_options) {
    const draft = createExecutionConfigDraftFromOptions(
      cfg.agent_options as never,
    );
    draft.device_wait_timeout_seconds =
      cfg.device_wait_timeout_seconds ?? draft.device_wait_timeout_seconds;
    return draft;
  }
  const draft = createExecutionConfigDraft();
  draft.agent_config_mode = mode;
  draft.timeout_seconds = cfg.timeout_seconds || draft.timeout_seconds;
  draft.device_wait_timeout_seconds =
    cfg.device_wait_timeout_seconds
    || draft.device_wait_timeout_seconds;
  return draft;
}

function ScheduleForm({
  planId,
  existing,
  onSave,
  onCancel,
}: ScheduleFormProps) {
  const queryClient = useQueryClient();
  const [cronExpr, setCronExpr] = useState(
    existing?.cron_expr || "0 9 * * *",
  );
  const [timezone, setTimezone] = useState(
    existing?.timezone || "Asia/Shanghai",
  );
  const [concurrency, setConcurrency] = useState(
    existing?.execution_config?.concurrency || 1,
  );
  const [deviceStrategy, setDeviceStrategy] = useState<DeviceStrategy>(
    (existing?.execution_config?.device_strategy as DeviceStrategy)
      || "automatic",
  );
  const [selectedPodIds, setSelectedPodIds] = useState<string[]>(
    existing?.execution_config?.pod_ids || [],
  );
  const [executionDraft, setExecutionDraft] =
    useState<ExecutionConfigDraft>(() => draftFromSchedule(existing));
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      if (deviceStrategy === "specified" && selectedPodIds.length === 0) {
        throw new Error("指定设备模式至少选择 1 台设备");
      }
      const built = buildExecuteConfig(executionDraft);
      if (!built.config) {
        throw new Error(built.error);
      }
      const payload = {
        cron_expr: cronExpr,
        timezone,
        execution_config: {
          test_type: "regression" as const,
          device_strategy: deviceStrategy,
          pod_ids: deviceStrategy === "specified" ? selectedPodIds : [],
          concurrency,
          device_wait_timeout_seconds:
            executionDraft.device_wait_timeout_seconds,
          timeout_seconds: built.config.timeout_seconds,
          agent_config_mode: built.config.agent_config_mode,
          agent_options: built.config.agent_options,
        },
      };
      if (existing) {
        return scheduleApi.update(planId, payload);
      }
      return scheduleApi.create(planId, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule", planId] });
      queryClient.invalidateQueries({
        queryKey: ["schedule-events", planId],
      });
      onSave();
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("保存失败");
      }
    },
  });

  return (
    <div
      style={{
        padding: "12px 0",
        borderTop: "1px solid var(--mua-border)",
        marginTop: 12,
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div>
          <label className="form-label">Cron 表达式</label>
          <CronInput
            value={cronExpr}
            timezone={timezone}
            onChange={setCronExpr}
            error={error}
          />
        </div>
        <div>
          <label className="form-label">时区</label>
          <select
            className="form-input"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
          >
            {TIMEZONE_OPTIONS.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <DeviceWaitTimeoutField
          id="schedule-device-wait-timeout-seconds"
          value={executionDraft.device_wait_timeout_seconds}
          onChange={(next) =>
            setExecutionDraft({
              ...executionDraft,
              device_wait_timeout_seconds: next,
            })}
        />
      </div>

      <div style={{ marginBottom: 16 }}>
        <DeviceStrategySelector
          strategy={deviceStrategy}
          onStrategyChange={setDeviceStrategy}
          concurrency={concurrency}
          onConcurrencyChange={setConcurrency}
          selectedPodIds={selectedPodIds}
          onSelectedPodIdsChange={setSelectedPodIds}
        />
      </div>

      <div style={{ marginBottom: 16 }}>
        <label className="form-label">Agent 配置</label>
        <ExecutionConfigFields
          value={executionDraft}
          onChange={setExecutionDraft}
          allowCaseDefault={false}
          showThreadId={false}
        />
      </div>

      {error && (
        <div
          className="form-error"
          style={{ marginBottom: 12 }}
          role="alert"
        >
          {error}
        </div>
      )}

      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          gap: 8,
          marginTop: 20,
        }}
      >
        <button
          type="button"
          className="secondary-button"
          onClick={onCancel}
        >
          取消
        </button>
        <button
          type="button"
          className="primary-button"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? "保存中…" : "保存调度"}
        </button>
      </div>
    </div>
  );
}

export function ScheduleCard({ planId }: { planId: string }) {
  const queryClient = useQueryClient();
  const navigate = useBusinessNavigate();
  const [editing, setEditing] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const schedule = useQuery({
    queryKey: ["schedule", planId],
    queryFn: () => scheduleApi.get(planId),
    retry: false,
    refetchInterval: (query) => {
      const state = query.state;
      if (state.error instanceof ApiError && state.error.status === 404) {
        return false;
      }
      return 10000;
    },
  });

  const enableMutation = useMutation({
    mutationFn: (enabled: boolean) =>
      enabled
        ? scheduleApi.enable(planId)
        : scheduleApi.disable(planId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule", planId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => scheduleApi.delete(planId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule", planId] });
      setDeleteOpen(false);
    },
  });

  if (schedule.isLoading) {
    return (
      <section className="plan-detail-section">
        <div className="plan-inline-skeleton" />
      </section>
    );
  }

  const hasSchedule = !schedule.isError && schedule.data;

  if (editing) {
    return (
      <section className="plan-detail-section">
        <div className="plan-section-heading">
          <div>
            <span className="section-kicker">定时调度</span>
            <h2>
              {hasSchedule ? "编辑定时调度" : "创建定时调度"}
            </h2>
          </div>
        </div>
        <ScheduleForm
          planId={planId}
          existing={schedule.data || undefined}
          onSave={() => setEditing(false)}
          onCancel={() => setEditing(false)}
        />
      </section>
    );
  }

  if (!hasSchedule) {
    return (
      <section className="plan-detail-section">
        <div className="plan-section-heading">
          <div>
            <span className="section-kicker">定时调度</span>
            <h2>定时调度</h2>
          </div>
          <button
            type="button"
            className="primary-button"
            onClick={() => setEditing(true)}
          >
            创建定时调度
          </button>
        </div>
        <div className="plan-case-empty">
          未配置定时调度。创建后系统将按 cron 表达式自动触发测试执行。
        </div>
      </section>
    );
  }

  const s = schedule.data!;

  function handleRunNow() {
    navigate(`/test-plans/${planId}/run`);
  }

  return (
    <section className="plan-detail-section">
      <div className="plan-section-heading">
        <div>
          <span className="section-kicker">定时调度</span>
          <h2
            style={{ display: "flex", alignItems: "center", gap: 8 }}
          >
            定时调度
            <span
              style={{
                fontSize: 12,
                padding: "2px 8px",
                borderRadius: 4,
                background: s.enabled ? "#dcfce7" : "#f3f4f6",
                color: s.enabled ? "#166534" : "#6b7280",
                fontWeight: 400,
              }}
            >
              {s.enabled ? "已启用" : "已禁用"}
            </span>
          </h2>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="secondary-button"
            onClick={handleRunNow}
          >
            立即执行
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() => setEditing(true)}
          >
            编辑
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={enableMutation.isPending}
            onClick={() => enableMutation.mutate(!s.enabled)}
          >
            {s.enabled ? "禁用" : "启用"}
          </button>
          <button
            type="button"
            className="secondary-button"
            style={{ color: "var(--state-error)" }}
            onClick={() => setDeleteOpen(true)}
          >
            删除
          </button>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
          marginBottom: 12,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 12,
              color: "var(--mua-neutral-500)",
              marginBottom: 2,
            }}
          >
            Cron 表达式
          </div>
          <div
            style={{
              fontFamily: "monospace",
              fontWeight: 500,
              fontSize: 14,
            }}
          >
            {s.cron_expr}
          </div>
        </div>
        <div>
          <div
            style={{
              fontSize: 12,
              color: "var(--mua-neutral-500)",
              marginBottom: 2,
            }}
          >
            时区
          </div>
          <div style={{ fontSize: 14 }}>{s.timezone}</div>
        </div>
        <div>
          <div
            style={{
              fontSize: 12,
              color: "var(--mua-neutral-500)",
              marginBottom: 2,
            }}
          >
            下次运行
          </div>
          <div style={{ fontWeight: 500, fontSize: 14 }}>
            {formatChinaDateTime(s.next_run_at)}
          </div>
        </div>
        <div>
          <div
            style={{
              fontSize: 12,
              color: "var(--mua-neutral-500)",
              marginBottom: 2,
            }}
          >
            上次运行
          </div>
          <div style={{ fontSize: 14 }}>
            {s.last_run_at ? formatChinaDateTime(s.last_run_at) : "—"}
          </div>
        </div>
      </div>

      <div
        style={{
          padding: "8px 12px",
          background: "var(--mua-neutral-50)",
          borderRadius: "var(--radius-sm)",
          fontSize: 12,
          display: "flex",
          gap: 24,
          marginBottom: 16,
          flexWrap: "wrap",
        }}
      >
        <span>
          设备策略：
          {s.execution_config.device_strategy === "automatic"
            ? "自动分配"
            : "指定设备"}
        </span>
        <span>并发度：{s.execution_config.concurrency}</span>
        {s.execution_config.device_strategy === "specified"
          && s.execution_config.pod_ids?.length > 0 && (
          <span>
            指定设备：{s.execution_config.pod_ids.length} 台
          </span>
        )}
        {s.execution_config.device_wait_timeout_seconds && (
          <span>
            等待超时：
            {s.execution_config.device_wait_timeout_seconds}s
          </span>
        )}
        {s.execution_config.timeout_seconds && (
          <span>
            任务超时：{s.execution_config.timeout_seconds}s
          </span>
        )}
        <span>
          Agent 配置：
          {s.execution_config.agent_config_mode === "global"
            ? "全局"
            : s.execution_config.agent_config_mode === "custom"
              ? "自定义"
              : "用例默认"}
        </span>
      </div>

      <ScheduleEvents planId={planId} />

      <ConfirmDialog
        open={deleteOpen}
        title="删除定时调度"
        description="确定要删除此定时调度吗？删除后将不再自动触发执行。"
        confirmLabel="删除"
        pendingLabel="删除中…"
        isPending={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate()}
        onClose={() => setDeleteOpen(false)}
      />
    </section>
  );
}
