import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";

import { ApiError, api } from "../api/client";
import { CopyButton } from "../components/copy-button";
import { RuntimeConfigSnapshot } from "../components/runtime-config-snapshot";
import { StatusBadge } from "../components/status-badge";
import { formatChinaDateTime, formatDurationSeconds, formatTaskElapsedTime } from "../utils/time";
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

const REMOTE_TASK_STATUS_LABEL: Record<number, string> = {
  1: "已创建",
  2: "运行中",
  3: "已完成",
  4: "取消中",
  5: "已取消",
  6: "失败",
  7: "已中断",
};

const REMOTE_RESULT_STATUS_LABEL: Record<number, string> = {
  0: "运行中",
  1: "成功",
  2: "失败",
  3: "成功",
  4: "已停止",
  5: "已停止",
  6: "失败",
};

function statusText(value: number | null | undefined, resultStatus = false) {
  if (value == null) return "-";
  const labels = resultStatus ? REMOTE_RESULT_STATUS_LABEL : REMOTE_TASK_STATUS_LABEL;
  return labels[value] ?? `状态 ${value}`;
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

type ScreenshotValidation = {
  signature: string;
  accessibleKeys: Set<string>;
};

const TERMINAL_STATUSES = ["result_ready", "cancelled"];
const SCREENSHOT_CHECK_TIMEOUT_MS = 8000;

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

function remoteStatusText(
  data: TaskRuntimeResponse | undefined,
  item: Task,
): string {
  if (isTerminalStatus(item.execution_status) && item.remote_status_code != null) {
    return statusText(item.remote_status_code, true);
  }
  const firstThreadTask = data?.thread_groups.flatMap((group) => group.tasks)[0];
  return statusText(data?.current_step?.status ?? item.remote_status_code ?? firstThreadTask?.status);
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
  const [previewScreenshotIndex, setPreviewScreenshotIndex] = useState<number | null>(null);
  const [caseContentExpanded, setCaseContentExpanded] = useState(false);
  const [failedScreenshots, setFailedScreenshots] = useState<Set<string>>(() => new Set());
  const [screenshotValidation, setScreenshotValidation] =
    useState<ScreenshotValidation | null>(null);
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
  const realtimeScreenshots = runtime.data?.result.assets.screenshots;
  const screenshots = useMemo(
    () => screenshotEntries(realtimeScreenshots),
    [realtimeScreenshots],
  );
  const screenshotSignature = useMemo(
    () => JSON.stringify(screenshots.map((screenshot) => [screenshot.key, screenshot.url])),
    [screenshots],
  );
  const screenshotCheckComplete =
    screenshotValidation?.signature === screenshotSignature;
  const screenshotCheckPending = screenshots.length > 0 && !screenshotCheckComplete;
  const returnedScreenshotCount = Object.keys(realtimeScreenshots ?? {}).length;
  const files = result.assets.files ?? [];
  const usage = result.assets.usage ?? {};
  const firstThreadTask = runtime.data?.thread_groups.flatMap((group) => group.tasks)[0];
  const visibleThreadSteps = isTerminal
    ? mergeRuntimeThreadSteps(threadSteps, runtime.data?.thread_steps ?? [])
    : [];
  const toolCount = isTerminal ? runtimeToolCount(visibleThreadSteps) : null;
  const totalSteps = typeof result.assets.total_steps === "number"
    ? result.assets.total_steps
    : null;
  const stepMetric = totalSteps ?? toolCount;
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
    () => screenshots.filter(
      (shot) =>
        screenshotCheckComplete
        && screenshotValidation.accessibleKeys.has(shot.key)
        && !failedScreenshots.has(shot.key),
    ),
    [failedScreenshots, screenshotCheckComplete, screenshotValidation, screenshots],
  );
  const selectedScreenshot = visibleScreenshots[selectedScreenshotIndex] ?? null;
  const previewScreenshot = previewScreenshotIndex === null
    ? null
    : visibleScreenshots[previewScreenshotIndex] ?? null;

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
    setSelectedScreenshotIndex(0);
    setPreviewScreenshotIndex(null);
    setFailedScreenshots(new Set());
    if (screenshots.length === 0) {
      setScreenshotValidation({
        signature: screenshotSignature,
        accessibleKeys: new Set(),
      });
      return;
    }

    let active = true;
    let remaining = screenshots.length;
    const accessibleKeys = new Set<string>();
    const cleanups: Array<() => void> = [];

    setScreenshotValidation(null);
    for (const screenshot of screenshots) {
      const image = new Image();
      let settled = false;
      const settle = (accessible: boolean) => {
        if (settled || !active) return;
        settled = true;
        if (accessible) accessibleKeys.add(screenshot.key);
        remaining -= 1;
        if (remaining === 0) {
          setScreenshotValidation({
            signature: screenshotSignature,
            accessibleKeys: new Set(accessibleKeys),
          });
        }
      };
      const timeout = window.setTimeout(
        () => settle(false),
        SCREENSHOT_CHECK_TIMEOUT_MS,
      );
      image.onload = () => {
        window.clearTimeout(timeout);
        settle(true);
      };
      image.onerror = () => {
        window.clearTimeout(timeout);
        settle(false);
      };
      cleanups.push(() => {
        window.clearTimeout(timeout);
        image.onload = null;
        image.onerror = null;
      });
      image.src = screenshot.url;
    }

    return () => {
      active = false;
      cleanups.forEach((cleanup) => cleanup());
    };
  }, [screenshotSignature, screenshots]);

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

  useEffect(() => {
    if (previewScreenshotIndex === null) return;
    if (previewScreenshotIndex < visibleScreenshots.length) return;
    setPreviewScreenshotIndex(null);
  }, [previewScreenshotIndex, visibleScreenshots.length]);

  useEffect(() => {
    if (previewScreenshotIndex === null) return;
    function closePreviewOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setPreviewScreenshotIndex(null);
    }
    window.addEventListener("keydown", closePreviewOnEscape);
    return () => window.removeEventListener("keydown", closePreviewOnEscape);
  }, [previewScreenshotIndex]);

  if (task.isPending) return <div className="table-card"><p className="muted">加载中...</p></div>;
  const friendlyError = emptyFriendlyError(task.error);
  if (friendlyError) return <div className="table-card"><p className="form-error">{friendlyError}</p></div>;
  const item = loadedItem;
  if (!item) return <div className="table-card"><p className="muted">任务不存在</p></div>;
  const runId = firstThreadTask?.run_id ?? item.remote_run_id;

  return (
    <div className="overview-page runtime-dashboard">
      <section className="runtime-hero table-card">
        <div>
          <p className="eyebrow">运行总览</p>
          <h2>{item.scenario}</h2>
          <div className="runtime-identifiers muted">
            <div><span>TaskID</span> <code className="mono">{item.id}</code></div>
            {runId && <div><span>RunID</span> <code className="mono">{runId}</code></div>}
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
              <span className="runtime-metric-label">远端状态</span>
              <strong>{remoteStatusText(runtime.data, item)}</strong>
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
              <strong>{stepMetric ?? "-"}</strong>
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

        <section className="table-card runtime-card task-overview-screenshots">
          <div className="section-heading">
            <h2>执行截图</h2>
            <span className="muted small">
              {screenshotCheckPending
                ? "检查中"
                : visibleScreenshots.length > 0
                ? `${selectedScreenshotIndex + 1} / ${visibleScreenshots.length}`
                : "暂无图片"}
            </span>
          </div>
          {(!runtime.data && !runtime.isError) || screenshotCheckPending ? (
            <p className="muted">正在加载执行截图...</p>
          ) : selectedScreenshot ? (
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
                <button
                  type="button"
                  className="runtime-screenshot-zoom-trigger"
                  aria-label={`放大截图 ${selectedScreenshotIndex + 1}`}
                  onClick={() => setPreviewScreenshotIndex(selectedScreenshotIndex)}
                >
                  <img
                    src={selectedScreenshot.url}
                    alt={`截图 ${selectedScreenshotIndex + 1}`}
                    onError={() =>
                      setFailedScreenshots((current) =>
                        new Set(current).add(selectedScreenshot.key),
                      )
                    }
                  />
                </button>
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
          ) : runtime.isError ? (
            <p className="muted">截图数据不可用。</p>
          ) : returnedScreenshotCount > 0 ? (
            <p className="muted">
              已返回 {returnedScreenshotCount} 张截图，但没有可访问 URL。
            </p>
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
            <div><dt>失败类型</dt><dd className={item.failure_type ? "form-error" : undefined}>{item.failure_type ?? "-"}</dd></div>
            <div><dt>创建时间</dt><dd>{formatChinaDateTime(item.created_at)}</dd></div>
            <div><dt>开始时间</dt><dd>{formatChinaDateTime(item.started_at)}</dd></div>
            <div><dt>完成时间</dt><dd>{formatChinaDateTime(item.finished_at)}</dd></div>
          </dl>
        </section>
        {runtime.data?.execution_config && (
          <RuntimeConfigSnapshot config={runtime.data.execution_config} />
        )}
      </div>
      {previewScreenshot && previewScreenshotIndex !== null && (
        <div
          className="modal-overlay runtime-screenshot-preview-overlay"
          role="presentation"
          onClick={() => setPreviewScreenshotIndex(null)}
        >
          <div
            className="runtime-screenshot-preview-panel"
            role="dialog"
            aria-modal="true"
            aria-label={`截图 ${previewScreenshotIndex + 1} 预览`}
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="modal-close runtime-screenshot-preview-close"
              aria-label="关闭截图预览"
              onClick={() => setPreviewScreenshotIndex(null)}
            >
              ×
            </button>
            <img
              src={previewScreenshot.url}
              alt={`截图 ${previewScreenshotIndex + 1}`}
            />
          </div>
        </div>
      )}
    </div>
  );
}
