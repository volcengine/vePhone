import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";

import { ApiError, api } from "../api/client";
import { CloudPhoneStreamPanel } from "../components/cloud-phone-stream-panel";
import type {
  RuntimeCurrentStep,
  RuntimeThreadStep,
  RuntimeToolCallResult,
  TaskRuntimeResponse,
} from "../api/types";
import { mergeRuntimeThreadSteps } from "../utils/runtime-trace";
import { formatChinaDateTime } from "../utils/time";

function emptyFriendlyError(error: unknown) {
  if (!error) return null;
  if (error instanceof ApiError && error.message.includes("not configured")) return null;
  return error instanceof Error ? error.message : "执行轨迹加载失败";
}

const TERMINAL_STATUSES = ["result_ready", "cancelled"];

const REMOTE_STATUS_LABEL: Record<number, { label: string; tone: string }> = {
  1: { label: "已创建", tone: "neutral" },
  2: { label: "运行中", tone: "running" },
  3: { label: "已完成", tone: "success" },
  4: { label: "取消中", tone: "warning" },
  5: { label: "已取消", tone: "neutral" },
  6: { label: "失败", tone: "danger" },
  7: { label: "已中断", tone: "danger" },
};

function remoteStatusInfo(value: number | null | undefined) {
  if (value == null) return { label: "-", tone: "neutral" };
  return REMOTE_STATUS_LABEL[value] ?? { label: `状态 ${value}`, tone: "neutral" };
}

function isTerminalStatus(status: string) {
  return TERMINAL_STATUSES.includes(status);
}

function currentStepSnapshot(step: RuntimeCurrentStep): RuntimeThreadStep {
  return {
    run_id: step.run_id,
    thread_id: step.thread_id,
    status: step.status,
    step_id: step.step_id,
    results: step.results,
  };
}

function parseTimestamp(ts: string | undefined): number {
  if (!ts) return 0;
  try {
    return new Date(ts).getTime();
  } catch {
    return 0;
  }
}

function toolSuccess(tool: RuntimeToolCallResult): boolean | null {
  const sr = tool.StepResult;
  if (!sr || typeof sr !== "object") return null;
  const innerStatus = toolInnerResultStatus(sr.Result);
  if (innerStatus != null) return innerStatus;
  if ("IsSuccess" in sr) return Boolean(sr.IsSuccess);
  return null;
}

function toolInnerResultStatus(result: unknown): boolean | null {
  if (typeof result !== "string" || !result.trim()) return null;
  try {
    const parsed = JSON.parse(result) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
    const value = parsed as Record<string, unknown>;
    if (value.status === "failure" || value.status === "failed") return false;
    if (value.status === "success") return true;
    if (value.error != null) return false;
  } catch {
    return null;
  }
  return null;
}

function toolResultText(tool: RuntimeToolCallResult): string | null {
  const sr = tool.StepResult;
  if (!sr || typeof sr !== "object") return null;
  const result = sr.Result;
  if (typeof result === "string") return result;
  if (result != null) return JSON.stringify(result, null, 2);
  return null;
}

type TimelineItem = {
  key: string;
  action: string;
  timestamp: string | undefined;
  param: Record<string, unknown> | undefined;
  stepResult: Record<string, unknown> | undefined;
  isSuccess: boolean | null;
  resultText: string | null;
  runId: string | null;
  isCurrent: boolean;
};

function buildTimeline(
  threadSteps: TaskRuntimeResponse["thread_steps"],
  currentStep: TaskRuntimeResponse["current_step"],
): TimelineItem[] {
  const items: TimelineItem[] = [];
  const seen = new Set<string>();

  for (const runStep of threadSteps) {
    for (let i = 0; i < runStep.results.length; i++) {
      const tool = runStep.results[i];
      const action = tool.Action ?? "unknown";
      const ts = tool.Timestamp;
      const key = `${runStep.run_id ?? ""}:${i}:${action}:${ts ?? ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      items.push({
        key,
        action,
        timestamp: ts,
        param: tool.Param,
        stepResult: tool.StepResult as Record<string, unknown> | undefined,
        isSuccess: toolSuccess(tool),
        resultText: toolResultText(tool),
        runId: runStep.run_id,
        isCurrent: false,
      });
    }
  }

  items.sort((a, b) => parseTimestamp(a.timestamp) - parseTimestamp(b.timestamp));

  if (currentStep && currentStep.results.length > 0) {
    const lastIdx = currentStep.results.length - 1;
    const latest = currentStep.results[lastIdx];
    const action = latest.Action ?? currentStep.step_id ?? "unknown";
    const ts = latest.Timestamp;
    const key = `current:${currentStep.step_id ?? ""}:${lastIdx}:${action}:${ts ?? ""}`;
    const existingIdx = items.findIndex((item) =>
      item.action === action && item.timestamp === ts && item.runId === currentStep.run_id,
    );
    if (existingIdx >= 0) {
      items[existingIdx] = { ...items[existingIdx], isCurrent: true };
    } else {
      items.push({
        key,
        action,
        timestamp: ts,
        param: latest.Param,
        stepResult: latest.StepResult as Record<string, unknown> | undefined,
        isSuccess: toolSuccess(latest),
        resultText: toolResultText(latest),
        runId: currentStep.run_id,
        isCurrent: true,
      });
    }
  }

  return items;
}

function formatToolTime(ts: string | undefined): string {
  if (!ts) return "-";
  return formatChinaDateTime(ts);
}

function ToolCallCard({ item, index }: { item: TimelineItem; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const successLabel = item.isSuccess === null
    ? null
    : item.isSuccess
      ? { text: "成功", cls: "success" }
      : { text: "失败", cls: "danger" };

  return (
    <div className={`trace-timeline-item ${item.isCurrent ? "current" : ""}`}>
      <div className="trace-timeline-dot">
        <span className={index === 0 ? "first" : ""} />
      </div>
      <div className="trace-timeline-content">
        <div className="trace-tool-header">
          <div className="trace-tool-title">
            <span className={`trace-tool-badge ${item.isCurrent ? "running" : ""}`}>
              {item.action}
            </span>
            {item.isCurrent && <span className="trace-tool-live"><span className="inline-pulse" /> 执行中</span>}
            {successLabel && !item.isCurrent && (
              <span className={`trace-tool-result ${successLabel.cls}`}>{successLabel.text}</span>
            )}
          </div>
          <span className="trace-tool-time mono">{formatToolTime(item.timestamp)}</span>
        </div>

        {(item.param || item.stepResult) && (
          <>
            <button
              type="button"
              className="trace-tool-toggle"
              onClick={() => setExpanded(v => !v)}
            >
              {expanded ? "收起详情" : "查看详情"}
            </button>
            {expanded && (
              <div className="trace-tool-details">
                {item.param && Object.keys(item.param).length > 0 && (
                  <div className="trace-tool-section">
                    <h4>参数</h4>
                    <pre>{JSON.stringify(item.param, null, 2)}</pre>
                  </div>
                )}
                {item.resultText && (
                  <div className="trace-tool-section">
                    <h4>结果</h4>
                    <pre>{item.resultText}</pre>
                  </div>
                )}
                {item.stepResult && !item.resultText && Object.keys(item.stepResult).length > 0 && (
                  <div className="trace-tool-section">
                    <h4>结果</h4>
                    <pre>{JSON.stringify(item.stepResult, null, 2)}</pre>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function TaskTracePage() {
  const { taskId } = useParams();
  const [stepSnapshots, setStepSnapshots] = useState<TaskRuntimeResponse["thread_steps"]>([]);
  const [showAllSteps, setShowAllSteps] = useState(false);
  const runtime = useQuery({
    enabled: Boolean(taskId),
    queryKey: ["task-runtime", taskId],
    queryFn: () => api.get<TaskRuntimeResponse>(`/tasks/${taskId}/runtime`),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 2000;
      return isTerminalStatus(data.task.execution_status) ? false : 2000;
    },
  });

  useEffect(() => {
    setStepSnapshots([]);
    setShowAllSteps(false);
  }, [taskId]);

  useEffect(() => {
    const currentStep = runtime.data?.current_step;
    if (!runtime.data) return;
    if (isTerminalStatus(runtime.data.task.execution_status)) {
      const threadSteps = runtime.data.thread_steps ?? [];
      if (threadSteps.length > 0) {
        setStepSnapshots((previous) => mergeRuntimeThreadSteps(previous, threadSteps));
        return;
      }
    }
    if (currentStep) {
      setStepSnapshots((previous) =>
        mergeRuntimeThreadSteps(previous, [currentStepSnapshot(currentStep)]),
      );
    }
  }, [runtime.data]);

  const currentStep = runtime.data?.current_step ?? null;
  const task = runtime.data?.task ?? null;
  const isRunning = task ? !isTerminalStatus(task.execution_status) : false;

  const timeline = useMemo(
    () => buildTimeline(stepSnapshots, isRunning ? currentStep : null),
    [stepSnapshots, currentStep, isRunning],
  );

  const stepCount = timeline.length;
  const hasHiddenSteps = stepCount > 20;
  const visibleTimeline = showAllSteps || !hasHiddenSteps
    ? timeline
    : timeline.slice(-20);
  const currentStepInfo = currentStep ? remoteStatusInfo(currentStep.status) : null;
  const streamPodId = runtime.data?.execution_config?.pod_id ?? null;

  if (runtime.isPending) return <div className="table-card"><p className="muted">正在加载执行轨迹...</p></div>;
  const friendlyError = emptyFriendlyError(runtime.error);
  if (friendlyError) return <div className="table-card"><p className="form-error">{friendlyError}</p></div>;
  if (!runtime.data) return <div className="table-card"><p className="muted">轨迹数据不可用</p></div>;

  return (
    <div className="runtime-dashboard trace-dashboard">
      <div className="trace-runtime-layout">
        <div className="trace-runtime-main">
          {isRunning && currentStep && (
            <section className="table-card runtime-card trace-current-step-card">
              <div className="section-heading">
                <h2>当前步骤</h2>
                <div className="section-actions">
                  <span className={`trace-step-status ${currentStepInfo?.tone ?? "neutral"}`}>
                    <span className="inline-pulse" />
                    {currentStepInfo?.label ?? "-"}
                  </span>
                  <span className="muted small">
                    <span className="inline-pulse" /> 自动刷新中
                  </span>
                </div>
              </div>
              <div className="trace-current-info">
                <div className="trace-current-step-id">
                  <span className="trace-tool-badge running">{currentStep.step_id ?? "等待调度"}</span>
                </div>
                <dl className="trace-current-meta">
                  <div><dt>RunID</dt><dd className="mono">{currentStep.run_id ?? "-"}</dd></div>
                  <div><dt>ThreadID</dt><dd className="mono">{currentStep.thread_id ?? "-"}</dd></div>
                </dl>
              </div>
              {currentStep.results.length > 0 && (
                <div className="trace-current-tool">
                  <span className="muted small">正在执行：</span>
                  <strong>{currentStep.results[currentStep.results.length - 1]?.Action ?? "-"}</strong>
                </div>
              )}
            </section>
          )}

          <section className="table-card runtime-card">
            <div className="section-heading">
              <h2>执行步骤详情</h2>
              <div className="section-actions">
                <span className="muted small">已保留 {stepCount} 步</span>
              </div>
            </div>

            {timeline.length === 0 ? (
              <p className="muted">暂无步骤详情。</p>
            ) : (
              <>
                <div className="trace-timeline">
                  {visibleTimeline.map((item, idx) => (
                    <ToolCallCard key={item.key} item={item} index={idx} />
                  ))}
                  {isRunning && visibleTimeline.length > 0 && (
                    <div className="trace-timeline-item pending">
                      <div className="trace-timeline-dot"><span className="pending-dot" /></div>
                      <div className="trace-timeline-content">
                        <span className="muted small">等待下一步操作...</span>
                      </div>
                    </div>
                  )}
                </div>
                {hasHiddenSteps && (
                  <div className="trace-step-toggle-row">
                    <button
                      type="button"
                      className="secondary-button compact"
                      onClick={() => setShowAllSteps((value) => !value)}
                    >
                      {showAllSteps ? "收起到最近 20 步" : `展开全部 ${stepCount} 步`}
                    </button>
                  </div>
                )}
              </>
            )}
          </section>
        </div>

        <aside className="trace-runtime-stream">
          <div className="table-card runtime-card">
            <div className="section-heading">
              <h2>实时画面</h2>
            </div>
            {streamPodId ? (
              <CloudPhoneStreamPanel podId={streamPodId} />
            ) : (
              <p className="muted">当前任务未绑定 Ecsid，无法打开实时画面。</p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
