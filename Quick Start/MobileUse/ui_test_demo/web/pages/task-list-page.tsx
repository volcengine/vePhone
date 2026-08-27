import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError, api } from "../api/client";
import type {
  Task,
  TaskListPage,
  TaskOperatorListResponse,
  TaskStats,
  Verdict,
} from "../api/types";
import { CopyButton } from "../components/copy-button";
import { BusinessLink as Link } from "../components/business-link";
import { MetricCard } from "../components/metric-card";
import { PageHeader } from "../components/page-header";
import { SingleSelect } from "../components/single-select";
import { StatusBadge } from "../components/status-badge";
import { formatChinaDateTime, formatTaskElapsedTime, recentWindowStartIso } from "../utils/time";

const STATUS_FILTERS = [
  { value: "all", label: "全部状态" },
  { value: "queued", label: "排队中" },
  { value: "running", label: "执行中" },
  { value: "result_ready", label: "已完成" },
  { value: "cancelled", label: "已取消" },
] as const;

const RESULT_FILTERS = [
  { value: "all", label: "全部结果" },
  { value: "pass", label: "成功" },
  { value: "fail", label: "失败" },
] as const;

const REVIEW_FILTERS = [
  { value: "all", label: "全部审核" },
  { value: "unreviewed", label: "待审核" },
  { value: "pass", label: "复核通过" },
  { value: "fail", label: "复核失败" },
] as const;

const REVIEW_RESULT_OPTIONS = [
  { value: "pass", label: "复核通过" },
  { value: "fail", label: "复核失败" },
] as const;

const TIME_FILTERS = [
  { value: "all", label: "全部时间" },
  { value: "1d", label: "最近一天" },
  { value: "3d", label: "最近3天" },
  { value: "7d", label: "最近一周" },
  { value: "30d", label: "最近一个月" },
] as const;

const TIME_FILTER_DAYS: Record<string, number> = {
  "1d": 1,
  "3d": 3,
  "7d": 7,
  "30d": 30,
};

const PAGE_SIZE = 20;

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12h14M12 5v14" />
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

function RefreshIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

function SmartphoneIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect width="14" height="20" x="5" y="2" rx="2" ry="2" /><path d="M12 18h.01" />
    </svg>
  );
}

function CheckCircleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

function AlertCircleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" /><line x1="12" x2="12" y1="8" y2="12" /><line x1="12" x2="12.01" y1="16" y2="16" />
    </svg>
  );
}

function ManualReviewIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  );
}

function ListIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="8" x2="21" y1="6" y2="6" /><line x1="8" x2="21" y1="12" y2="12" /><line x1="8" x2="21" y1="18" y2="18" /><line x1="3" x2="3.01" y1="6" y2="6" /><line x1="3" x2="3.01" y1="12" y2="12" /><line x1="3" x2="3.01" y1="18" y2="18" />
    </svg>
  );
}

function manualReviewLabel(reviewResult: Verdict | null) {
  if (reviewResult === "pass") return "复核通过";
  if (reviewResult === "fail") return "复核失败";
  return "待审核";
}

function verdictLabel(verdict: Verdict | null) {
  if (verdict === "pass") return "成功";
  if (verdict === "fail") return "失败";
  return "-";
}

function ManualReviewBadge({ task }: { task: Task }) {
  if (task.execution_status !== "result_ready") {
    return <span className="result-empty">-</span>;
  }

  const tone = task.review_result === "pass"
    ? "success"
    : task.review_result === "fail"
      ? "danger"
      : "warning";

  return (
    <span
      className={`status-badge ${tone}`}
      title={task.reviewed_by ? `审核人：${task.reviewed_by}` : undefined}
    >
      <span className="dot" />
      {manualReviewLabel(task.review_result ?? null)}
    </span>
  );
}

export function TaskListPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [resultFilter, setResultFilter] = useState<string>("all");
  const [reviewFilter, setReviewFilter] = useState<string>("all");
  const [operatorFilter, setOperatorFilter] = useState<string>("all");
  const [timeFilter, setTimeFilter] = useState<string>("all");
  const [createdAfterFilter, setCreatedAfterFilter] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [actionError, setActionError] = useState<string | null>(null);
  const [manualRefreshing, setManualRefreshing] = useState(false);
  const [cancelRequestedTaskId, setCancelRequestedTaskId] = useState<string | null>(null);
  const [reviewingTask, setReviewingTask] = useState<Task | null>(null);
  const [reviewResult, setReviewResult] = useState<Verdict>("pass");
  const [reviewNote, setReviewNote] = useState("");

  const queryString = (() => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(PAGE_SIZE));
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (resultFilter !== "all") params.set("verdict", resultFilter);
    if (reviewFilter !== "all") params.set("review_result", reviewFilter);
    if (operatorFilter !== "all") params.set("operator", operatorFilter);
    if (createdAfterFilter) {
      params.set("created_after", createdAfterFilter);
    }
    if (search) params.set("search", search);
    return params.toString();
  })();

  const tasks = useQuery({
    queryKey: ["tasks", queryString],
    queryFn: () => api.get<TaskListPage>(`/tasks?${queryString}`),
    refetchInterval: 3000,
  });

  const stats = useQuery({
    queryKey: ["task-stats"],
    queryFn: () => api.get<TaskStats>("/tasks/stats"),
    refetchInterval: 5000,
  });

  const operators = useQuery({
    queryKey: ["task-operators"],
    queryFn: () => api.get<TaskOperatorListResponse>("/tasks/operators"),
  });

  const cancelTask = useMutation({
    mutationFn: (taskId: string) => api.post<Task>(`/tasks/${taskId}/cancel`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["task-stats"] });
    },
    onError: (error) => {
      setCancelRequestedTaskId(null);
      setActionError(error instanceof ApiError ? error.message : "取消任务失败");
    },
  });

  const reviewTask = useMutation({
    mutationFn: (payload: { taskId: string; reviewResult: Verdict; reviewNote: string }) =>
      api.put<Task>(`/tasks/${payload.taskId}/review`, {
        review_result: payload.reviewResult,
        review_note: payload.reviewNote.trim() || null,
      }),
    onSuccess: () => {
      setReviewingTask(null);
      setReviewNote("");
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["task-stats"] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "保存人工审核失败");
    },
  });

  const items = tasks.data?.items ?? [];
  const total = tasks.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const kpis = {
    total: stats.data?.total ?? 0,
    running: stats.data?.running ?? 0,
    queued: stats.data?.queued ?? 0,
    passRate: stats.data?.pass_rate ?? 0,
    manualReviewFailRate: stats.data?.manual_review_fail_rate ?? 0,
    manualReviewFailCount: stats.data?.manual_review_fail_count ?? 0,
    manualReviewTotal: stats.data?.manual_review_total ?? 0,
  };

  const hasFilter = statusFilter !== "all"
    || resultFilter !== "all"
    || reviewFilter !== "all"
    || operatorFilter !== "all"
    || timeFilter !== "all"
    || Boolean(search);

  const operatorOptions = [
    { value: "all", label: "全部操作者" },
    ...(operators.data?.items ?? []).map((operator) => ({
      value: operator,
      label: operator,
    })),
  ];

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  function resetFilters() {
    setStatusFilter("all");
    setResultFilter("all");
    setReviewFilter("all");
    setOperatorFilter("all");
    setTimeFilter("all");
    setCreatedAfterFilter(null);
    setSearch("");
    setSearchInput("");
    setPage(1);
  }

  function handleCancel(taskId: string) {
    if (!confirm("确认取消此任务吗？正在运行的任务会调用远端 CancelTask 接口。")) {
      return;
    }
    setActionError(null);
    setCancelRequestedTaskId(taskId);
    cancelTask.mutate(taskId);
  }

  function openReviewDialog(task: Task) {
    setActionError(null);
    setReviewingTask(task);
    setReviewResult(task.review_result ?? "pass");
    setReviewNote(task.review_note ?? "");
  }

  function submitReview(event: { preventDefault: () => void }) {
    event.preventDefault();
    if (!reviewingTask) return;
    reviewTask.mutate({
      taskId: reviewingTask.id,
      reviewResult,
      reviewNote,
    });
  }

  async function refreshTasks() {
    if (manualRefreshing) return;
    setActionError(null);
    setManualRefreshing(true);
    try {
      const [taskResult, statsResult] = await Promise.all([
        tasks.refetch(),
        stats.refetch(),
      ]);
      if (taskResult.isError || statsResult.isError) {
        setActionError("刷新执行记录失败，请稍后重试。");
      }
    } finally {
      setManualRefreshing(false);
    }
  }

  if (tasks.isPending) return <p className="panel">正在加载任务...</p>;
  if (tasks.isError) return <p className="panel form-error">执行记录加载失败：{(tasks.error as Error).message}</p>;

  return (
    <div className="tasks-page">
      <PageHeader
        breadcrumbs={[{ label: "首页", to: "/tasks" }, { label: "执行记录" }]}
        title="执行记录"
        description="查看自动化测试任务的执行记录和结果状态。"
      />

      <div className="metric-grid">
        <MetricCard
          testId="metric-total"
          label="总任务数"
          value={kpis.total}
          meta="全部单任务记录"
          tone="primary"
          icon={<ListIcon />}
        />
        <MetricCard
          testId="metric-running"
          label="执行中"
          value={kpis.running}
          meta="正在占用设备"
          tone="running"
          icon={<SmartphoneIcon />}
        />
        <MetricCard
          testId="metric-queued"
          label="排队中"
          value={kpis.queued}
          meta="等待设备分配"
          tone="warning"
          icon={<AlertCircleIcon />}
        />
        <MetricCard
          testId="metric-pass-rate"
          label="成功率"
          value={`${kpis.passRate}%`}
          meta="已完成任务"
          tone="success"
          icon={<CheckCircleIcon />}
        />
        <MetricCard
          testId="metric-manual-review-fail-rate"
          label="人工复核失败率"
          value={`${kpis.manualReviewFailRate}%`}
          meta={`${kpis.manualReviewFailCount}/${kpis.manualReviewTotal} 条复核失败`}
          tone="success"
          icon={<ManualReviewIcon />}
        />
      </div>

      <div className="task-filter-bar">
        <div className="task-search">
          <SearchIcon />
          <input
            aria-label="搜索任务"
            placeholder="搜索任务 ID、用例 ID、场景或操作者"
            type="search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
        </div>
        <SingleSelect
          label="状态筛选"
          value={statusFilter}
          options={STATUS_FILTERS}
          onChange={(value) => {
            setStatusFilter(value);
            setPage(1);
          }}
        />
        <SingleSelect
          label="执行结果筛选"
          value={resultFilter}
          options={RESULT_FILTERS}
          onChange={(value) => {
            setResultFilter(value);
            setPage(1);
          }}
        />
        <SingleSelect
          label="人工审核筛选"
          value={reviewFilter}
          options={REVIEW_FILTERS}
          onChange={(value) => {
            setReviewFilter(value);
            setPage(1);
          }}
        />
        <SingleSelect
          label="操作者筛选"
          value={operatorFilter}
          options={operatorOptions}
          onChange={(value) => {
            setOperatorFilter(value);
            setPage(1);
          }}
        />
        <SingleSelect
          label="时间筛选"
          value={timeFilter}
          options={TIME_FILTERS}
          onChange={(value) => {
            setTimeFilter(value);
            setCreatedAfterFilter(
              value === "all" ? null : recentWindowStartIso(TIME_FILTER_DAYS[value]),
            );
            setPage(1);
          }}
        />
        {hasFilter && (
          <button
            type="button"
            className="text-button"
            aria-label="重置筛选"
            onClick={resetFilters}
          >
            重置
          </button>
        )}
        <div className="task-filter-spacer" />
        <span className="task-total">共 {total} 条</span>
        <button
          type="button"
          className="secondary-button compact"
          disabled={manualRefreshing}
          onClick={() => void refreshTasks()}
        >
          <RefreshIcon />
          {manualRefreshing ? "刷新中..." : "刷新"}
        </button>
      </div>

      <div className="table-card">
        {actionError && <div className="error-banner">{actionError}</div>}
        {items.length === 0 ? (
          hasFilter ? (
            <div className="empty-state">
              <p>无匹配结果，请调整搜索条件或表头筛选</p>
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">
                <ListIcon />
              </div>
              <p>暂无任务</p>
              <p className="muted small">点击上方按钮创建第一个测试任务</p>
              <Link className="primary-button" to="/tasks/new">
                <PlusIcon />
                创建第一个任务
              </Link>
            </div>
          )
        ) : (
          <div className="table-scroll">
            <table className="data-table task-table">
              <thead>
                <tr>
                  <th>任务ID</th>
                  <th>执行对象</th>
                  <th>来源</th>
                  <th>状态</th>
                  <th>结果</th>
                  <th>人工审核</th>
                  <th>创建时间</th>
                  <th>耗时</th>
                  <th>操作者</th>
                  <th className="col-actions col-actions-centered">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((task) => (
                  <tr key={task.id}>
                    <td>
                      <div className={`task-id-stack ${task.batch_id ? "multi-case" : "single-case"}`}>
                        {task.batch_id ? (
                          <>
                            <div className="cell-id-copy task-id-line">
                              <code
                                className="mono cell-id-text batch-id task-id-neutral"
                                title={task.batch_id}
                              >
                                {task.batch_id}
                              </code>
                              <CopyButton value={task.batch_id} label="批次ID" />
                            </div>
                            <div className="cell-id-copy task-id-line">
                              <code className="mono cell-id-text child-task-id task-id-neutral" title={task.id}>
                                {task.id}
                              </code>
                              <CopyButton value={task.id} label="子任务ID" />
                            </div>
                          </>
                        ) : (
                          <div className="cell-id-copy task-id-line">
                            <code
                              className="mono cell-id-text single-task-id task-id-neutral"
                              title={task.display_task_id ?? task.id}
                            >
                              {task.display_task_id ?? task.id}
                            </code>
                            <CopyButton
                              value={task.display_task_id ?? task.id}
                              label="任务ID"
                            />
                          </div>
                        )}
                      </div>
                    </td>
                    <td>
                      <div className="task-target">
                        <span className="task-target-name-wrapper" data-full-title={task.scenario}>
                          <Link className="task-target-link" to={`/tasks/${task.id}`}>{task.scenario}</Link>
                        </span>
                        <div className="cell-id-copy">
                          <code className="mono cell-id-text task-target-case" title={task.case_id}>{task.case_id}</code>
                          <CopyButton value={task.case_id} label="用例ID" />
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`source-badge ${task.source_type === "multi_cases" ? "source-badge-multi" : "source-badge-single"}`}>
                        {task.source_type === "multi_cases" ? "测试计划" : "用例库"}
                      </span>
                    </td>
                    <td>
                      <StatusBadge status={task.execution_status} />
                    </td>
                    <td>
                      {task.verdict
                        ? <StatusBadge verdict={task.verdict} />
                        : <span className="result-empty">-</span>}
                    </td>
                    <td>
                      <ManualReviewBadge task={task} />
                    </td>
                    <td className="muted cell-nowrap">{formatChinaDateTime(task.created_at)}</td>
                    <td className="muted cell-nowrap">
                      {formatTaskElapsedTime(task.execution_status, task.started_at, task.finished_at)}
                    </td>
                    <td>{task.created_by || <span className="muted">-</span>}</td>
                    <td className="col-actions col-actions-centered">
                      <div className="task-row-actions">
                        <Link className="task-action-pill task-action-pill-view" to={`/tasks/${task.id}`}>
                          查看
                        </Link>
                        {task.execution_status === "result_ready" && (
                          <button
                            type="button"
                            className={`task-action-pill ${task.review_result ? "task-action-pill-review-edit" : "task-action-pill-review"}`}
                            onClick={() => openReviewDialog(task)}
                          >
                            {task.review_result ? "修改审核" : "人工审核"}
                          </button>
                        )}
                        {(task.execution_status === "queued" || task.execution_status === "running") && (
                          <button
                            type="button"
                            className="danger-text-button"
                            onClick={() => handleCancel(task.id)}
                            disabled={cancelTask.isPending || cancelRequestedTaskId === task.id}
                          >
                            {cancelRequestedTaskId === task.id ? "取消中" : "取消"}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {totalPages > 1 && (
          <div className="pagination">
            <button
              className="page-button"
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
            >
              <ChevronLeftIcon />
            </button>
            <span className="page-info">第 {page} / {totalPages} 页</span>
            <button
              className="page-button"
              disabled={page >= totalPages}
              onClick={() => setPage(p => p + 1)}
            >
              <ChevronRightIcon />
            </button>
          </div>
        )}
      </div>
      {reviewingTask && (
        <div className="modal-overlay" role="presentation">
          <form
            className="modal-panel confirm-dialog-panel task-review-dialog"
            role="dialog"
            aria-label="人工审核"
            onSubmit={submitReview}
          >
            <div className="modal-header">
              <div>
                <h3>人工审核</h3>
                <p className="confirm-dialog-description task-review-description">人工结论不会覆盖系统执行结果，只用于复核统计。</p>
              </div>
              <button
                type="button"
                className="modal-close"
                aria-label="关闭"
                onClick={() => setReviewingTask(null)}
              >
                ×
              </button>
            </div>
            <div className="modal-body task-review-body">
              <dl className="task-review-summary">
                <div>
                  <dt>任务 ID</dt>
                  <dd><code className="mono">{reviewingTask.display_task_id ?? reviewingTask.id}</code></dd>
                </div>
                <div>
                  <dt>系统结果</dt>
                  <dd>{verdictLabel(reviewingTask.verdict)}</dd>
                </div>
              </dl>
              <label className="form-field task-review-select-field">
                <span>审核结论</span>
                <SingleSelect
                  label="审核结论"
                  value={reviewResult}
                  options={REVIEW_RESULT_OPTIONS}
                  onChange={setReviewResult}
                />
              </label>
              <label className="form-field">
                <span>审核备注</span>
                <textarea
                  aria-label="审核备注"
                  value={reviewNote}
                  rows={4}
                  maxLength={2000}
                  placeholder="可填写人工判断依据，选填"
                  onChange={(event) => setReviewNote(event.target.value)}
                />
              </label>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="secondary-button task-review-footer-button"
                onClick={() => setReviewingTask(null)}
                disabled={reviewTask.isPending}
              >
                取消
              </button>
              <button
                type="submit"
                className="primary-button task-review-footer-button"
                disabled={reviewTask.isPending}
              >
                {reviewTask.isPending ? "保存中..." : "保存审核"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
