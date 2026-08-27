import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";

import { ApiError, api } from "../api/client";
import { CopyButton } from "../components/copy-button";
import { RuntimeConfigSnapshot } from "../components/runtime-config-snapshot";
import { StatusBadge } from "../components/status-badge";
import { formatChinaDateTime, formatDurationSeconds, formatTaskElapsedTime } from "../utils/time";
import { failureTypeLabel } from "../utils/task-status";
import type {
  RuntimeScreenshot,
  Task,
  TaskRuntimeResponse,
  TestCase,
} from "../api/types";
import { mergeRuntimeThreadSteps, runtimeToolCount } from "../utils/runtime-trace";

function emptyFriendlyError(error: unknown) {
  if (!error) return null;
  if (error instanceof ApiError && error.message.includes("not configured")) return null;
  return error instanceof Error ? error.message : "任务加载失败";
}

const REMOTE_STATUS_LABEL: Record<number, string> = {
  1: "已创建",
  2: "运行中",
  3: "已完成",
  4: "取消中",
  5: "已取消",
  6: "失败",
  7: "已中断",
};

function statusText(value: number | null | undefined) {
  if (value == null) return "-";
  return REMOTE_STATUS_LABEL[value] ?? `状态 ${value}`;
}

function usageValue(value: number | string | undefined) {
  if (value == null || value === "") return "-";
  return String(value);
}

function MetricGlyph({
  type,
}: {
  type: "status" | "token-in" | "token-out" | "duration" | "steps";
}) {
  if (type === "status") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="7" />
        <path d="m8.5 12 2.2 2.2 4.8-5" />
      </svg>
    );
  }
  if (type === "token-in") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M4 7h9" />
        <path d="m10 4 3 3-3 3" />
        <rect x="13.5" y="5" width="6.5" height="14" rx="2" />
      </svg>
    );
  }
  if (type === "token-out") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <rect x="4" y="5" width="6.5" height="14" rx="2" />
        <path d="M10.5 7h9" />
        <path d="m16.5 4 3 3-3 3" />
      </svg>
    );
  }
  if (type === "duration") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="7" />
        <path d="M12 8v4l3 2" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="7" cy="7" r="2.2" />
      <circle cx="17" cy="7" r="2.2" />
      <circle cx="17" cy="17" r="2.2" />
      <path d="M9.2 7h5.6M17 9.2v5.6" />
    </svg>
  );
}

type ScreenshotEntry = {
  key: string;
  url: string;
  originalUrl: string | null;
  data: RuntimeScreenshot;
};

const TERMINAL_STATUSES = ["result_ready", "cancelled"];

function numericSuffix(key: string): number | null {
  const match = key.match(/-(\d+)$/);
  return match ? Number(match[1]) : null;
}

function compareScreenshotKeys(leftKey: string, rightKey: string) {
  const leftSuffix = numericSuffix(leftKey);
  const rightSuffix = numericSuffix(rightKey);
  if (leftSuffix !== null && rightSuffix !== null && leftSuffix !== rightSuffix) {
    return leftSuffix - rightSuffix;
  }
  return leftKey.localeCompare(rightKey);
}

function screenshotEntries(
  screenshots: Record<string, RuntimeScreenshot> | undefined,
): ScreenshotEntry[] {
  return Object.entries(screenshots ?? {})
    .sort(([leftKey], [rightKey]) => compareScreenshotKeys(leftKey, rightKey))
    .flatMap(([key, data]) => {
      const url = data.screenshot ?? data.original_screenshot;
      if (!url) return [];
      return [{
        key,
        url,
        originalUrl: data.original_screenshot ?? null,
        data,
      }];
    });
}

function remoteStatusCode(
  data: TaskRuntimeResponse | undefined,
  item: Task,
): number | null | undefined {
  const firstThreadTask = data?.thread_groups.flatMap((group) => group.tasks)[0];
  return data?.current_step?.status ?? item.remote_status_code ?? firstThreadTask?.status;
}

function currentPhaseLabel(data: TaskRuntimeResponse | undefined): string | null {
  if (data?.current_phase?.type !== "device_prepare") return null;
  if (data.current_phase.action === "reset") return "正在重置设备";
  if (data.current_phase.action === "reboot") return "正在重启设备";
  return null;
}

function isTerminalStatus(status: string) {
  return TERMINAL_STATUSES.includes(status);
}

function shouldCollapseCaseContent(value: string): boolean {
  return value.length > 240 || value.split(/\r?\n/).length > 6;
}

export function TaskOverviewPage() {
  const { taskId } = useParams();
  const [threadSteps, setThreadSteps] = useState<TaskRuntimeResponse["thread_steps"]>([]);
  const task = useQuery({
    enabled: Boolean(taskId),
    queryKey: ["task", taskId],
    queryFn: () => api.get<Task>(`/tasks/${taskId}`),
  });
  const runtime = useQuery({
    enabled: Boolean(taskId),
    queryKey: ["task-runtime", taskId],
    queryFn: () => api.get<TaskRuntimeResponse>(`/tasks/${taskId}/runtime`),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 3000;
      return isTerminalStatus(data.task.execution_status) ? false : 3000;
    },
  });

  const [nowMs, setNowMs] = useState(() => Date.now());
  const [selectedScreenshotIndex, setSelectedScreenshotIndex] = useState(0);
  const [caseContentExpanded, setCaseContentExpanded] = useState(false);
  const [failedScreenshots, setFailedScreenshots] = useState<Set<string>>(() => new Set());
  const [recordingFailed, setRecordingFailed] = useState(false);
  const loadedItem = runtime.data?.task ?? task.data ?? null;
  const caseDetail = useQuery({
    enabled: Boolean(loadedItem?.case_id),
    queryKey: ["task-case-content", loadedItem?.case_id],
    queryFn: () => api.get<TestCase>(`/cases/${loadedItem?.case_id ?? ""}`),
    retry: false,
  });
  const isTerminal = loadedItem ? isTerminalStatus(loadedItem.execution_status) : true;
  const result = runtime.data?.result ?? {
    summary: loadedItem?.result_summary ?? null,
    evidence: loadedItem?.result_evidence ?? [],
    recording_url: loadedItem?.recording_url ?? null,
    assets: loadedItem?.result_assets ?? {},
  };
  const resultEvidence = result.evidence ?? [];
  const screenshots = useMemo(
    () => screenshotEntries(result.assets.screenshots),
    [result.assets.screenshots],
  );
  const files = result.assets.files ?? [];
  const usage = result.assets.usage ?? {};
  const firstThreadTask = runtime.data?.thread_groups.flatMap((group) => group.tasks)[0];
  const phaseLabel = currentPhaseLabel(runtime.data);
  const visibleThreadSteps = isTerminal
    ? mergeRuntimeThreadSteps(threadSteps, runtime.data?.thread_steps ?? [])
    : [];
  const toolCount = isTerminal ? runtimeToolCount(visibleThreadSteps) : null;
  const remoteDurationSeconds = isTerminal && typeof result.assets.duration_ms === "number"
    ? result.assets.duration_ms / 1000
    : null;
  const durationText = remoteDurationSeconds !== null
    ? formatDurationSeconds(remoteDurationSeconds)
    : loadedItem
    ? formatTaskElapsedTime(
      loadedItem.execution_status,
      loadedItem.started_at,
      loadedItem.finished_at,
      nowMs,
    )
    : "-";
  const visibleScreenshots = useMemo(
    () => screenshots.filter((shot) => !failedScreenshots.has(shot.key)),
    [screenshots, failedScreenshots],
  );
  const selectedScreenshot = visibleScreenshots[selectedScreenshotIndex] ?? null;

  useEffect(() => {
    if (isTerminal || loadedItem?.execution_status !== "running") return;
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [isTerminal, loadedItem?.execution_status]);

  useEffect(() => {
    setThreadSteps([]);
  }, [taskId]);

  useEffect(() => {
    setCaseContentExpanded(false);
  }, [loadedItem?.case_id]);

  useEffect(() => {
    if (!runtime.data) return;
    if (!isTerminalStatus(runtime.data.task.execution_status)) return;
    setThreadSteps((previous) =>
      mergeRuntimeThreadSteps(previous, runtime.data.thread_steps ?? []),
    );
  }, [runtime.data]);

  useEffect(() => {
    if (selectedScreenshotIndex >= visibleScreenshots.length) {
      setSelectedScreenshotIndex(Math.max(0, visibleScreenshots.length - 1));
    }
  }, [visibleScreenshots.length, selectedScreenshotIndex]);

  if (task.isPending) return <div className="table-card"><p className="muted">加载中...</p></div>;
  const friendlyError = emptyFriendlyError(task.error);
  if (friendlyError) return <div className="table-card"><p className="form-error">{friendlyError}</p></div>;
  const item = loadedItem;
  if (!item) return <div className="table-card"><p className="muted">任务不存在</p></div>;

  return (
    <div className="overview-page runtime-dashboard">
      <section className="runtime-hero table-card">
        <div>
          <p className="eyebrow">运行总览</p>
          <h2>{item.scenario}</h2>
          <div className="runtime-identifiers muted">
            <div><span>TaskID</span> <code className="mono">{item.id}</code></div>
            {firstThreadTask?.run_id && <div><span>RunID</span> <code className="mono">{firstThreadTask.run_id}</code></div>}
            {item.remote_thread_id && <div><span>ThreadID</span> <code className="mono">{item.remote_thread_id}</code></div>}
          </div>
        </div>
        <div
          className="runtime-metric-strip runtime-metric-strip--bare runtime-metric-strip--full-labels"
          aria-label="运行元信息"
        >
          <div className="runtime-metric-pill status">
            <span className="runtime-metric-glyph">
              <MetricGlyph type="status" />
            </span>
            <span className="runtime-metric-copy">
              <span className="runtime-metric-label">
                {phaseLabel ? "当前阶段" : "远端状态"}
              </span>
              <strong>
                {phaseLabel ?? statusText(remoteStatusCode(runtime.data, item))}
              </strong>
            </span>
          </div>
          <div className="runtime-metric-pill token-in">
            <span className="runtime-metric-glyph">
              <MetricGlyph type="token-in" />
            </span>
            <span className="runtime-metric-copy">
              <span className="runtime-metric-label">输入 Tokens</span>
              <strong>{usageValue(usage.in_tokens)}</strong>
            </span>
          </div>
          <div className="runtime-metric-pill token-out">
            <span className="runtime-metric-glyph">
              <MetricGlyph type="token-out" />
            </span>
            <span className="runtime-metric-copy">
              <span className="runtime-metric-label">输出 Tokens</span>
              <strong>{usageValue(usage.out_tokens)}</strong>
            </span>
          </div>
          <div className="runtime-metric-pill duration">
            <span className="runtime-metric-glyph">
              <MetricGlyph type="duration" />
            </span>
            <span className="runtime-metric-copy">
              <span className="runtime-metric-label">运行总时间</span>
              <strong>{durationText}</strong>
            </span>
          </div>
          <div className="runtime-metric-pill steps">
            <span className="runtime-metric-glyph">
              <MetricGlyph type="steps" />
            </span>
            <span className="runtime-metric-copy">
              <span className="runtime-metric-label">执行步数</span>
              <strong>{toolCount ?? "-"}</strong>
            </span>
          </div>
        </div>
      </section>

      <div className="task-overview-layout">
        <section className="table-card runtime-card task-overview-result">
          <div className="section-heading">
            <h2>执行结果</h2>
            <div className="section-actions">
              <StatusBadge verdict={item.verdict} />
              {runtime.isError && <span className="muted small">使用本地缓存</span>}
            </div>
          </div>
          {result.summary ? (
            <p className="verdict-summary">{result.summary}</p>
          ) : (
            <p className="muted">暂未获取到结果摘要。</p>
          )}
          {resultEvidence.length > 0 && (
            <ul className="evidence-list compact">
              {resultEvidence.map((evidence, idx) => (
                <li key={`${idx}-${evidence}`} className="evidence-item">
                  <span className="evidence-index">{idx + 1}</span>
                  <span className="evidence-text">{evidence}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="table-card runtime-card task-overview-recording runtime-recording-card">
          <div className="section-heading">
            <h2>录制回放</h2>
          </div>
          {result.recording_url && !recordingFailed ? (
            <>
              <video
                src={result.recording_url}
                controls
                preload="metadata"
                onError={() => setRecordingFailed(true)}
              />
              <a className="primary-button" href={result.recording_url} target="_blank" rel="noreferrer">
                查看录制回放
              </a>
            </>
          ) : result.recording_url ? (
            <div className="runtime-asset-expired recording">
              <strong>录制回放已过期或无法访问</strong>
              <p>可重新执行任务生成新的录制和截图。</p>
            </div>
          ) : (
            <p className="muted">本次任务未返回 RecordingUrl。</p>
          )}
        </section>

        <section className="table-card runtime-card task-overview-screenshots">
          <div className="section-heading">
            <h2>执行截图</h2>
            <span className="muted small">
              {visibleScreenshots.length > 0
                ? `${selectedScreenshotIndex + 1} / ${visibleScreenshots.length}`
                : "暂无图片"}
            </span>
          </div>
          {selectedScreenshot ? (
            <div className="runtime-screenshot-viewer">
              <div className="runtime-screenshot-stage">
                {visibleScreenshots.length > 1 && (
                  <button
                    type="button"
                    className="runtime-screenshot-nav previous"
                    aria-label="上一张截图"
                    onClick={() =>
                      setSelectedScreenshotIndex((current) =>
                        current === 0 ? visibleScreenshots.length - 1 : current - 1,
                      )
                    }
                  >
                    ‹
                  </button>
                )}
                <img
                  src={selectedScreenshot.url}
                  alt={`截图 ${selectedScreenshotIndex + 1}`}
                  onError={() =>
                    setFailedScreenshots((current) =>
                      new Set(current).add(selectedScreenshot.key),
                    )
                  }
                />
                {visibleScreenshots.length > 1 && (
                  <button
                    type="button"
                    className="runtime-screenshot-nav next"
                    aria-label="下一张截图"
                    onClick={() =>
                      setSelectedScreenshotIndex((current) =>
                        current === visibleScreenshots.length - 1 ? 0 : current + 1,
                      )
                    }
                  >
                    ›
                  </button>
                )}
              </div>
              {visibleScreenshots.length > 1 && (
                <div className="runtime-screenshot-thumbs" aria-label="截图缩略图">
                  {visibleScreenshots.map((screenshot, idx) => (
                    <button
                      key={screenshot.key}
                      type="button"
                      className={idx === selectedScreenshotIndex ? "active" : undefined}
                      aria-label={`查看截图 ${idx + 1}`}
                      onClick={() => setSelectedScreenshotIndex(idx)}
                    >
                      <img
                        src={screenshot.url}
                        alt=""
                        onError={() =>
                          setFailedScreenshots((current) =>
                            new Set(current).add(screenshot.key),
                          )
                        }
                      />
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="muted">暂无图片。</p>
          )}

        </section>

        <section className="table-card runtime-card task-overview-files">
          <div className="section-heading">
            <h2>结果文件</h2>
            <span className="muted small">{files.length} 个文件</span>
          </div>
          {files.length > 0 ? (
            <ul className="runtime-file-list">
              {files.map((file) => <li key={file}>{file}</li>)}
            </ul>
          ) : (
            <p className="muted">暂无文件。</p>
          )}
        </section>

        <section
          className="table-card runtime-card task-overview-case"
          aria-label="用例内容"
        >
          <div className="section-heading">
            <div>
              <h2>用例内容</h2>
              {caseDetail.data && (
                <p className="muted small runtime-case-meta">
                  <span>{caseDetail.data.module ?? "未分组"}</span>
                  <code translate="no">{caseDetail.data.id}</code>
                </p>
              )}
            </div>
            {caseDetail.data?.content_markdown?.trim() && (
              <div className="section-actions">
                <CopyButton
                  value={caseDetail.data.content_markdown}
                  label="用例内容"
                />
                {shouldCollapseCaseContent(caseDetail.data.content_markdown) && (
                  <button
                    type="button"
                    className="text-button runtime-case-toggle"
                    aria-expanded={caseContentExpanded}
                    aria-label={caseContentExpanded ? "收起用例内容" : "展开用例内容"}
                    onClick={() => setCaseContentExpanded((current) => !current)}
                  >
                    {caseContentExpanded ? "收起" : "展开"}
                  </button>
                )}
              </div>
            )}
          </div>
          {caseDetail.isLoading ? (
            <p className="muted">正在加载用例内容...</p>
          ) : caseDetail.isError ? (
            <p className="muted">用例内容不可用。</p>
          ) : caseDetail.data?.content_markdown?.trim() ? (
            <>
              <strong className="runtime-case-title">
                {caseDetail.data.title}
              </strong>
              <pre
                className={`runtime-case-content${
                  caseContentExpanded ? " expanded" : ""
                }`}
              >
                {caseDetail.data.content_markdown}
              </pre>
            </>
          ) : (
            <p className="muted">暂无用例内容。</p>
          )}
        </section>

        <section className="table-card runtime-card task-overview-meta">
          <div className="section-heading">
            <h2>任务信息</h2>
          </div>
          <dl className="runtime-meta-grid">
            <div><dt>用例ID</dt><dd className="mono" title={item.case_id}>{item.case_id}</dd></div>
            <div><dt>设备ID</dt><dd className="mono" title={firstThreadTask?.pod_id ?? undefined}>{firstThreadTask?.pod_id ?? "-"}</dd></div>
            <div><dt>失败类型</dt><dd className={item.failure_type ? "form-error" : undefined}>{failureTypeLabel(item.failure_type)}</dd></div>
            <div><dt>创建时间</dt><dd>{formatChinaDateTime(item.created_at)}</dd></div>
            <div><dt>开始时间</dt><dd>{formatChinaDateTime(item.started_at)}</dd></div>
            <div><dt>完成时间</dt><dd>{formatChinaDateTime(item.finished_at)}</dd></div>
          </dl>
        </section>
        {runtime.data?.execution_config && (
          <RuntimeConfigSnapshot config={runtime.data.execution_config} />
        )}
      </div>
    </div>
  );
}
