import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { ApiError, api } from "../api/client";
import type {
  PlanReportSummary,
  PlanReportListResponse,
  PlanReportStatsResponse,
  ReportStatus,
  TestPlan,
  TestPlanListResponse,
} from "../api/types";
import { BusinessLink as Link } from "../components/business-link";
import { CopyButton } from "../components/copy-button";
import { MetricCard } from "../components/metric-card";
import { PageHeader } from "../components/page-header";
import { PaginationControls } from "../components/pagination-controls";
import { ReportStatusBadge } from "../components/report-status-badge";
import { SingleSelect } from "../components/single-select";
import {
  formatChinaDateTime,
  formatDurationSeconds,
  recentWindowStartIso,
} from "../utils/time";

const PAGE_SIZE = 10;
type StatusFilter = ReportStatus | "all";
type TimeFilter = "all" | "1d" | "3d" | "7d" | "30d" | "custom";
type PresetTimeFilter = Exclude<TimeFilter, "all" | "custom">;
type ReportDownloadFormat = "markdown" | "csv";

const DOWNLOADABLE_REPORT_STATUSES: ReportStatus[] = [
  "success",
  "failure",
  "exception",
];

const DOWNLOAD_FORMATS: Array<{
  value: ReportDownloadFormat;
  extension: string;
  label: string;
  description: string;
}> = [
  {
    value: "markdown",
    extension: "md",
    label: "Markdown 报告",
    description: "KPI、执行快照、子任务结果",
  },
  {
    value: "csv",
    extension: "csv",
    label: "CSV 明细表",
    description: "适合表格分析子任务结果",
  },
];

const STATUS_OPTIONS = [
  { value: "all", label: "全部结果" },
  { value: "queued", label: "排队中" },
  { value: "running", label: "执行中" },
  { value: "success", label: "成功" },
  { value: "failure", label: "失败" },
  { value: "exception", label: "异常" },
  { value: "cancelled", label: "已取消" },
] as const;

const TIME_OPTIONS = [
  { value: "all", label: "全部时间" },
  { value: "1d", label: "最近一天" },
  { value: "3d", label: "最近3天" },
  { value: "7d", label: "最近一周" },
  { value: "30d", label: "最近一个月" },
] as const;

const TIME_DAYS: Record<Exclude<TimeFilter, "all" | "custom">, number> = {
  "1d": 1,
  "3d": 3,
  "7d": 7,
  "30d": 30,
};

function parseTimeFilter(
  value: string | null,
  createdAfter: string,
): TimeFilter {
  if (!createdAfter) return "all";
  return value !== null && Object.hasOwn(TIME_DAYS, value)
    ? value as PresetTimeFilter
    : "custom";
}

function parsePage(value: string | null): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

function parseStatus(value: string | null): StatusFilter {
  return STATUS_OPTIONS.some((item) => item.value === value)
    ? value as StatusFilter
    : "all";
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

export function TaskReportListPage() {
  const [urlParams, setUrlParams] = useSearchParams();
  const [searchInput, setSearchInput] = useState(urlParams.get("search") ?? "");
  const [search, setSearch] = useState(urlParams.get("search") ?? "");
  const [planSearchInput, setPlanSearchInput] = useState("");
  const [planSearch, setPlanSearch] = useState("");
  const [openDownloadMenu, setOpenDownloadMenu] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<{
    executionId: string;
    format: ReportDownloadFormat;
  } | null>(null);
  const page = parsePage(urlParams.get("page"));
  const planId = urlParams.get("test_plan_id") ?? "all";
  const status = parseStatus(urlParams.get("status"));
  const createdAfter = urlParams.get("created_after") ?? "";
  const timeFilter = parseTimeFilter(
    urlParams.get("time_range"),
    createdAfter,
  );

  const filterParams = useMemo(() => {
    const params = new URLSearchParams();
    if (planId !== "all") params.set("test_plan_id", planId);
    if (status !== "all") params.set("status", status);
    if (createdAfter) params.set("created_after", createdAfter);
    if (search) params.set("search", search);
    return params;
  }, [createdAfter, planId, search, status]);

  const listParams = useMemo(() => {
    const params = new URLSearchParams(filterParams);
    params.set("page", String(page));
    params.set("page_size", String(PAGE_SIZE));
    return params;
  }, [filterParams, page]);
  const listKey = listParams.toString();
  const planParams = useMemo(() => {
    const params = new URLSearchParams({
      page: "1",
      page_size: "50",
    });
    if (planSearch) params.set("search", planSearch);
    return params.toString();
  }, [planSearch]);

  useEffect(() => {
    const timer = window.setTimeout(
      () => setPlanSearch(planSearchInput.trim()),
      250,
    );
    return () => window.clearTimeout(timer);
  }, [planSearchInput]);

  useEffect(() => {
    if (openDownloadMenu === null) return;
    function closeDownloadMenuOnOutsideClick(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest(".task-report-download-action")) return;
      setOpenDownloadMenu(null);
    }
    window.addEventListener("pointerdown", closeDownloadMenuOnOutsideClick);
    return () =>
      window.removeEventListener("pointerdown", closeDownloadMenuOnOutsideClick);
  }, [openDownloadMenu]);

  useEffect(() => {
    const nextSearch = searchInput.trim();
    if (nextSearch === search) return;
    const timer = window.setTimeout(() => {
      updateParams((next) => {
        if (nextSearch) next.set("search", nextSearch);
        else next.delete("search");
      }, { resetPage: true });
      setSearch(nextSearch);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [search, searchInput]);

  const plans = useQuery({
    queryKey: ["test-plans", "report-filter", planSearch],
    queryFn: () =>
      api.get<TestPlanListResponse>(`/test-plans?${planParams}`),
  });
  const selectedPlanInResults = (plans.data?.items ?? []).some(
    (plan) => plan.id === planId,
  );
  const selectedPlan = useQuery({
    queryKey: ["test-plan", "report-filter", planId],
    queryFn: () => api.get<TestPlan>(`/test-plans/${planId}`),
    enabled: planId !== "all" && !selectedPlanInResults,
    retry: false,
  });
  const reports = useQuery({
    queryKey: ["task-reports", listKey],
    queryFn: () =>
      api.get<PlanReportListResponse>(`/task-reports?${listKey}`),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((item) =>
          item.report_status === "queued" || item.report_status === "running")
        ? 3000
        : 5000;
    },
  });
  const stats = useQuery({
    queryKey: ["task-report-stats"],
    queryFn: () =>
      api.get<PlanReportStatsResponse>("/task-reports/stats"),
    refetchInterval: reports.data?.items.some((item) =>
        item.report_status === "queued" || item.report_status === "running")
      ? 3000
      : 5000,
  });

  const activePlanOptions = (plans.data?.items ?? []).map((plan) => ({
      value: plan.id,
      label: plan.name,
    }));
  const selectedPlanIsActive = activePlanOptions.some(
    (option) => option.value === planId,
  );
  const planOptions = [
    { value: "all", label: "全部任务" },
    ...(planId !== "all" && !selectedPlanIsActive
      ? [{
          value: planId,
          label: selectedPlan.data?.name ?? (
            selectedPlan.error instanceof ApiError
              && selectedPlan.error.status === 404
              ? `已删除计划（${planId}）`
              : `已选择计划（${planId}）`
          ),
        }]
      : []),
    ...activePlanOptions,
  ];
  const timeOptions = timeFilter === "custom"
    ? [...TIME_OPTIONS, { value: "custom", label: "自定义时间" } as const]
    : TIME_OPTIONS;
  const metrics = stats.data ?? {
    report_count: 0,
    success_count: 0,
    failure_count: 0,
    average_pass_rate: 0,
  };
  const hasReportFilter = planId !== "all"
    || status !== "all"
    || Boolean(createdAfter)
    || Boolean(search);

  function updateParams(
    change: (next: URLSearchParams) => void,
    { resetPage = false }: { resetPage?: boolean } = {},
  ) {
    const next = new URLSearchParams(urlParams);
    change(next);
    if (resetPage) next.delete("page");
    setUrlParams(next);
  }

  function updateFilter(
    key: "test_plan_id" | "status",
    value: string,
  ) {
    updateParams((next) => {
      if (value === "all") next.delete(key);
      else next.set(key, value);
    }, { resetPage: true });
  }

  function changeTime(value: TimeFilter) {
    updateParams((next) => {
      if (value === "all") {
        next.delete("time_range");
        next.delete("created_after");
      } else if (value !== "custom") {
        next.set("time_range", value);
        next.set("created_after", recentWindowStartIso(TIME_DAYS[value]));
      }
    }, { resetPage: true });
  }

  async function downloadReport(
    report: PlanReportSummary,
    format: ReportDownloadFormat,
  ) {
    const extension = format === "csv" ? "csv" : "md";
    setOpenDownloadMenu(null);
    setDownloading({ executionId: report.execution_id, format });
    try {
      const response = await api.download(
        `/task-reports/${report.execution_id}/download?format=${format}`,
      );
      const blob = await response.blob();
      const filename = filenameFromDisposition(
        response.headers.get("Content-Disposition"),
      ) ?? `cua-test-report-${report.task_batch_id}.${extension}`;
      downloadBlob(filename, blob);
    } catch {
      // Keep the list stable; failed downloads can be retried from the same row.
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="page-container task-report-list-page">
      <PageHeader
        breadcrumbs={[{ label: "首页", to: "/tasks" }, { label: "测试报告" }]}
        title="测试报告"
        description="查看测试计划每次运行的聚合结果与子任务明细"
      />

      <div className="metric-grid task-report-metrics">
        <MetricCard
          testId="report-count"
          label="报告总数"
          value={metrics.report_count}
          meta="当前筛选范围"
          icon={<MetricIcon path="M6 3h8l4 4v14H6zM14 3v5h5M9 13h6M9 17h4" />}
        />
        <MetricCard
          testId="report-success"
          label="成功"
          value={metrics.success_count}
          meta="执行成功报告"
          tone="success"
          icon={<MetricIcon path="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-4-9 3 3 5-6" />}
        />
        <MetricCard
          testId="report-failure"
          label="失败"
          value={metrics.failure_count}
          meta="断言失败报告"
          tone="warning"
          icon={<MetricIcon path="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-3-6 6-6M9 9l6 6" />}
        />
        <MetricCard
          testId="report-average"
          label="平均通过率"
          value={formatKpiPercent(metrics.average_pass_rate)}
          meta="按执行快照统计"
          tone="running"
          icon={<MetricIcon path="M4 18 10 12l4 4 6-10M7 7h.01M17 17h.01M7 17 17 7" />}
        />
      </div>

      <div className="page-content task-report-content">
        {(plans.isError || stats.isError || (
          selectedPlan.isError
          && !(selectedPlan.error instanceof ApiError
            && selectedPlan.error.status === 404)
        )) && (
          <div className="error-banner" role="alert">
            <span>筛选项或报告统计加载失败。</span>
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                void plans.refetch();
                void stats.refetch();
                if (selectedPlan.isError) void selectedPlan.refetch();
              }}
            >
              重新加载
            </button>
          </div>
        )}
        <div className="filter-card task-report-filter-bar">
          <label className="task-report-search">
            <span className="sr-only">搜索任务ID</span>
            <input
              aria-label="搜索任务ID"
              type="search"
              placeholder="搜索任务ID"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </label>
          <div className="task-report-filter-field plan-filter">
            <SingleSelect
              label="测试计划筛选"
              value={planId}
              options={planOptions}
              onChange={(value) => updateFilter("test_plan_id", value)}
              searchValue={planSearchInput}
              onSearchChange={setPlanSearchInput}
              searchLabel="搜索测试计划"
              emptyText="暂无匹配计划"
            />
          </div>
          <div className="task-report-filter-field status-filter">
            <SingleSelect
              label="报告状态筛选"
              value={status}
              options={STATUS_OPTIONS}
              onChange={(value) => updateFilter("status", value)}
            />
          </div>
          <div className="task-report-filter-field time-filter">
            <SingleSelect
              label="时间筛选"
              value={timeFilter}
              options={timeOptions}
              onChange={changeTime}
            />
          </div>
          {(planId !== "all" || status !== "all" || createdAfter || search) && (
            <button
              type="button"
              className="secondary-button task-report-filter-reset"
              onClick={() => {
                updateParams((next) => {
                  next.delete("test_plan_id");
                  next.delete("status");
                  next.delete("time_range");
                  next.delete("created_after");
                  next.delete("search");
                  setSearch("");
                  setSearchInput("");
                }, { resetPage: true });
              }}
            >
              重置筛选
            </button>
          )}
        </div>

        <div className="table-card task-report-table-card">
          {reports.isLoading ? (
            <div
              className="task-report-skeleton"
              role="status"
              aria-label="正在加载测试报告"
              aria-live="polite"
              aria-busy="true"
            >
              {Array.from({ length: 6 }, (_, index) => <span key={index} />)}
            </div>
          ) : reports.isError ? (
            <ReportError
              error={reports.error}
              onRetry={() => void reports.refetch()}
            />
          ) : (reports.data?.items.length ?? 0) === 0 ? (
            hasReportFilter ? (
              <div className="empty-state task-report-empty">
                <strong>无匹配结果，请调整搜索条件或表头筛选</strong>
              </div>
            ) : (
              <div className="empty-state task-report-empty">
                <strong>暂无测试报告</strong>
                <p>运行测试计划后，可在这里查看聚合报告。</p>
                <Link className="primary-button" to="/test-plans">
                  返回测试计划
                </Link>
              </div>
            )
          ) : (
            <div className="table-scroll">
              <table className="data-table task-table task-report-table">
                <thead>
                  <tr>
                    <th>任务 ID</th>
                    <th>测试计划</th>
                    <th>执行结果</th>
                    <th>测试通过率</th>
                    <th>创建时间</th>
                    <th>总执行时长</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.data?.items.map((report) => {
                    const downloadMenuOpen = openDownloadMenu === report.execution_id;
                    return (
                      <tr
                        key={report.execution_id}
                        className={downloadMenuOpen ? "download-menu-open" : undefined}
                      >
                        <td>
                          <div className="task-report-id-cell">
                            <Link
                              to={`/task-reports/${report.execution_id}`}
                              className="task-report-id-link"
                              translate="no"
                            >
                              {report.task_batch_id}
                            </Link>
                            <CopyButton value={report.task_batch_id} label="任务ID" />
                          </div>
                        </td>
                        <td>
                          <span className="task-report-plan-name" title={report.plan_name_snapshot}>
                            {report.plan_name_snapshot}
                          </span>
                        </td>
                        <td><ReportStatusBadge status={report.report_status} /></td>
                        <td className="report-rate">{Math.round(report.pass_rate)}%</td>
                        <td>{formatChinaDateTime(report.created_at)}</td>
                        <td>{formatDurationSeconds(report.duration_seconds)}</td>
                        <td
                          className={`task-report-download-cell ${
                            downloadMenuOpen ? "open" : ""
                          }`}
                        >
                          <ReportDownloadAction
                            report={report}
                            open={downloadMenuOpen}
                            downloading={
                              downloading?.executionId === report.execution_id
                            }
                            onToggle={() =>
                              setOpenDownloadMenu((current) =>
                                current === report.execution_id
                                  ? null
                                  : report.execution_id
                              )}
                            onDownload={(format) => {
                              void downloadReport(report, format);
                            }}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {!reports.isLoading && !reports.isError && (
            <PaginationControls
              page={page}
              pageSize={PAGE_SIZE}
              total={reports.data?.total ?? 0}
              onPageChange={(value) => {
                updateParams((next) => {
                  if (value <= 1) next.delete("page");
                  else next.set("page", String(value));
                });
              }}
              onPageSizeChange={() => {
                updateParams(() => undefined, { resetPage: true });
              }}
              showPageSize={false}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function ReportDownloadAction({
  report,
  open,
  downloading,
  onToggle,
  onDownload,
}: {
  report: PlanReportSummary;
  open: boolean;
  downloading: boolean;
  onToggle: () => void;
  onDownload: (format: ReportDownloadFormat) => void;
}) {
  if (!DOWNLOADABLE_REPORT_STATUSES.includes(report.report_status)) {
    return (
      <span className="task-report-download-disabled">
        {report.report_status === "running" || report.report_status === "queued"
          ? "完成后可下载"
          : "不支持下载"}
      </span>
    );
  }

  return (
    <div className={`task-report-download-action ${open ? "open" : ""}`}>
      <button
        type="button"
        className="secondary-button task-report-download-button"
        aria-label={downloading ? undefined : `下载报告 ${report.task_batch_id}`}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={downloading}
        onClick={onToggle}
      >
        {downloading ? (
          <>
            <span className="task-report-download-spinner" aria-hidden="true" />
            生成中...
          </>
        ) : (
          <>
            <DownloadIcon />
            下载报告
          </>
        )}
      </button>
      {open && !downloading && (
        <div className="task-report-download-menu" role="menu">
          {DOWNLOAD_FORMATS.map((format) => (
            <button
              key={format.value}
              type="button"
              role="menuitem"
              className="task-report-download-format"
              onClick={() => onDownload(format.value)}
            >
              <span className={`task-report-download-file ${format.extension}`}>
                {format.extension.toUpperCase()}
              </span>
              <span>
                <strong>{format.label}</strong>
                <small>{format.description}</small>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function DownloadIcon() {
  return (
    <svg className="task-report-download-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3v12" />
      <path d="m7 10 5 5 5-5" />
      <path d="M5 21h14" />
    </svg>
  );
}

function filenameFromDisposition(value: string | null): string | null {
  const match = value?.match(/filename="?(?<filename>[^";]+)"?/);
  return match?.groups?.filename ?? null;
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function ReportError({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry: () => void;
}) {
  const forbidden = error instanceof ApiError && error.status === 403;
  return (
    <div className="empty-state error" role="alert">
      <strong>{forbidden ? "无权查看测试报告" : "测试报告加载失败"}</strong>
      <p>{forbidden ? "当前账号没有测试报告访问权限。" : "请稍后重新加载。"}</p>
      {!forbidden && (
        <button type="button" className="secondary-button" onClick={onRetry}>
          重新加载
        </button>
      )}
    </div>
  );
}
