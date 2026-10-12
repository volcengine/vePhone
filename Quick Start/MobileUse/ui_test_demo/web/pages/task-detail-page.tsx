import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation, useParams, useSearchParams } from "react-router";

import { ApiError, api } from "../api/client";
import type { Task, TaskListPage, Verdict } from "../api/types";
import { BusinessLink as Link } from "../components/business-link";
import { useBusinessPath } from "../business-context";
import { PageHeader } from "../components/page-header";
import { SingleSelect } from "../components/single-select";
import { StatusBadge } from "../components/status-badge";
import { formatChinaDateTime } from "../utils/time";

const REVIEW_RESULT_OPTIONS = [
  { value: "pass", label: "复核通过" },
  { value: "fail", label: "复核失败" },
] as const;

function FileTextIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function ActivityIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}

function emptyFriendlyError(error: unknown) {
  if (!error) return null;
  if (error instanceof ApiError && error.message.includes("not configured")) return null;
  return error instanceof Error ? error.message : "任务详情加载失败";
}

function mapStatus(status: string) {
  return status;
}

function reviewLabel(result: Verdict | null | undefined): string {
  if (result === "pass") return "复核通过";
  if (result === "fail") return "复核失败";
  return "待审核";
}

function queueSearchParams(searchParams: URLSearchParams): URLSearchParams {
  const params = new URLSearchParams(searchParams);
  params.delete("review");
  params.delete("page");
  params.delete("page_size");
  if (!params.has("status")) params.set("status", "result_ready");
  params.set("page", "1");
  params.set("page_size", "100");
  return params;
}

function taskHref(taskId: string, searchParams: URLSearchParams): string {
  const params = new URLSearchParams(searchParams);
  params.set("review", "1");
  const query = params.toString();
  return `/tasks/${taskId}${query ? `?${query}` : ""}`;
}

function ManualReviewPanel({
  item,
  queueItems,
  searchParams,
}: {
  item: Task;
  queueItems: Task[];
  searchParams: URLSearchParams;
}) {
  const queryClient = useQueryClient();
  const [reviewResult, setReviewResult] = useState<Verdict>(
    item.review_result ?? item.verdict ?? "pass",
  );
  const [reviewNote, setReviewNote] = useState(item.review_note ?? "");
  const index = queueItems.findIndex((task) => task.id === item.id);
  const previousTask = index > 0 ? queueItems[index - 1] : null;
  const nextTask = index >= 0 && index < queueItems.length - 1
    ? queueItems[index + 1]
    : null;

  useEffect(() => {
    setReviewResult(item.review_result ?? item.verdict ?? "pass");
    setReviewNote(item.review_note ?? "");
  }, [item.id, item.review_result, item.review_note, item.verdict]);

  const reviewMutation = useMutation({
    mutationFn: () =>
      api.put<Task>(`/tasks/${item.id}/review`, {
        review_result: reviewResult,
        review_note: reviewNote.trim() || null,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["task", item.id], updated);
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["task-stats"] });
      void queryClient.invalidateQueries({ queryKey: ["task-report-detail"] });
    },
  });

  return (
    <section className="task-detail-review-panel" role="region" aria-label="人工审核">
      <div className="section-heading">
        <div>
          <h2>人工审核</h2>
          <p className="muted">保存后停留当前任务，可手动切换上一条或下一条。</p>
        </div>
        <span className={`status-badge ${item.review_result === "fail" ? "danger" : item.review_result === "pass" ? "success" : "primary"}`}>
          <span className="dot" />
          {reviewLabel(item.review_result)}
        </span>
      </div>

      <dl className="task-review-summary-list">
        <div><dt>系统结果</dt><dd>{item.verdict === "pass" ? "成功" : item.verdict === "fail" ? "失败" : "未判定"}</dd></div>
        <div><dt>审核人</dt><dd>{item.reviewed_by ?? "-"}</dd></div>
        <div><dt>审核时间</dt><dd>{formatChinaDateTime(item.reviewed_at)}</dd></div>
      </dl>

      <SingleSelect
        label="审核结论"
        value={reviewResult}
        options={REVIEW_RESULT_OPTIONS}
        onChange={setReviewResult}
        className="task-review-select-field"
      />
      <label className="task-review-note-field">
        <span>审核备注</span>
        <textarea
          value={reviewNote}
          onChange={(event) => setReviewNote(event.target.value)}
          placeholder="补充人工判断依据"
        />
      </label>
      {reviewMutation.isError && (
        <p className="form-error">
          {reviewMutation.error instanceof Error
            ? reviewMutation.error.message
            : "保存审核失败"}
        </p>
      )}
      {reviewMutation.isSuccess && (
        <p className="task-review-save-state">审核已保存</p>
      )}
      <div className="task-review-navigation">
        {previousTask ? (
          <Link className="secondary-button" to={taskHref(previousTask.id, searchParams)}>
            上一条
          </Link>
        ) : (
          <button type="button" className="secondary-button" disabled>上一条</button>
        )}
        {nextTask ? (
          <Link className="secondary-button" to={taskHref(nextTask.id, searchParams)}>
            下一条
          </Link>
        ) : (
          <button type="button" className="secondary-button" disabled>下一条</button>
        )}
      </div>
      <button
        type="button"
        className="primary-button task-review-save-button"
        disabled={reviewMutation.isPending}
        onClick={() => reviewMutation.mutate()}
      >
        {reviewMutation.isPending ? "保存中..." : "保存审核"}
      </button>
    </section>
  );
}

export function TaskDetailPage() {
  const { taskId } = useParams();
  const businessPath = useBusinessPath();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const queueParams = useMemo(() => queueSearchParams(searchParams), [searchParams]);
  const task = useQuery({
    enabled: Boolean(taskId),
    queryKey: ["task", taskId],
    queryFn: () => api.get<Task>(`/tasks/${taskId}`),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 3000;
      return ["result_ready", "cancelled"].includes(data.execution_status)
        ? false
        : 3000;
    },
  });
  const reviewQueue = useQuery({
    enabled: Boolean(taskId),
    queryKey: ["task-review-queue", queueParams.toString()],
    queryFn: () => api.get<TaskListPage>(`/tasks?${queueParams.toString()}`),
  });

  if (task.isPending) return <p className="panel">正在加载任务详情...</p>;
  const friendlyError = emptyFriendlyError(task.error);
  if (friendlyError) return <p className="panel form-error">{friendlyError}</p>;
  if (!task.data) return <p className="panel form-error">任务不存在</p>;

  const item = task.data;
  const showReviewPanel = item.execution_status === "result_ready";

  return (
    <div className="detail-page">
      <PageHeader
        breadcrumbs={[
          { label: "首页", to: "/tasks" },
          { label: "执行记录", to: "/tasks" },
          { label: "任务详情" },
        ]}
        title={`${item.scenario} 测试`}
        description={(
          <>
            任务 ID <code className="mono">{item.id}</code> · 场景 {item.scenario}
          </>
        )}
        actions={
          <>
          <StatusBadge status={mapStatus(item.execution_status)} />
          {item.verdict && <StatusBadge verdict={item.verdict} />}
          </>
        }
      />

      <div className={showReviewPanel ? "task-detail-review-layout" : ""}>
        <div className="task-detail-main">
          <nav className="detail-tabs detail-tabs-full" aria-label="任务详情导航">
            <NavLink end to={`${businessPath(`/tasks/${item.id}`)}${location.search}`}>
              <FileTextIcon />
              概览
            </NavLink>
            <NavLink to={`${businessPath(`/tasks/${item.id}/trace`)}${location.search}`}>
              <ActivityIcon />
              执行轨迹
            </NavLink>
          </nav>
          <div className="tab-content tab-content-full">
            <Outlet />
          </div>
        </div>
        {showReviewPanel && (
          <ManualReviewPanel
            item={item}
            queueItems={reviewQueue.data?.items ?? [item]}
            searchParams={searchParams}
          />
        )}
      </div>
    </div>
  );
}
