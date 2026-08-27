import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { ApiError, api } from "../api/client";
import type {
  CreatorListResponse,
  ReportStatus,
  TagOptionListResponse,
  TestType,
  TestPlanListResponse,
  TestPlanStatsResponse,
} from "../api/types";
import { ConfirmDialog } from "../components/confirm-dialog";
import { BusinessLink as Link } from "../components/business-link";
import { CopyButton } from "../components/copy-button";
import { MetricCard } from "../components/metric-card";
import { PageHeader } from "../components/page-header";
import { PaginationControls } from "../components/pagination-controls";
import { SingleSelect } from "../components/single-select";
import { tagToneClass } from "../utils/tag-tone";
import { formatChinaDateTime } from "../utils/time";

const PAGE_SIZE = 10;

const TEST_TYPE_LABELS: Record<TestType, string> = {
  new_feature: "新功能测试",
  regression: "回归测试",
};

const TEST_TYPE_OPTIONS: Array<{ value: "" | TestType; label: string }> = [
  { value: "", label: "全部类型" },
  { value: "new_feature", label: TEST_TYPE_LABELS.new_feature },
  { value: "regression", label: TEST_TYPE_LABELS.regression },
];

function testTypeLabel(value: TestType | string | null | undefined): string {
  return value === "new_feature"
    ? TEST_TYPE_LABELS.new_feature
    : TEST_TYPE_LABELS.regression;
}

function testTypeClass(value: TestType | string | null | undefined): string {
  return value === "new_feature" ? "new-feature" : "regression";
}

const STATUS_LABELS: Record<ReportStatus, string> = {
  queued: "排队中",
  running: "执行中",
  success: "成功",
  failure: "失败",
  exception: "异常",
  cancelled: "已取消",
};

function parsePage(value: string | null): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points="6 3 20 12 6 21 6 3" />
    </svg>
  );
}

function EditIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

function MetricIcon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function statusClass(status: ReportStatus): string {
  if (status === "success") return "success";
  if (status === "failure" || status === "exception") return "danger";
  if (status === "running") return "running";
  if (status === "queued") return "primary";
  return "neutral";
}

function formatKpiPercent(value: number): string {
  return `${Math.round(value)}%`;
}

function shouldShowPlanNameTooltip(name: string): boolean {
  return name.trim().length > 14;
}

export function TestPlanListPage() {
  const queryClient = useQueryClient();
  const [urlParams, setUrlParams] = useSearchParams();
  const [page, setPage] = useState(() => parsePage(urlParams.get("page")));
  const [search, setSearch] = useState(() => urlParams.get("search") ?? "");
  const [searchInput, setSearchInput] = useState(search);
  const [tagFilter, setTagFilter] = useState(() => urlParams.get("tag") ?? "");
  const [creatorFilter, setCreatorFilter] = useState(
    () => urlParams.get("created_by") ?? "",
  );
  const [testTypeFilter, setTestTypeFilter] = useState<"" | TestType>(() => {
    const value = urlParams.get("test_type");
    return value === "new_feature" || value === "regression" ? value : "";
  });
  const [deleteTarget, setDeleteTarget] = useState<
    TestPlanListResponse["items"][number] | null
  >(null);

  useEffect(() => {
    const nextSearch = searchInput.trim();
    if (nextSearch === search) return;
    const timer = window.setTimeout(() => {
      setSearch(nextSearch);
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [search, searchInput]);

  useEffect(() => {
    const next = new URLSearchParams();
    if (search) next.set("search", search);
    if (tagFilter) next.set("tag", tagFilter);
    if (creatorFilter) next.set("created_by", creatorFilter);
    if (testTypeFilter) next.set("test_type", testTypeFilter);
    if (page > 1) next.set("page", String(page));
    setUrlParams(next, { replace: true });
  }, [creatorFilter, page, search, setUrlParams, tagFilter, testTypeFilter]);

  const queryString = useMemo(() => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (search) params.set("search", search);
    if (tagFilter) params.set("tag", tagFilter);
    if (creatorFilter) params.set("created_by", creatorFilter);
    if (testTypeFilter) params.set("test_type", testTypeFilter);
    return params.toString();
  }, [creatorFilter, page, search, tagFilter, testTypeFilter]);

  const plans = useQuery({
    queryKey: ["test-plans", queryString],
    queryFn: () =>
      api.get<TestPlanListResponse>(`/test-plans?${queryString}`),
    refetchInterval: 5000,
  });
  const stats = useQuery({
    queryKey: ["test-plan-stats"],
    queryFn: () => api.get<TestPlanStatsResponse>("/test-plans/stats"),
    refetchInterval: 5000,
  });
  const tags = useQuery({
    queryKey: ["test-plan-tags", "filter"],
    queryFn: () =>
      api.get<TagOptionListResponse>("/test-plans/tags"),
  });
  const creators = useQuery({
    queryKey: ["test-plan-creators"],
    queryFn: () =>
      api.get<CreatorListResponse>("/test-plans/creators"),
  });
  const deletePlan = useMutation({
    mutationFn: (planId: string) => api.delete(`/test-plans/${planId}`),
    onSuccess: async (_data, planId) => {
      queryClient.setQueryData<TestPlanListResponse>(
        ["test-plans", queryString],
        (current) => {
          if (!current) return current;
          const items = current.items.filter((item) => item.id !== planId);
          if (items.length === current.items.length) return current;
          return {
            ...current,
            items,
            total: Math.max(0, current.total - 1),
          };
        },
      );
      if ((plans.data?.items.length ?? 0) === 1 && page > 1) {
        setPage((current) => Math.max(1, current - 1));
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["test-plans"] }),
        queryClient.invalidateQueries({ queryKey: ["test-plan-stats"] }),
        queryClient.invalidateQueries({ queryKey: ["task-reports"] }),
      ]);
      setDeleteTarget(null);
    },
  });

  const metrics = stats.data ?? {
    active_plan_count: 0,
    distinct_case_count: 0,
    execution_count: 0,
    latest_completed_pass_rate: 0,
  };
  const tagOptions = [
    { value: "", label: "全部标签" },
    ...(tags.data?.items ?? []).map((tag) => ({
      value: tag.name,
      label: tag.name,
    })),
  ];
  const creatorOptions = [
    { value: "", label: "全部操作者" },
    ...(creators.data?.items ?? []).map((creator) => ({
      value: creator,
      label: creator,
    })),
  ];
  const hasFilter = Boolean(search || tagFilter || creatorFilter || testTypeFilter);

  return (
    <div className="page-container test-plan-page">
      <PageHeader
        breadcrumbs={[
          { label: "首页", to: "/tasks" },
          { label: "测试计划" },
        ]}
        title="测试计划"
        description="编排有序用例集合，按需运行并追踪每次执行"
        actions={
          <Link to="/test-plans/new" className="primary-button">
            <PlusIcon />
            新建测试计划
          </Link>
        }
      />

      <div className="metric-grid test-plan-metric-grid">
        <MetricCard
          testId="plan-metric-active"
          label="有效计划"
          value={metrics.active_plan_count}
          meta="当前可运行"
          icon={<MetricIcon path="M4 5h16v14H4zM8 9h8M8 13h5" />}
        />
        <MetricCard
          testId="plan-metric-cases"
          label="覆盖用例"
          value={metrics.distinct_case_count}
          meta="跨计划去重"
          tone="success"
          icon={<MetricIcon path="m5 12 4 4L19 6" />}
        />
        <MetricCard
          testId="plan-metric-runs"
          label="累计执行"
          value={metrics.execution_count}
          meta="全部计划历史"
          tone="running"
          icon={<MetricIcon path="M8 5v14l11-7z" />}
        />
        <MetricCard
          testId="plan-metric-rate"
          label="最近通过率"
          value={formatKpiPercent(metrics.latest_completed_pass_rate)}
          meta="各计划最近完成"
          tone="warning"
          icon={<MetricIcon path="M4 19 10 13l4 4 6-10" />}
        />
      </div>

      <div className="page-content test-plan-content">
        {stats.isError && (
          <div className="error-banner" role="alert">
            <span>统计数据加载失败，当前指标暂不可用。</span>
            <button
              type="button"
              className="secondary-button"
              aria-label="重新加载统计数据"
              onClick={() => void stats.refetch()}
            >
              重新加载
            </button>
          </div>
        )}
        <div className="filter-card">
          <div className="test-plan-filter-toolbar">
            <label className="test-plan-search">
              <span className="sr-only">搜索测试计划</span>
              <SearchIcon />
              <input
                type="search"
                name="test-plan-search"
                autoComplete="off"
                aria-label="搜索测试计划"
                placeholder="搜索测试计划名称…"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
              />
            </label>
            <SingleSelect
              label="标签筛选"
              value={tagFilter}
              options={tagOptions}
              onChange={(value) => {
                setTagFilter(value);
                setPage(1);
              }}
            />
            <SingleSelect
              label="操作者筛选"
              value={creatorFilter}
              options={creatorOptions}
              onChange={(value) => {
                setCreatorFilter(value);
                setPage(1);
              }}
            />
            <SingleSelect
              label="测试类型筛选"
              value={testTypeFilter}
              options={TEST_TYPE_OPTIONS}
              onChange={(value) => {
                setTestTypeFilter(value);
                setPage(1);
              }}
            />
            {hasFilter && (
              <button
                type="button"
                className="text-button"
                aria-label="重置筛选"
                onClick={() => {
                  setSearch("");
                  setSearchInput("");
                  setTagFilter("");
                  setCreatorFilter("");
                  setTestTypeFilter("");
                  setPage(1);
                }}
              >
                重置筛选
              </button>
            )}
          </div>
        </div>

        <div className="table-card test-plan-table-card">
          {plans.isLoading ? (
            <div
              className="test-plan-skeleton"
              role="status"
              aria-label="正在加载测试计划"
              aria-live="polite"
              aria-busy="true"
            >
              {Array.from({ length: 5 }, (_, index) => (
                <span key={index} />
              ))}
            </div>
          ) : plans.isError ? (
            <div className="empty-state error" role="alert">
              <p>
                {plans.error instanceof ApiError
                  ? plans.error.message
                  : "测试计划加载失败"}
              </p>
              <button
                type="button"
                className="secondary-button"
                onClick={() => void plans.refetch()}
              >
                重新加载
              </button>
            </div>
          ) : (plans.data?.items.length ?? 0) === 0 ? (
            hasFilter ? (
              <div className="empty-state test-plan-empty">
                <strong>无匹配结果，请调整搜索条件或表头筛选</strong>
              </div>
            ) : (
              <div className="empty-state test-plan-empty">
                <strong>暂无测试计划</strong>
                <p>创建计划后，可按固定顺序批量执行测试用例。</p>
                <Link to="/test-plans/new" className="primary-button">
                  新建测试计划
                </Link>
              </div>
            )
          ) : (
            <div className="table-scroll">
              <table className="data-table task-table test-plan-table">
                <thead>
                  <tr>
                    <th>测试计划名称</th>
                    <th>测试类型</th>
                    <th>关联用例</th>
                    <th>标签</th>
                    <th>总执行次数</th>
                    <th>最近执行结果</th>
                    <th>最近执行</th>
                    <th>定时调度</th>
                    <th>操作者</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {plans.data?.items.map((plan) => (
                    <tr key={plan.id}>
                      <td>
                        <span
                          className={`test-plan-name-wrapper${
                            shouldShowPlanNameTooltip(plan.name)
                              ? " has-tooltip"
                              : ""
                          }`}
                          {...(shouldShowPlanNameTooltip(plan.name)
                            ? { "data-full-title": plan.name }
                            : {})}
                        >
                          <span className="test-plan-name-line">
                            <Link
                              to={`/test-plans/${plan.id}`}
                              className="test-plan-name"
                              title={plan.name}
                            >
                              {plan.name}
                            </Link>
                            <CopyButton value={plan.name} label="测试计划名称" />
                          </span>
                        </span>
                        {plan.description && (
                          <span className="test-plan-description">
                            {plan.description}
                          </span>
                        )}
                      </td>
                      <td>
                        <span className={`test-plan-type-badge ${testTypeClass(plan.test_type)}`}>
                          {testTypeLabel(plan.test_type)}
                        </span>
                      </td>
                      <td className="test-plan-number">{plan.case_count}</td>
                      <td>
                        <div className="test-plan-tags">
                          {plan.tags.slice(0, 3).map((tag) => (
                            <span
                              key={tag.name}
                              className={`tag ${tagToneClass(tag.name)}`}
                            >
                              {tag.name}
                            </span>
                          ))}
                          {plan.tags.length > 3 && (
                            <span className="tag-more">
                              +{plan.tags.length - 3}
                            </span>
                          )}
                          {plan.tags.length === 0 && (
                            <span className="case-empty-value">-</span>
                          )}
                        </div>
                      </td>
                      <td className="test-plan-number">
                        {plan.execution_count}
                      </td>
                      <td>
                        {plan.latest_execution ? (
                          <span
                            className={`status-badge ${
                              statusClass(plan.latest_execution.report_status)
                            }`}
                          >
                            <span className="dot" />
                            {STATUS_LABELS[plan.latest_execution.report_status]}
                          </span>
                        ) : (
                          <span className="status-badge neutral">
                            <span className="dot" />
                            未执行
                          </span>
                        )}
                      </td>
                      <td>
                        {plan.latest_execution ? (
                          <div className="test-plan-latest">
                            <Link
                              to={`/task-reports/${
                                plan.latest_execution.execution_id
                              }`}
                              translate="no"
                            >
                              {plan.latest_execution.task_batch_id}
                            </Link>
                            <span>
                              {formatChinaDateTime(
                                plan.latest_execution.created_at,
                              )}
                            </span>
                          </div>
                        ) : (
                          <span className="case-empty-value">-</span>
                        )}
                      </td>
                      <td>
                        {plan.schedule ? (
                          <Link
                            to={`/test-plans/${plan.id}`}
                            className={`schedule-status-badge ${plan.schedule.enabled ? "enabled" : "disabled"}`}
                            title={
                              plan.schedule.enabled
                                ? `已启用 · 下次运行 ${formatChinaDateTime(plan.schedule.next_run_at)}`
                                : "已禁用"
                            }
                          >
                            <span className="dot" />
                            {plan.schedule.enabled ? "已启用" : "已禁用"}
                          </Link>
                        ) : (
                          <span className="case-empty-value">未配置</span>
                        )}
                      </td>
                      <td>{plan.created_by || <span className="case-empty-value">-</span>}</td>
                      <td>
                        <div className="row-actions test-plan-row-actions">
                          <Link
                            to={`/test-plans/${plan.id}/run`}
                            className="icon-action"
                            title="执行测试计划"
                            aria-label="执行测试计划"
                          >
                            <PlayIcon />
                          </Link>
                          <Link
                            to={`/test-plans/${plan.id}/edit`}
                            className="icon-action"
                            title="编辑测试计划"
                            aria-label="编辑测试计划"
                          >
                            <EditIcon />
                          </Link>
                          <button
                            type="button"
                            className="icon-action danger"
                            title="删除测试计划"
                            aria-label="删除测试计划"
                            disabled={deletePlan.isPending}
                            onClick={() => {
                              if (deletePlan.isPending) return;
                              deletePlan.reset();
                              setDeleteTarget(plan);
                            }}
                          >
                            <TrashIcon />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!plans.isLoading && !plans.isError && (
            <PaginationControls
              page={page}
              pageSize={PAGE_SIZE}
              total={plans.data?.total ?? 0}
              onPageChange={setPage}
              onPageSizeChange={() => setPage(1)}
              showPageSize={false}
            />
          )}
        </div>
      </div>
      <ConfirmDialog
        open={deleteTarget !== null}
        title="删除测试计划"
        description="删除后计划将无法继续运行，但历史报告不会删除，仍可在测试报告中查看。"
        confirmLabel="确认删除"
        pendingLabel="正在删除…"
        isPending={deletePlan.isPending}
        errorMessage={
          deletePlan.isError ? "删除失败，请稍后重试。" : ""
        }
        onClose={() => {
          if (!deletePlan.isPending) setDeleteTarget(null);
        }}
        onConfirm={() => {
          if (deleteTarget && !deletePlan.isPending) {
            deletePlan.mutate(deleteTarget.id);
          }
        }}
      />
    </div>
  );
}
