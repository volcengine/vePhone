import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router";

import { ApiError, api } from "../api/client";
import type {
  PlanReportDetailResponse,
  PlanReportTask,
  ReportStatus,
} from "../api/types";
import { BusinessLink as Link } from "../components/business-link";
import { MetricCard } from "../components/metric-card";
import { PageHeader } from "../components/page-header";
import { PaginationControls } from "../components/pagination-controls";
import { ReportStatusBadge } from "../components/report-status-badge";
import { RuntimeConfigSnapshot } from "../components/runtime-config-snapshot";
import {
  formatChinaDateTime,
  formatDurationSeconds,
} from "../utils/time";
import { failureTypeLabel } from "../utils/task-status";

type PageSize = 10 | 20 | 50;

function parsePage(value: string | null): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

function parsePageSize(value: string | null): PageSize {
  const parsed = Number(value);
  return parsed === 20 || parsed === 50 ? parsed : 10;
}

function MetricIcon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

function formatKpiPercent(value: number): string {
  return `${Math.round(value)}%`;
}

function formatTaskMetric(value: number | null): string {
  return typeof value === "number" ? value.toLocaleString("en-US") : "-";
}

function formatTaskDuration(value: number | null): string {
  if (value == null || !Number.isFinite(value) || value < 0) return "-";
  const totalSeconds = Math.floor(value);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours} 小时 ${String(minutes).padStart(2, "0")} 分 ${
      String(seconds).padStart(2, "0")
    } 秒`;
  }
  if (minutes > 0) return `${minutes} 分 ${seconds} 秒`;
  return `${seconds} 秒`;
}

function taskStatus(task: PlanReportTask): string {
  if (task.execution_status === "unknown") return "未知状态";
  if (task.execution_status === "script_pending") return "脚本生成中";
  if (task.execution_status === "queued") return "排队中";
  if (task.execution_status === "running") return "执行中";
  if (task.execution_status === "cancelled") return "已取消";
  return "已完成";
}

function taskVerdict(task: PlanReportTask): string {
  if (task.verdict === "unknown") return "未知结果";
  if (task.verdict === "pass") return "成功";
  if (task.verdict === "fail") return "失败";
  return "未判定";
}

function isActive(status: ReportStatus): boolean {
  return status === "queued" || status === "running";
}

export function PlanExecutionReportPage() {
  const { executionId = "" } = useParams<{ executionId: string }>();
  const [urlParams, setUrlParams] = useSearchParams();
  const page = parsePage(urlParams.get("page"));
  const pageSize = parsePageSize(urlParams.get("page_size"));

  function updatePagination(
    nextPage: number,
    nextPageSize = pageSize,
  ) {
    const next = new URLSearchParams(urlParams);
    if (nextPage <= 1) next.delete("page");
    else next.set("page", String(nextPage));
    if (nextPageSize === 10) next.delete("page_size");
    else next.set("page_size", String(nextPageSize));
    setUrlParams(next);
  }

  const report = useQuery({
    queryKey: ["task-report-detail", executionId, page, pageSize],
    queryFn: () =>
      api.get<PlanReportDetailResponse>(
        `/task-reports/${executionId}?page=${page}&page_size=${pageSize}`,
      ),
    enabled: Boolean(executionId),
    refetchInterval: (query) =>
      query.state.data && isActive(query.state.data.report_status)
        ? 3000
        : false,
  });

  if (report.isLoading) {
    return (
      <div className="page-container plan-report-page">
        <div
          className="plan-report-skeleton"
          role="status"
          aria-label="正在加载测试报告"
          aria-live="polite"
          aria-busy="true"
        />
      </div>
    );
  }

  if (report.isError || !report.data) {
    const notFound = report.error instanceof ApiError
      && report.error.code === "task_report_not_found";
    const forbidden = report.error instanceof ApiError
      && report.error.status === 403;
    return (
      <div className="page-container plan-report-page">
        <div className="empty-state error" role="alert">
          <strong>
            {notFound
              ? "测试报告不存在"
              : forbidden
                ? "无权查看测试报告"
                : "测试报告加载失败"}
          </strong>
          <p>
            {notFound
              ? "该执行记录不存在或已不可访问。"
              : forbidden
                ? "当前账号没有该报告的访问权限。"
                : "请检查网络状态后重新加载。"}
          </p>
          {notFound || forbidden ? (
            <Link className="secondary-button" to="/task-reports">
              返回测试报告
            </Link>
          ) : (
            <button
              type="button"
              className="secondary-button"
              onClick={() => void report.refetch()}
            >
              重新加载
            </button>
          )}
        </div>
      </div>
    );
  }

  const item = report.data;
  const terminalCount = item.pass_count + item.fail_count
    + item.exception_count + item.cancelled_count;

  return (
    <div className="page-container plan-report-page">
      <PageHeader
        breadcrumbs={[
          { label: "首页", to: "/tasks" },
          { label: "测试报告", to: "/task-reports" },
          { label: item.task_batch_id },
        ]}
        title={item.plan_name_snapshot}
        description={`计划执行报告 · ${item.task_batch_id}`}
        actions={<ReportStatusBadge status={item.report_status} />}
      />

      <div className="metric-grid plan-report-metrics">
        <MetricCard
          testId="plan-report-result"
          label="执行结果"
          value={<ReportStatusBadge status={item.report_status} />}
          meta="实时聚合状态"
          icon={<MetricIcon path="M4 5h16v14H4zM8 9h8M8 13h5" />}
        />
        <MetricCard
          testId="plan-report-rate"
          label="测试通过率"
          value={formatKpiPercent(item.pass_rate)}
          meta="以执行快照为分母"
          tone="running"
          icon={<MetricIcon path="M4 19 10 13l4 4 6-10" />}
        />
        <MetricCard
          testId="plan-report-passed"
          label="通过子任务"
          value={`${item.pass_count} / ${item.case_ids_snapshot.length}`}
          meta={`已终态 ${terminalCount}`}
          tone="success"
          icon={<MetricIcon path="m5 12 4 4L19 6" />}
        />
        <MetricCard
          testId="plan-report-duration"
          label="总执行时长"
          value={formatDurationSeconds(item.duration_seconds)}
          meta={isActive(item.report_status) ? "持续更新中" : "批次总耗时"}
          tone="warning"
          icon={<MetricIcon path="M12 8v4l3 2M21 12a9 9 0 1 1-9-9" />}
        />
      </div>

      <div className="plan-report-stack">
        <section className="table-card plan-report-summary">
          <div className="section-heading">
            <h2>执行快照</h2>
          </div>
          <dl>
            <div><dt>创建时间</dt><dd>{formatChinaDateTime(item.created_at)}</dd></div>
            <div><dt>开始时间</dt><dd>{formatChinaDateTime(item.started_at)}</dd></div>
            <div><dt>完成时间</dt><dd>{formatChinaDateTime(item.finished_at)}</dd></div>
            <div>
              <dt>设备策略</dt>
              <dd>{item.device_strategy_snapshot === "automatic" ? "自动分配" : "指定设备"}</dd>
            </div>
            <div><dt>设备并发数</dt><dd>{item.concurrency_snapshot}</dd></div>
            <div>
              <dt>Pod</dt>
              <dd translate="no">
                {item.pod_ids_snapshot.length
                  ? item.pod_ids_snapshot.join(", ")
                  : "自动分配"}
              </dd>
            </div>
          </dl>
        </section>

        <RuntimeConfigSnapshot config={item.config_snapshot} />

        <section className="table-card plan-report-task-card">
          <div className="section-heading">
            <div>
              <h2>子任务结果</h2>
              <p className="muted">共 {item.tasks_total} 个子任务</p>
            </div>
          </div>
          {item.tasks.length === 0 ? (
            <div className="empty-state">当前页暂无子任务</div>
          ) : (
            <div className="table-scroll">
              <table className="data-table plan-report-task-table">
                <thead>
                  <tr>
                    <th>任务 ID</th>
                    <th>Run ID</th>
                    <th>用例</th>
                    <th>状态</th>
                    <th>结果</th>
                    <th>失败类型</th>
                    <th>创建时间</th>
                    <th>执行时长</th>
                    <th>输入 Token</th>
                    <th>输出 Token</th>
                    <th>执行步数</th>
                  </tr>
                </thead>
                <tbody>
                  {item.tasks.map((task) => (
                    <tr key={task.task_id}>
                      <td>
                        <Link to={`/tasks/${task.task_id}`} translate="no">
                          {task.task_id}
                        </Link>
                      </td>
                      <td>
                        {task.remote_run_id ? (
                          <code translate="no">{task.remote_run_id}</code>
                        ) : "-"}
                      </td>
                      <td className="plan-report-case-cell">
                        <strong>{task.case_title}</strong>
                        <code translate="no">{task.case_id}</code>
                        {!task.case_deleted && (
                          <Link
                            className="text-button plan-report-case-link"
                            to={`/cases/${task.case_id}/edit`}
                            aria-label={`查看用例 ${task.case_title}`}
                          >
                            查看用例
                          </Link>
                        )}
                      </td>
                      <td>
                        <span className={`task-report-task-status ${task.execution_status}`}>
                          {taskStatus(task)}
                        </span>
                      </td>
                      <td>{taskVerdict(task)}</td>
                      <td>
                        {task.failure_type ? (
                          <code className="safe-failure-type" translate="no">
                            {failureTypeLabel(task.failure_type)}
                          </code>
                        ) : "-"}
                      </td>
                      <td>{formatChinaDateTime(task.created_at)}</td>
                      <td>{formatTaskDuration(task.duration_seconds)}</td>
                      <td>{formatTaskMetric(task.input_tokens)}</td>
                      <td>{formatTaskMetric(task.output_tokens)}</td>
                      <td>{formatTaskMetric(task.total_steps)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <PaginationControls
            page={page}
            pageSize={pageSize}
            total={item.tasks_total}
            onPageChange={(value) => updatePagination(value)}
            onPageSizeChange={(value) => updatePagination(1, value)}
          />
        </section>
      </div>
    </div>
  );
}
