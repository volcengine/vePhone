import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router";
import { useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api/client";
import { useBusinessNavigate } from "../business-context";
import type {
  CaseBatchDeleteResponse,
  CaseStats,
  CreatorListResponse,
  ModuleListResponse,
  PodPoolResponse,
  TagListResponse,
  Task,
  TaskBatch,
  TaskBatchCreateRequest,
  TestCase,
  TestCaseListResponse,
} from "../api/types";
import { BusinessLink as Link } from "../components/business-link";
import { ConfirmDialog } from "../components/confirm-dialog";
import { CopyButton } from "../components/copy-button";
import { ExecuteDialog, type ExecuteConfig } from "../components/execute-dialog";
import {
  buildExecuteConfig,
  createExecutionConfigDraft,
  DeviceWaitTimeoutField,
  ExecutionConfigFields,
  type ExecutionConfigDraft,
} from "../components/execution-config-form";
import { MetricCard } from "../components/metric-card";
import { PageHeader } from "../components/page-header";
import { PaginationControls } from "../components/pagination-controls";
import { SingleSelect } from "../components/single-select";
import { tagToneClass } from "../utils/tag-tone";
import { formatChinaDate, formatChinaDateTime, parseTimestampMs } from "../utils/time";

const PAGE_SIZE = 10;
const MAX_BATCH_CONCURRENCY = 20;
const NO_ONLINE_CUA_NODE_MESSAGE = "当前没有可用的已在线 CUA 节点，请检查设备池状态或稍后重试。";

type DeviceStrategy = "automatic" | "specified";
type BulkExecuteConfig = ExecuteConfig & {
  device_strategy: DeviceStrategy;
  pod_ids: string[];
  concurrency: number;
  device_wait_timeout_seconds: number;
};

function formatRelativeTime(value: string | null): string {
  if (!value) return "从未执行";
  const ms = parseTimestampMs(value);
  if (Number.isNaN(ms)) return "从未执行";
  const diffMs = Date.now() - ms;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}小时前`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 30) return `${diffDay}天前`;
  return formatChinaDate(value);
}

function passRate(c: TestCase): number {
  if (c.execution_count === 0) return 0;
  return Math.round((c.pass_count / c.execution_count) * 100);
}

function formatPodIdentity(pod: PodPoolResponse["items"][number]): string {
  const podName = pod.pod_name?.trim();
  return podName && podName !== pod.pod_id
    ? `${podName} · ${pod.pod_id}`
    : pod.pod_id;
}

function automaticAssignablePods(pool: PodPoolResponse | undefined): PodPoolResponse["items"] {
  return (pool?.items ?? []).filter(
    (pod) =>
      pod.discovery_state === "active"
      && pod.pod_status_code === 2
      && pod.local_state === "available"
      && !pod.task_id,
  );
}

function formatPodSelectionLimitError(
  selectedCount: number,
  concurrency: number,
): string {
  return `已选择 ${selectedCount} 台设备，超过当前设备并发数 ${concurrency}。请减少设备数量，或提高设备并发数后再执行。`;
}

function initialPage(params: URLSearchParams): number {
  const value = Number(params.get("page") ?? "1");
  return Number.isInteger(value) && value > 0 ? value : 1;
}

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12h14M12 5v14" />
    </svg>
  );
}

function ImportIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16" />
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

function DuplicateIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect width="13" height="13" x="9" y="9" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function BookIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
    </svg>
  );
}

function AutomationIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m13 2-2 2.5h3L12 7" />
      <rect width="18" height="13" x="3" y="8" rx="2" />
      <path d="M8 13h.01M16 13h.01M9 17h6" />
    </svg>
  );
}

function RunsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 12h4l3-9 4 18 3-9h4" />
    </svg>
  );
}

function PassRateIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <path d="m9 11 3 3L22 4" />
    </svg>
  );
}

export function CasesPage() {
  const navigate = useBusinessNavigate();
  const queryClient = useQueryClient();
  const [urlParams, setUrlParams] = useSearchParams();
  const [page, setPage] = useState(() => initialPage(urlParams));
  const [search, setSearch] = useState(() => urlParams.get("search") ?? "");
  const [searchInput, setSearchInput] = useState(
    () => urlParams.get("search") ?? "",
  );
  const [moduleFilter, setModuleFilter] = useState<string>(
    () => urlParams.get("module") ?? "",
  );
  const [tagFilter, setTagFilter] = useState<string>(
    () => urlParams.get("tag") ?? "",
  );
  const [creatorFilter, setCreatorFilter] = useState<string>(
    () => urlParams.get("created_by") ?? "",
  );
  const [execDialogOpen, setExecDialogOpen] = useState(false);
  const [execCase, setExecCase] = useState<TestCase | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TestCase | null>(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [bulkExecuteOpen, setBulkExecuteOpen] = useState(false);
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [deleteDialogError, setDeleteDialogError] = useState("");

  const queryParams = useMemo(() => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(PAGE_SIZE));
    if (search) params.set("search", search);
    if (moduleFilter) params.set("module", moduleFilter);
    if (tagFilter) params.set("tag", tagFilter);
    if (creatorFilter) params.set("created_by", creatorFilter);
    return params.toString();
  }, [page, search, moduleFilter, tagFilter, creatorFilter]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (page > 1) params.set("page", String(page));
    if (search) params.set("search", search);
    if (moduleFilter) params.set("module", moduleFilter);
    if (tagFilter) params.set("tag", tagFilter);
    if (creatorFilter) params.set("created_by", creatorFilter);
    setUrlParams(params, { replace: true });
  }, [
    creatorFilter,
    moduleFilter,
    page,
    search,
    setUrlParams,
    tagFilter,
  ]);

  const casesQuery = useQuery({
    queryKey: ["cases", queryParams],
    queryFn: () => api.get<TestCaseListResponse>(`/cases?${queryParams}`),
    refetchInterval: 5000,
  });

  const statsQuery = useQuery({
    queryKey: ["case-stats"],
    queryFn: () => api.get<CaseStats>("/cases/stats"),
    refetchInterval: 5000,
  });

  const tagsQuery = useQuery({
    queryKey: ["case-tags"],
    queryFn: () => api.get<TagListResponse>("/cases/tags"),
  });

  const modulesQuery = useQuery({
    queryKey: ["case-modules"],
    queryFn: () => api.get<ModuleListResponse>("/cases/modules"),
  });

  const creatorsQuery = useQuery({
    queryKey: ["case-creators"],
    queryFn: () => api.get<CreatorListResponse>("/cases/creators"),
  });

  const deleteCase = useMutation({
    mutationFn: (caseId: string) => api.delete(`/cases/${caseId}`),
    onMutate: () => {
      setActionError("");
      setActionMessage("");
      setDeleteDialogError("");
    },
    onSuccess: () => {
      setDeleteTarget(null);
      setActionMessage("用例已删除。");
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      void queryClient.invalidateQueries({ queryKey: ["case-stats"] });
      void queryClient.invalidateQueries({ queryKey: ["case-tags"] });
      void queryClient.invalidateQueries({ queryKey: ["case-modules"] });
    },
    onError: (error) => {
      setDeleteDialogError(
        error instanceof ApiError && error.code === "case_has_tasks"
          ? "该用例已有执行记录，为保留任务历史暂不能删除。"
          : error instanceof ApiError && error.code === "case_has_test_plans"
          ? "该用例已绑定测试计划，请先从测试计划中移除后再删除。"
          : error instanceof ApiError
          ? `${error.message}，请刷新页面后重试。`
          : "删除用例失败，请刷新页面后重试。",
      );
    },
  });

  const copyCase = useMutation({
    mutationFn: (caseId: string) =>
      api.post<TestCase>(`/cases/${caseId}/copy`),
    onMutate: () => {
      setActionError("");
      setActionMessage("");
    },
    onSuccess: (copied) => {
      setActionMessage(`已创建副本「${copied.title}」。`);
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      void queryClient.invalidateQueries({ queryKey: ["case-stats"] });
      void queryClient.invalidateQueries({ queryKey: ["case-tags"] });
      void queryClient.invalidateQueries({ queryKey: ["case-modules"] });
    },
    onError: (error) => {
      setActionError(
        error instanceof ApiError
          ? `${error.message}，请稍后重试。`
          : "复制用例失败，请稍后重试。",
      );
    },
  });

  const executeCase = useMutation({
    mutationFn: ({ caseId, config }: { caseId: string; config: ExecuteConfig }) =>
      api.post<Task>(`/cases/${caseId}/execute`, {
        idempotency_key: `exec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        pod_id: config.pod_id,
        timeout_seconds: config.timeout_seconds,
        agent_config_mode: config.agent_config_mode,
        agent_options: config.agent_options,
      }),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      void queryClient.invalidateQueries({ queryKey: ["pod-pool"] });
      setExecDialogOpen(false);
      navigate(`/tasks/${data.id}`);
    },
  });
  const executeBatch = useMutation({
    mutationFn: (payload: TaskBatchCreateRequest) =>
      api.post<TaskBatch>("/task-batches", payload),
    onMutate: () => {
      setActionError("");
      setActionMessage("");
    },
    onSuccess: (batch) => {
      setBulkExecuteOpen(false);
      setSelectedCaseIds([]);
      setActionMessage(`已创建批量执行任务 ${batch.id}。`);
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      void queryClient.invalidateQueries({ queryKey: ["pod-pool"] });
      navigate("/tasks");
    },
    onError: (error) => {
      setActionError(
        error instanceof ApiError
          ? `${error.message}，请检查执行配置后重试。`
          : "批量执行失败，请检查执行配置后重试。",
      );
    },
  });
  const deleteCases = useMutation({
    mutationFn: (caseIds: string[]) =>
      api.post<CaseBatchDeleteResponse>("/cases/batch-delete", { case_ids: caseIds }),
    onMutate: () => {
      setActionError("");
      setActionMessage("");
      setDeleteDialogError("");
    },
    onSuccess: (result) => {
      if (result.failed_count > 0) {
        const failed = result.items
          .filter((item) => item.status === "failed")
          .slice(0, 3)
          .map((item) => `${item.case_id}: ${caseDeleteMessage(item.code)}`)
          .join("；");
        setDeleteDialogError(`部分用例删除失败：${failed}`);
        setSelectedCaseIds(
          result.items
            .filter((item) => item.status === "failed")
            .map((item) => item.case_id),
        );
        setActionMessage(
          result.deleted_count > 0 ? `已删除 ${result.deleted_count} 个用例。` : "",
        );
      } else {
        setBulkDeleteOpen(false);
        setSelectedCaseIds([]);
        setActionMessage(`已删除 ${result.deleted_count} 个用例。`);
      }
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      void queryClient.invalidateQueries({ queryKey: ["case-stats"] });
      void queryClient.invalidateQueries({ queryKey: ["case-tags"] });
      void queryClient.invalidateQueries({ queryKey: ["case-modules"] });
    },
    onError: (error) => {
      setDeleteDialogError(
        error instanceof ApiError
          ? `${error.message}，请稍后重试。`
          : "批量删除失败，请稍后重试。",
      );
    },
  });

  const totalItems = casesQuery.data?.total ?? 0;
  const items = casesQuery.data?.items ?? [];
  const kpi = statsQuery.data ?? {
    total: 0,
    auto_count: 0,
    today_executions: 0,
    total_executions: 0,
    pass_rate: 0,
  };
  const hasFilter = Boolean(search || moduleFilter || tagFilter);
  const selectedCases = selectedCaseIds
    .map((caseId) => items.find((item) => item.id === caseId))
    .filter((item): item is TestCase => Boolean(item));
  const selectedCount = selectedCaseIds.length;
  const allPageSelected = items.length > 0
    && items.every((item) => selectedCaseIds.includes(item.id));
  const moduleOptions = useMemo(
    () => [
      { value: "", label: "全部模块" },
      ...(modulesQuery.data?.items ?? []).map((module) => ({
        value: module,
        label: module,
      })),
    ],
    [modulesQuery.data?.items],
  );
  const tagOptions = useMemo(
    () => [
      { value: "", label: "全部标签" },
      ...(tagsQuery.data?.items ?? []).map((tag) => ({
        value: tag,
        label: tag,
      })),
    ],
    [tagsQuery.data?.items],
  );
  const creatorOptions = useMemo(
    () => [
      { value: "", label: "全部创建人" },
      ...(creatorsQuery.data?.items ?? []).map((creator) => ({
        value: creator,
        label: creator,
      })),
    ],
    [creatorsQuery.data?.items],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    setSelectedCaseIds((current) => {
      const next = current.filter((caseId) =>
        items.some((item) => item.id === caseId),
      );
      return next.length === current.length ? current : next;
    });
  }, [items]);

  function handleFilterChange(type: "module" | "tag" | "creator", value: string) {
    setPage(1);
    if (type === "module") setModuleFilter(value);
    if (type === "tag") setTagFilter(value);
    if (type === "creator") setCreatorFilter(value);
  }

  function toggleCaseSelection(caseId: string) {
    setSelectedCaseIds((current) =>
      current.includes(caseId)
        ? current.filter((item) => item !== caseId)
        : [...current, caseId],
    );
  }

  function togglePageSelection() {
    setSelectedCaseIds((current) => {
      if (allPageSelected) {
        return current.filter((caseId) => !items.some((item) => item.id === caseId));
      }
      const next = new Set(current);
      items.forEach((item) => next.add(item.id));
      return [...next];
    });
  }

  function exportSelectedCases() {
    const rows = selectedCases.map((item) => ({
      title: item.title,
      module: item.module ?? "",
      tags: item.tags.join("|"),
      content_markdown: item.content_markdown,
    }));
    const csv = [
      ["title", "module", "tags", "content_markdown"],
      ...rows.map((row) => [
        row.title,
        row.module,
        row.tags,
        row.content_markdown,
      ]),
    ].map((row) => row.map(csvEscape).join(",")).join("\n");
    downloadText(
      `mua-cases-${new Date().toISOString().slice(0, 10)}.csv`,
      csv,
      "text/csv;charset=utf-8",
    );
    setActionMessage(`已导出 ${selectedCases.length} 个用例。`);
  }

  function executeSelectedCases(config: ExecuteConfig) {
    if (selectedCaseIds.length === 1) {
      executeCase.mutate({ caseId: selectedCaseIds[0], config });
      return;
    }
  }

  function executeSelectedBatch(config: BulkExecuteConfig) {
    executeBatch.mutate({
      name: `批量执行 ${selectedCaseIds.length} 个用例`,
      test_type: "regression",
      selection_mode: "multi_cases",
      case_ids: selectedCaseIds,
      selection_snapshot: { case_ids: selectedCaseIds },
      device_strategy: config.device_strategy,
      pod_ids: config.device_strategy === "specified" ? config.pod_ids : [],
      concurrency: config.concurrency,
      device_wait_timeout_seconds: config.device_wait_timeout_seconds,
      timeout_seconds: config.timeout_seconds,
      agent_config_mode: config.agent_config_mode,
      agent_options: config.agent_options,
      idempotency_key: `batch_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    });
  }

  return (
    <div className="page-container cases-page">
      <PageHeader
        breadcrumbs={[{ label: "首页", to: "/tasks" }, { label: "用例库" }]}
        title="用例库"
        description="管理所有 Markdown 格式的自动化测试用例"
        actions={
          <>
            <Link to="/cases/import/preview" className="secondary-button">
              <ImportIcon />
              <span>导入用例</span>
            </Link>
            <Link to="/cases/new" className="primary-button">
              <PlusIcon />
              <span>新建用例</span>
            </Link>
          </>
        }
      />
      <div className="metric-grid case-metric-grid">
        <MetricCard
          testId="case-metric-total"
          label="用例总数"
          value={kpi.total}
          meta="全部测试资产"
          icon={<BookIcon />}
        />
        <MetricCard
          testId="case-metric-today"
          label="今日执行"
          value={kpi.today_executions}
          meta="中国时区今日"
          tone="success"
          icon={<AutomationIcon />}
        />
        <MetricCard
          testId="case-metric-executions"
          label="累计执行"
          value={kpi.total_executions}
          meta="全部历史执行"
          tone="running"
          icon={<RunsIcon />}
        />
        <MetricCard
          testId="case-metric-pass-rate"
          label="通过率"
          value={`${kpi.pass_rate}%`}
          meta="全部已执行用例"
          tone="warning"
          icon={<PassRateIcon />}
        />
      </div>
      <div className="page-content case-content-compact">
        {actionMessage && (
          <div className="case-action-message" aria-live="polite">
            {actionMessage}
          </div>
        )}
        {actionError && (
          <div className="error-banner" role="alert">
            {actionError}
          </div>
        )}
        <div className="filter-card">
          <div className="case-filter-toolbar task-filter-bar">
            <div className="case-filter-search task-search">
              <SearchIcon />
              <input
                aria-label="搜索用例"
                autoComplete="off"
                name="case-search"
                type="search"
                placeholder="搜索用例名称、ID 或模块…"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>
            <SingleSelect
              label="模块筛选"
              value={moduleFilter}
              options={moduleOptions}
              onChange={(value) => handleFilterChange("module", value)}
            />
            <SingleSelect
              label="标签筛选"
              value={tagFilter}
              options={tagOptions}
              onChange={(value) => handleFilterChange("tag", value)}
            />
            <SingleSelect
              label="创建人筛选"
              value={creatorFilter}
              options={creatorOptions}
              onChange={(value) => handleFilterChange("creator", value)}
            />
            {(search || moduleFilter || tagFilter || creatorFilter) && (
              <button
                type="button"
                className="text-button"
                aria-label="重置筛选"
                onClick={() => {
                  setSearch("");
                  setSearchInput("");
                  setModuleFilter("");
                  setTagFilter("");
                  setCreatorFilter("");
                  setPage(1);
                }}
              >
                重置筛选
              </button>
            )}
          </div>
        </div>

        {selectedCount > 0 && (
          <div className="case-bulk-action-bar" aria-live="polite">
            <strong>已选择 {selectedCount} 个用例</strong>
            <span>仅对当前已勾选用例生效</span>
            <div className="case-bulk-action-spacer" />
            <button
              type="button"
              className="case-bulk-action-button"
              onClick={() => setSelectedCaseIds([])}
            >
              清空选择
            </button>
            <button
              type="button"
              className="case-bulk-action-button run"
              onClick={() => setBulkExecuteOpen(true)}
            >
              批量执行
            </button>
            <button
              type="button"
              className="case-bulk-action-button export"
              onClick={exportSelectedCases}
            >
              批量导出
            </button>
            <button
              type="button"
              className="case-bulk-action-button danger"
              onClick={() => {
                setDeleteDialogError("");
                setBulkDeleteOpen(true);
              }}
            >
              批量删除
            </button>
          </div>
        )}

        <div className="table-card">
          {casesQuery.isLoading ? (
            <div className="empty-state">加载中…</div>
          ) : casesQuery.isError ? (
            <div className="empty-state error">
              加载失败：{casesQuery.error instanceof ApiError ? casesQuery.error.message : "未知错误"}
            </div>
          ) : items.length === 0 ? (
            hasFilter ? (
              <div className="empty-state">
                <p>无匹配结果，请调整搜索条件或表头筛选</p>
              </div>
            ) : (
              <div className="empty-state">
                <p>暂无用例</p>
                <Link to="/cases/new" className="primary-button" style={{ marginTop: 12 }}>
                  <PlusIcon />
                  <span>创建第一个用例</span>
                </Link>
              </div>
            )
          ) : (
            <div className="table-scroll">
              <table className="data-table task-table cases-table">
                <thead>
                  <tr>
                    <th className="sticky-col case-sticky-header" style={{ minWidth: 310 }} aria-label="用例ID">
                      <label className="case-select-all">
                        <input
                          type="checkbox"
                          aria-label={allPageSelected ? "取消选择当前页用例" : "选择当前页用例"}
                          checked={allPageSelected}
                          onChange={togglePageSelection}
                        />
                        <span>用例ID</span>
                      </label>
                    </th>
                    <th style={{ minWidth: 200 }}>用例名称</th>
                    <th style={{ width: 100 }}>模块</th>
                    <th style={{ minWidth: 160 }}>标签</th>
                    <th style={{ width: 90 }}>关联计划</th>
                    <th style={{ width: 80 }}>执行次数</th>
                    <th style={{ width: 80 }}>通过率</th>
                    <th style={{ width: 130 }}>最近执行</th>
                    <th style={{ width: 80 }}>创建人</th>
                    <th style={{ width: 100 }}>更新时间</th>
                    <th className="case-actions-cell" style={{ width: 160 }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => {
                    const rate = passRate(c);
                    const boundPlanCount = c.bound_plan_count ?? 0;
                    return (
                      <tr key={c.id}>
                        <td className="sticky-col">
                          <div className="case-select-id-cell">
                            <input
                              type="checkbox"
                              aria-label={`选择用例 ${c.title} ${c.id}`}
                              checked={selectedCaseIds.includes(c.id)}
                              onChange={() => toggleCaseSelection(c.id)}
                            />
                            <div className="cell-id-copy">
                              <span
                                className="monospace cell-id-full"
                                translate="no"
                                style={{ fontSize: "0.75rem", color: "var(--mua-neutral-500)" }}
                                title={c.id}
                              >
                                {c.id}
                              </span>
                              <CopyButton value={c.id} label="用例ID" />
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="case-name-wrapper" data-full-title={c.title}>
                            <Link to={`/cases/${c.id}/edit`} className="case-name-link case-name-link-neutral">
                              {c.title}
                            </Link>
                          </span>
                        </td>
                        <td className="cell-truncate" style={{ fontSize: "0.8rem" }}>
                          {c.module || <span style={{ color: "var(--mua-neutral-400)" }}>—</span>}
                        </td>
                        <td>
                          <div className="tag-list">
                            {c.tags.slice(0, 3).map((t) => (
                              <button
                                key={t}
                                type="button"
                                className={`tag tag-clickable ${tagToneClass(t)}${tagFilter === t ? " tag-active" : ""}`}
                                title={tagFilter === t ? `取消筛选「${t}」` : `按标签「${t}」筛选`}
                                onClick={() => handleFilterChange("tag", tagFilter === t ? "" : t)}
                              >
                                {t}
                              </button>
                            ))}
                            {c.tags.length > 3 && (
                              <span className="tag-more">+{c.tags.length - 3}</span>
                            )}
                            {c.tags.length === 0 && <span style={{ color: "var(--mua-neutral-400)", fontSize: "0.8rem" }}>—</span>}
                          </div>
                        </td>
                        <td className="case-number-cell">
                          {boundPlanCount > 0 ? boundPlanCount : "-"}
                        </td>
                        <td className="case-number-cell">
                          {c.execution_count}
                        </td>
                        <td className="case-number-cell">
                          <span className={`case-rate ${rate >= 80 ? "success" : rate >= 50 ? "warning" : "danger"}`}>
                            {rate}%
                          </span>
                        </td>
                        <td>
                          {c.last_executed_at ? (
                            <span
                              className="case-relative-time"
                              title={formatChinaDateTime(c.last_executed_at)}
                            >
                              {formatRelativeTime(c.last_executed_at)}
                            </span>
                          ) : (
                            <span className="case-empty-value">从未执行</span>
                          )}
                        </td>
                        <td>
                          <span className="case-owner-text">{c.created_by}</span>
                        </td>
                        <td style={{ fontSize: "0.75rem", color: "var(--mua-neutral-500)", whiteSpace: "nowrap" }}>
                          {formatChinaDateTime(c.updated_at)}
                        </td>
                        <td className="case-actions-cell">
                          <div className="row-actions case-row-actions">
                            <button
                              type="button"
                              className="icon-action"
                              title="执行用例"
                              aria-label="执行用例"
                              onClick={() => { setExecCase(c); setExecDialogOpen(true); }}
                              disabled={executeCase.isPending}
                            >
                              <PlayIcon />
                            </button>
                            <Link
                              to={`/cases/${c.id}/edit`}
                              className="icon-action"
                              title="编辑用例"
                              aria-label="编辑用例"
                            >
                              <EditIcon />
                            </Link>
                            <button
                              type="button"
                              className="icon-action"
                              title="复制用例"
                              aria-label="复制用例"
                              onClick={() => copyCase.mutate(c.id)}
                              disabled={copyCase.isPending}
                            >
                              <DuplicateIcon />
                            </button>
                            <button
                              type="button"
                              className="icon-action danger"
                              title="删除用例"
                              aria-label="删除用例"
                              onClick={() => setDeleteTarget(c)}
                              disabled={deleteCase.isPending}
                            >
                              <TrashIcon />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {!casesQuery.isLoading && !casesQuery.isError && (
            <PaginationControls
              page={page}
              pageSize={PAGE_SIZE}
              total={totalItems}
              onPageChange={setPage}
              onPageSizeChange={() => setPage(1)}
              showPageSize={false}
            />
          )}
        </div>
      </div>

      <ExecuteDialog
        open={execDialogOpen}
        caseTitle={execCase?.title ?? ""}
        onClose={() => { setExecDialogOpen(false); setExecCase(null); }}
        onConfirm={(config) => {
          if (execCase) executeCase.mutate({ caseId: execCase.id, config });
        }}
        isPending={executeCase.isPending}
        allowCaseDefault={Boolean(execCase?.default_agent_options)}
        errorMessage={
          executeCase.error instanceof ApiError
            ? `${executeCase.error.message}，请检查设备与执行配置后重试。`
            : executeCase.isError
              ? "创建任务失败，请检查设备与执行配置后重试。"
              : ""
        }
      />
      {selectedCount === 1 ? (
        <ExecuteDialog
          open={bulkExecuteOpen}
          caseTitle={`${selectedCount} 个用例`}
          onClose={() => setBulkExecuteOpen(false)}
          onConfirm={executeSelectedCases}
          isPending={executeBatch.isPending || executeCase.isPending}
          allowCaseDefault={false}
          errorMessage={actionError}
        />
      ) : (
        <BulkExecuteDialog
          open={bulkExecuteOpen}
          selectedCount={selectedCount}
          onClose={() => setBulkExecuteOpen(false)}
          onConfirm={executeSelectedBatch}
          isPending={executeBatch.isPending}
          errorMessage={actionError}
        />
      )}
      <ConfirmDialog
        open={deleteTarget !== null}
        title="删除用例"
        description={deleteTarget
          ? `确定删除「${deleteTarget.title}」吗？删除后将从用例库和测试计划候选列表中隐藏，历史执行记录仍保留。`
          : ""}
        confirmLabel="确认删除"
        pendingLabel="删除中…"
        isPending={deleteCase.isPending}
        errorMessage={deleteDialogError}
        onClose={() => {
          setDeleteTarget(null);
          setDeleteDialogError("");
        }}
        onConfirm={() => {
          if (deleteTarget) deleteCase.mutate(deleteTarget.id);
        }}
      />
      <ConfirmDialog
        open={bulkDeleteOpen}
        title="批量删除用例"
        description={`将尝试删除已选择的 ${selectedCount} 个用例。`}
        confirmLabel="确认删除"
        pendingLabel="删除中…"
        isPending={deleteCases.isPending}
        errorMessage={deleteDialogError}
        onClose={() => {
          setBulkDeleteOpen(false);
          setDeleteDialogError("");
        }}
        onConfirm={() => deleteCases.mutate(selectedCaseIds)}
      >
        <div className="case-delete-policy-card">
          <div className="case-delete-policy-icon" aria-hidden="true">!</div>
          <div>
            <strong>删除前会自动校验用例状态</strong>
            <p>
              仍绑定有效测试计划，或存在排队中、运行中或正在生成脚本任务的用例不会被删除。
            </p>
          </div>
        </div>
        <ul className="case-delete-policy-list">
          <li>已有完成、失败、中断或取消记录的用例允许软删除，历史执行记录仍保留。</li>
          <li>删除后用例将从用例库和测试计划候选列表中隐藏，不能再被新任务引用。</li>
        </ul>
      </ConfirmDialog>
    </div>
  );
}

function BulkExecuteDialog({
  open,
  selectedCount,
  onClose,
  onConfirm,
  isPending,
  errorMessage = "",
}: {
  open: boolean;
  selectedCount: number;
  onClose: () => void;
  onConfirm: (config: BulkExecuteConfig) => void;
  isPending?: boolean;
  errorMessage?: string;
}) {
  const [deviceStrategy, setDeviceStrategy] =
    useState<DeviceStrategy>("automatic");
  const [concurrency, setConcurrency] = useState(1);
  const [selectedPodIds, setSelectedPodIds] = useState<string[]>([]);
  const [draft, setDraft] = useState<ExecutionConfigDraft>(
    createExecutionConfigDraft,
  );
  const [formError, setFormError] = useState("");
  const [podSearch, setPodSearch] = useState("");
  const maxConcurrency = Math.max(
    1,
    Math.min(selectedCount || 1, MAX_BATCH_CONCURRENCY),
  );
  const pods = useQuery({
    queryKey: ["pod-pool", "cases-bulk-execute"],
    queryFn: () => api.post<PodPoolResponse>("/pod-pool/refresh"),
    enabled: open,
    refetchInterval: open && !isPending ? 3000 : false,
  });
  const selectablePods = useMemo(
    () => (pods.data?.items ?? []).filter(
      (pod) =>
        pod.discovery_state === "active"
        && pod.pod_status_code === 2,
    ),
    [pods.data],
  );
  const selectablePodIds = useMemo(
    () => new Set(selectablePods.map((pod) => pod.pod_id)),
    [selectablePods],
  );
  const visibleSelectablePods = useMemo(() => {
    const keyword = podSearch.trim().toLowerCase();
    if (!keyword) return selectablePods;
    return selectablePods.filter((pod) =>
      `${pod.pod_name ?? ""} ${pod.pod_id} ${pod.local_state ?? ""}`
        .toLowerCase()
        .includes(keyword));
  }, [podSearch, selectablePods]);

  useEffect(() => {
    if (!open) return;
    setDeviceStrategy("automatic");
    setConcurrency(maxConcurrency);
    setSelectedPodIds([]);
    setDraft(createExecutionConfigDraft());
    setFormError("");
    setPodSearch("");
  }, [maxConcurrency, open]);

  useEffect(() => {
    setConcurrency((current) => Math.max(1, Math.min(current, maxConcurrency)));
    setSelectedPodIds((current) =>
      current
        .filter((podId) => selectablePodIds.has(podId))
        .slice(0, maxConcurrency));
  }, [maxConcurrency, selectablePodIds]);

  if (!open) return null;

  function selectDeviceStrategy(strategy: DeviceStrategy) {
    if (isPending) return;
    setDeviceStrategy(strategy);
    setFormError("");
    if (strategy === "automatic") {
      setSelectedPodIds([]);
      setPodSearch("");
    }
  }

  function togglePod(podId: string) {
    if (isPending || !selectablePodIds.has(podId)) return;
    const selected = selectedPodIds.includes(podId);
    if (!selected && selectedPodIds.length >= concurrency) {
      setFormError(
        formatPodSelectionLimitError(selectedPodIds.length + 1, concurrency),
      );
      return;
    }
    setSelectedPodIds((current) =>
      current.includes(podId)
        ? current.filter((item) => item !== podId)
        : [...current, podId]);
    setFormError("");
  }

  async function submit() {
    if (isPending) return;
    const result = buildExecuteConfig(draft);
    setFormError(result.error);
    if (!result.config) return;
    if (deviceStrategy === "specified") {
      if (pods.isError || !pods.data) {
        setFormError("设备池刷新失败，请重新加载设备池后再提交。");
        return;
      }
      if (selectedPodIds.some((podId) => !selectablePodIds.has(podId))) {
        setFormError("设备状态已更新，请重新选择可用设备。");
        return;
      }
      if (selectedPodIds.length === 0) {
        setFormError("指定设备模式至少选择 1 台设备。");
        return;
      }
      if (selectedPodIds.length > concurrency) {
        setFormError(
          formatPodSelectionLimitError(selectedPodIds.length, concurrency),
        );
        return;
      }
    }

    let effectiveConcurrency = Math.min(concurrency, selectedCount, MAX_BATCH_CONCURRENCY);
    if (deviceStrategy === "automatic") {
      const refreshed = await pods.refetch();
      if (!refreshed.data) {
        setFormError("设备池刷新失败，请重新加载设备池后再提交。");
        return;
      }
      const onlinePods = automaticAssignablePods(refreshed.data);
      if (onlinePods.length === 0) {
        setFormError(NO_ONLINE_CUA_NODE_MESSAGE);
        return;
      }
      effectiveConcurrency = Math.min(effectiveConcurrency, onlinePods.length);
    }

    onConfirm({
      ...result.config,
      device_strategy: deviceStrategy,
      pod_ids: deviceStrategy === "specified" ? selectedPodIds : [],
      concurrency: effectiveConcurrency,
      device_wait_timeout_seconds: draft.device_wait_timeout_seconds,
    });
  }

  return (
    <div
      className="modal-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isPending) onClose();
      }}
    >
      <div
        className="modal-panel execute-dialog-panel wide"
        role="dialog"
        aria-modal="true"
        aria-label="批量执行配置"
      >
        <div className="modal-header">
          <h3>批量执行配置</h3>
          <button
            type="button"
            className="icon-action"
            onClick={onClose}
            aria-label="关闭"
            disabled={isPending}
          >
            ×
          </button>
        </div>
        <div className="modal-body">
          <p className="modal-case-title">
            <PlayIcon />
            <span>{selectedCount} 个用例</span>
          </p>
          <section className="plan-run-section">
            <div className="plan-section-heading">
              <div>
                <span className="section-kicker">设备策略</span>
                <h2>配置并发和设备范围</h2>
              </div>
            </div>
            <div className="plan-run-device-row">
              <div className="plan-run-strategy-grid">
                <label className={deviceStrategy === "automatic" ? "selected" : ""}>
                  <input
                    type="radio"
                    aria-label="自动分配"
                    name="case-bulk-device-strategy"
                    value="automatic"
                    checked={deviceStrategy === "automatic"}
                    onChange={() => selectDeviceStrategy("automatic")}
                  />
                  <strong>自动分配</strong>
                  <span>从当前设备池中动态分配空闲设备</span>
                </label>
                <label className={deviceStrategy === "specified" ? "selected" : ""}>
                  <input
                    type="radio"
                    aria-label="指定设备"
                    name="case-bulk-device-strategy"
                    value="specified"
                    checked={deviceStrategy === "specified"}
                    onChange={() => selectDeviceStrategy("specified")}
                  />
                  <strong>指定设备</strong>
                  <span>仅在选中的设备范围内持续排队</span>
                </label>
              </div>
              <label className="plan-run-field plan-run-concurrency">
                <span>设备并发数</span>
                <input
                  name="concurrency"
                  autoComplete="off"
                  type="number"
                  aria-label="设备并发数"
                  min={1}
                  max={maxConcurrency}
                  value={concurrency}
                  onChange={(event) => {
                    const next = Math.max(
                      1,
                      Math.min(maxConcurrency, Number(event.target.value) || 1),
                    );
                    setConcurrency(next);
                    setFormError(
                      selectedPodIds.length > next
                        ? formatPodSelectionLimitError(selectedPodIds.length, next)
                        : "",
                    );
                  }}
                  disabled={isPending}
                />
                <small>最大不超过 {maxConcurrency} 个并发任务</small>
              </label>
            </div>
            {deviceStrategy === "specified" && (
              <div className="plan-run-device-select">
                {pods.isLoading ? (
                  <p className="muted" role="status">正在加载设备池…</p>
                ) : pods.isError ? (
                  <div className="form-error" role="alert">
                    设备池加载失败，请重新加载。
                  </div>
                ) : selectablePods.length === 0 ? (
                  <div className="plan-case-empty">暂无可选设备</div>
                ) : (
                  <div className="plan-run-field plan-run-pod-field">
                    <span id="case-bulk-pod-list-label">设备选择</span>
                    <div className="plan-run-pod-panel">
                      <div className="plan-run-pod-toolbar">
                        <label className="plan-run-pod-search">
                          <span className="sr-only">搜索设备</span>
                          <input
                            type="search"
                            className="plan-run-pod-search-input"
                            aria-label="搜索设备"
                            placeholder="搜索设备 ID / 名称"
                            value={podSearch}
                            onChange={(event) => setPodSearch(event.target.value)}
                            disabled={isPending}
                          />
                        </label>
                        <span className="plan-run-pod-quota">
                          {selectedPodIds.length} / {concurrency}
                        </span>
                      </div>
                      <div
                        className="plan-run-pod-list"
                        role="group"
                        aria-labelledby="case-bulk-pod-list-label"
                      >
                        {visibleSelectablePods.map((pod) => {
                          const selected = selectedPodIds.includes(pod.pod_id);
                          const disabled = (
                            Boolean(isPending)
                            || (
                              !selected
                              && selectedPodIds.length >= concurrency
                            )
                          );
                          return (
                            <label
                              key={pod.pod_id}
                              className={[
                                "plan-run-pod-option",
                                selected ? "selected" : "",
                                disabled ? "disabled" : "",
                              ].filter(Boolean).join(" ")}
                            >
                              <input
                                type="checkbox"
                                name="pod_ids"
                                value={pod.pod_id}
                                checked={selected}
                                disabled={disabled}
                                aria-label={`${pod.pod_name} ${pod.pod_id}`}
                                onChange={() => togglePod(pod.pod_id)}
                              />
                              <span>
                                <strong>{formatPodIdentity(pod)}</strong>
                                <code translate="no">{pod.pod_id}</code>
                              </span>
                              <em className={pod.local_state === "available" ? "available" : "busy"}>
                                {pod.local_state === "available" ? "可用" : "繁忙 · 将排队"}
                              </em>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
          <section className="plan-run-section">
            <div className="plan-section-heading">
              <div>
                <span className="section-kicker">调度配置</span>
                <h2>调度配置</h2>
              </div>
            </div>
            <DeviceWaitTimeoutField
              id="case-bulk-device-wait-timeout-seconds"
              value={draft.device_wait_timeout_seconds}
              onChange={(next) => {
                setDraft({
                  ...draft,
                  device_wait_timeout_seconds: next,
                });
                setFormError("");
              }}
              disabled={isPending}
            />
          </section>
          <ExecutionConfigFields
            value={draft}
            onChange={(next) => {
              setDraft(next);
              setFormError("");
            }}
            disabled={Boolean(isPending)}
            allowCaseDefault={false}
          />
          {formError && <p className="form-error" role="alert">{formError}</p>}
          {errorMessage && <p className="form-error" role="alert">{errorMessage}</p>}
        </div>
        <div className="modal-footer">
          <button
            type="button"
            className="secondary-button"
            onClick={onClose}
            disabled={isPending}
          >
            取消
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={() => void submit()}
            disabled={isPending}
          >
            <PlayIcon />
            <span>{isPending ? "提交中…" : "开始执行"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function csvEscape(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function downloadText(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function caseDeleteMessage(code: string | null): string {
  if (code === "case_has_tasks") return "存在排队中或运行中的任务";
  if (code === "case_has_test_plans") return "已绑定测试计划";
  if (code === "case_not_found") return "用例不存在";
  return "删除失败";
}
