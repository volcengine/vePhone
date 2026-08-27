import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  useBlocker,
  useLocation,
  useParams,
} from "react-router";

import { ApiError, api } from "../api/client";
import { useBusinessNavigate } from "../business-context";
import type {
  ModuleListResponse,
  TagOption,
  TagOptionListResponse,
  TestCase,
  TestCaseListResponse,
  TestPlan,
  TestPlanCaseListResponse,
  TestType,
  TestPlanWrite,
} from "../api/types";
import {
  MultiSelect,
  type MultiSelectOption,
} from "../components/multi-select";
import { BusinessLink as Link } from "../components/business-link";
import { ConfirmDialog } from "../components/confirm-dialog";
import { PageHeader } from "../components/page-header";
import { PaginationControls } from "../components/pagination-controls";
import { SingleSelect } from "../components/single-select";
import { formatChinaDateTime } from "../utils/time";

type PageSize = 10 | 20 | 50;

const TEST_TYPE_LABELS: Record<TestType, string> = {
  new_feature: "新功能测试",
  regression: "回归测试",
};

const TEST_TYPE_OPTIONS: Array<{ value: TestType; label: string }> = [
  { value: "regression", label: TEST_TYPE_LABELS.regression },
  { value: "new_feature", label: TEST_TYPE_LABELS.new_feature },
];

function tagOptions(items: TagOption[]): MultiSelectOption[] {
  return items.map((item) => ({
    value: item.name,
    label: item.name,
    count: item.case_count ?? undefined,
    foregroundColor: item.foreground_color,
    backgroundColor: item.background_color,
  }));
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

async function loadAllPlanCases(planId: string): Promise<TestCase[]> {
  const first = await api.get<TestPlanCaseListResponse>(
    `/test-plans/${planId}/cases?page=1&page_size=10`,
  );
  const items = [...first.items];
  const pages = Math.ceil(first.total / 10);
  for (let page = 2; page <= pages; page += 1) {
    const next = await api.get<TestPlanCaseListResponse>(
      `/test-plans/${planId}/cases?page=${page}&page_size=10`,
    );
    items.push(...next.items);
  }
  return items;
}

async function loadAllTags(): Promise<TagOptionListResponse> {
  const first = await api.get<TagOptionListResponse>(
    "/tags?page=1&page_size=100",
  );
  const items = [...first.items];
  const pages = Math.ceil(first.total / 100);
  for (let page = 2; page <= pages; page += 1) {
    const next = await api.get<TagOptionListResponse>(
      `/tags?page=${page}&page_size=100`,
    );
    items.push(...next.items);
  }
  return {
    items,
    total: first.total,
    page: 1,
    page_size: 100,
  };
}

function caseTagStyle(
  tagName: string,
  colors: Map<string, TagOption>,
): React.CSSProperties | undefined {
  const tag = colors.get(tagName);
  return tag
    ? {
        color: tag.foreground_color,
        backgroundColor: tag.background_color,
      }
    : undefined;
}

function friendlyError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "保存测试计划失败，请稍后重试。";
  }
  if (error.code === "test_plan_name_conflict") {
    return "已有同名测试计划，请修改名称后重试。";
  }
  if (error.code === "test_plan_cases_not_found") {
    return "部分用例已被删除，请刷新候选用例后重新选择。";
  }
  if (error.code === "tag_color_registry_exhausted") {
    return "标签颜色资源已用尽，请联系管理员处理。";
  }
  return `${error.message}，请稍后重试。`;
}

export function TestPlanEditorPage() {
  const navigate = useBusinessNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { planId } = useParams<{ planId: string }>();
  const isNew = location.pathname.endsWith("/test-plans/new");
  const editingId = isNew ? null : planId;
  const nameRef = useRef<HTMLInputElement>(null);
  const initializedRef = useRef<string | null>(null);
  const savePendingRef = useRef(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [testType, setTestType] = useState<TestType>("regression");
  const [planTags, setPlanTags] = useState<string[]>([]);
  const [planTagInput, setPlanTagInput] = useState("");
  const [selectedCases, setSelectedCases] = useState<TestCase[]>([]);
  const [selectedPage, setSelectedPage] = useState(1);
  const [selectedPageSize, setSelectedPageSize] = useState<PageSize>(10);
  const [candidatePage, setCandidatePage] = useState(1);
  const [candidatePageSize, setCandidatePageSize] = useState<PageSize>(10);
  const [candidateSearchInput, setCandidateSearchInput] = useState("");
  const [candidateSearch, setCandidateSearch] = useState("");
  const [candidateModule, setCandidateModule] = useState("");
  const [candidateTags, setCandidateTags] = useState<string[]>([]);
  const [candidateTagSearch, setCandidateTagSearch] = useState("");
  const [validationError, setValidationError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saveCompleted, setSaveCompleted] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (savePendingRef.current) return;
      setCandidateSearch(candidateSearchInput.trim());
      setCandidatePage(1);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [candidateSearchInput]);

  const plan = useQuery({
    queryKey: ["test-plan", editingId],
    queryFn: () => api.get<TestPlan>(`/test-plans/${editingId}`),
    enabled: Boolean(editingId),
  });
  const boundCases = useQuery({
    queryKey: ["test-plan-all-cases", editingId],
    queryFn: () => loadAllPlanCases(editingId as string),
    enabled: Boolean(editingId),
  });
  const tags = useQuery({
    queryKey: ["tags", "all"],
    queryFn: loadAllTags,
  });
  const modules = useQuery({
    queryKey: ["case-modules"],
    queryFn: () => api.get<ModuleListResponse>("/cases/modules"),
  });

  useEffect(() => {
    if (
      !editingId
      || !plan.data
      || !boundCases.data
      || initializedRef.current === editingId
    ) {
      return;
    }
    initializedRef.current = editingId;
    setName(plan.data.name);
    setDescription(plan.data.description ?? "");
    setTestType(plan.data.test_type);
    setPlanTags(plan.data.tags.map((tag) => tag.name));
    setSelectedCases(boundCases.data);
    setDirty(false);
  }, [boundCases.data, editingId, plan.data]);

  const candidateParams = useMemo(() => {
    const params = new URLSearchParams({
      page: String(candidatePage),
      page_size: String(candidatePageSize),
    });
    if (candidateSearch) params.set("search", candidateSearch);
    if (candidateModule) params.set("module", candidateModule);
    for (const tag of candidateTags) params.append("tag", tag);
    return params.toString();
  }, [
    candidateModule,
    candidatePage,
    candidatePageSize,
    candidateSearch,
    candidateTags,
  ]);
  const candidates = useQuery({
    queryKey: ["cases", "plan-candidates", candidateParams],
    queryFn: () =>
      api.get<TestCaseListResponse>(`/cases?${candidateParams}`),
  });

  const writePlan = useMutation({
    mutationFn: (payload: TestPlanWrite) =>
      isNew
        ? api.post<TestPlan>("/test-plans", payload)
        : api.put<TestPlan>(`/test-plans/${editingId}`, payload),
    onSuccess: async () => {
      setDirty(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["test-plans"] }),
        queryClient.invalidateQueries({ queryKey: ["test-plan-stats"] }),
        queryClient.invalidateQueries({ queryKey: ["tags"] }),
      ]);
      setSaveCompleted(true);
    },
    onError: (error) => setSaveError(friendlyError(error)),
  });

  useEffect(() => {
    savePendingRef.current = writePlan.isPending;
  }, [writePlan.isPending]);

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      (writePlan.isPending || dirty)
      && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    if (blocker.state === "blocked" && writePlan.isPending) {
      blocker.reset();
    }
  }, [blocker, writePlan.isPending]);

  useEffect(() => {
    if (!dirty && !writePlan.isPending) return;
    function warn(event: BeforeUnloadEvent) {
      event.preventDefault();
    }
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, writePlan.isPending]);

  useEffect(() => {
    if (!saveCompleted || writePlan.isPending) return;
    setSaveCompleted(false);
    navigate("/test-plans");
  }, [navigate, saveCompleted, writePlan.isPending]);

  const registry = tags.data?.items ?? [];
  const registryByName = useMemo(
    () => new Map(registry.map((tag) => [tag.name, tag])),
    [registry],
  );
  const allTagOptions = useMemo(() => tagOptions(registry), [registry]);
  const candidateTagOptions = allTagOptions.filter((option) =>
    option.label.toLocaleLowerCase().includes(
      candidateTagSearch.toLocaleLowerCase(),
    )
  );
  const moduleOptions = [
    { value: "", label: "全部模块" },
    ...(modules.data?.items ?? []).map((module) => ({
      value: module,
      label: module,
    })),
  ];
  const selectedIds = new Set(selectedCases.map((item) => item.id));
  const selectedStart = (selectedPage - 1) * selectedPageSize;
  const selectedPageItems = selectedCases.slice(
    selectedStart,
    selectedStart + selectedPageSize,
  );

  function markDirty() {
    if (writePlan.isPending) return;
    setDirty(true);
    setSaveError("");
    setValidationError("");
  }

  function addPlanTag() {
    if (writePlan.isPending) return;
    const tag = planTagInput.trim();
    if (!tag) return;
    if (planTags.includes(tag)) {
      setPlanTagInput("");
      return;
    }
    setPlanTags((current) => [...current, tag]);
    setPlanTagInput("");
    markDirty();
  }

  function removePlanTag(tag: string) {
    if (writePlan.isPending) return;
    setPlanTags((current) => current.filter((item) => item !== tag));
    markDirty();
  }

  function toggleCase(testCase: TestCase) {
    if (writePlan.isPending) return;
    if (
      !selectedIds.has(testCase.id)
      && selectedCases.length >= 100
    ) {
      setValidationError("测试计划最多绑定 100 个用例");
      return;
    }
    markDirty();
    if (selectedIds.has(testCase.id)) {
      setSelectedCases((current) =>
        current.filter((item) => item.id !== testCase.id)
      );
      return;
    }
    setSelectedCases((current) => [...current, testCase]);
  }

  function moveCase(caseId: string, direction: "top" | "up" | "down") {
    if (writePlan.isPending) return;
    setSelectedCases((current) => {
      const index = current.findIndex((item) => item.id === caseId);
      if (index < 0) return current;
      const target = direction === "top"
        ? 0
        : direction === "up"
          ? Math.max(0, index - 1)
          : Math.min(current.length - 1, index + 1);
      if (target === index) return current;
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(target, 0, item);
      return next;
    });
    markDirty();
    if (direction === "top") setSelectedPage(1);
  }

  function removeCase(caseId: string) {
    if (writePlan.isPending) return;
    setSelectedCases((current) =>
      current.filter((item) => item.id !== caseId)
    );
    markDirty();
  }

  function save() {
    if (writePlan.isPending) return;
    setValidationError("");
    setSaveError("");
    if (!name.trim()) {
      setValidationError("请输入测试计划名称");
      nameRef.current?.focus();
      return;
    }
    if (selectedCases.length === 0) {
      setValidationError("请至少选择 1 个测试用例");
      return;
    }
    writePlan.mutate({
      name: name.trim(),
      description: description.trim() || null,
      test_type: testType,
      tags: planTags,
      case_ids: selectedCases.map((item) => item.id),
    });
  }

  if (!isNew && (plan.isLoading || boundCases.isLoading)) {
    return (
      <div className="page-container test-plan-editor-page">
        <div
          className="test-plan-editor-skeleton"
          role="status"
          aria-label="正在加载测试计划"
          aria-live="polite"
          aria-busy="true"
        />
      </div>
    );
  }

  if (!isNew && (plan.isError || boundCases.isError)) {
    return (
      <div className="page-container test-plan-editor-page">
        <div className="empty-state error" role="alert">
          <p>测试计划加载失败，请重新加载。</p>
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              void plan.refetch();
              void boundCases.refetch();
            }}
          >
            重新加载
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container test-plan-editor-page">
      <PageHeader
        breadcrumbs={[
          { label: "首页", to: "/tasks" },
          { label: "测试计划", to: "/test-plans" },
          { label: isNew ? "新建" : "编辑" },
        ]}
        title={isNew ? "新建测试计划" : "编辑测试计划"}
        description="计划只保存稳定的用例顺序，设备与执行配置在运行时选择"
      />

      <fieldset
        className="test-plan-editor-stack"
        disabled={writePlan.isPending}
      >
        {(saveError || (
          validationError
          && validationError !== "请输入测试计划名称"
        )) && (
          <div className="error-banner" role="alert">
            {saveError || validationError}
          </div>
        )}
        {(tags.isError || modules.isError) && (
          <div className="error-banner" role="alert">
            <span>筛选数据加载失败，标签或模块暂不可用。</span>
            <button
              type="button"
              className="secondary-button"
              aria-label="重新加载筛选数据"
              onClick={() => {
                void tags.refetch();
                void modules.refetch();
              }}
            >
              重新加载
            </button>
          </div>
        )}

        <section className="plan-editor-section">
          <div className="plan-editor-section-heading">
            <div>
              <span className="section-kicker">基本信息</span>
              <h2>定义计划范围</h2>
            </div>
          </div>
          <div className="plan-basic-grid">
            <label className="plan-field">
              <span>测试计划名称 <b>*</b></span>
              <input
                ref={nameRef}
                name="test_plan_name"
                autoComplete="off"
                aria-label="测试计划名称"
                maxLength={100}
                value={name}
                onChange={(event) => {
                  if (writePlan.isPending) return;
                  setName(event.target.value);
                  markDirty();
                }}
              />
              {validationError === "请输入测试计划名称" && (
                <small className="form-error">{validationError}</small>
              )}
            </label>
            <div className="plan-field">
              <span>测试类型</span>
              <SingleSelect
                label="测试类型"
                value={testType}
                options={TEST_TYPE_OPTIONS}
                onChange={(value) => {
                  if (writePlan.isPending) return;
                  setTestType(value);
                  markDirty();
                }}
              />
            </div>
            <div className="plan-field">
              <span>计划标签</span>
              <div className="tag-input-area plan-tag-input-area">
                <div className="tag-list editable">
                  {planTags.map((tag) => (
                    <span key={tag} className="tag tag-primary tag-removable">
                      {tag}
                      <button
                        type="button"
                        aria-label={`移除计划标签 ${tag}`}
                        onClick={() => removePlanTag(tag)}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <input
                    type="text"
                    className="tag-text-input"
                    aria-label="计划标签输入"
                    placeholder={planTags.length === 0
                      ? "输入标签后按回车添加"
                      : ""}
                    value={planTagInput}
                    onChange={(event) => {
                      if (!writePlan.isPending) {
                        setPlanTagInput(event.target.value);
                      }
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === ",") {
                        event.preventDefault();
                        addPlanTag();
                      }
                      if (
                        event.key === "Backspace"
                        && !planTagInput
                        && planTags.length > 0
                      ) {
                        event.preventDefault();
                        const last = planTags.at(-1);
                        if (last) removePlanTag(last);
                      }
                    }}
                    onBlur={addPlanTag}
                  />
                </div>
              </div>
            </div>
            <label className="plan-field plan-field-wide">
              <span>计划描述</span>
              <textarea
                name="test_plan_description"
                aria-label="计划描述"
                maxLength={2000}
                rows={3}
                value={description}
                onChange={(event) => {
                  if (writePlan.isPending) return;
                  setDescription(event.target.value);
                  markDirty();
                }}
              />
            </label>
          </div>
        </section>

        <section className="plan-editor-section">
          <div className="plan-editor-section-heading">
            <div>
              <span className="section-kicker">候选用例</span>
              <h2>从用例库选择</h2>
            </div>
            <span className="section-count">
              已选 {selectedCases.length} / 100
            </span>
          </div>
          <div className="plan-case-toolbar">
            <label className="plan-case-search">
              <span className="sr-only">搜索候选用例</span>
              <SearchIcon />
              <input
                type="search"
                name="candidate_case_search"
                autoComplete="off"
                aria-label="搜索候选用例"
                placeholder="搜索名称、ID 或模块…"
                value={candidateSearchInput}
                onChange={(event) => {
                  if (!writePlan.isPending) {
                    setCandidateSearchInput(event.target.value);
                  }
                }}
              />
            </label>
            <SingleSelect
              label="候选模块"
              value={candidateModule}
              options={moduleOptions}
              onChange={(value) => {
                if (writePlan.isPending) return;
                setCandidateModule(value);
                setCandidatePage(1);
              }}
            />
            <MultiSelect
              label="候选标签"
              values={candidateTags}
              options={candidateTagOptions}
              onChange={(values) => {
                if (writePlan.isPending) return;
                setCandidateTags(values);
                setCandidatePage(1);
              }}
              searchValue={candidateTagSearch}
              onSearchChange={(value) => {
                if (!writePlan.isPending) setCandidateTagSearch(value);
              }}
            />
          </div>
          <CaseTable
            mode="candidate"
            items={candidates.data?.items ?? []}
            selectedIds={selectedIds}
            selectionAtLimit={selectedCases.length >= 100}
            colors={registryByName}
            loading={candidates.isLoading}
            error={candidates.isError}
            onToggle={toggleCase}
            onRetry={() => void candidates.refetch()}
          />
          <PaginationControls
            page={candidatePage}
            pageSize={candidatePageSize}
            total={candidates.data?.total ?? 0}
            onPageChange={(value) => {
              if (!writePlan.isPending) setCandidatePage(value);
            }}
            onPageSizeChange={(value) => {
              if (writePlan.isPending) return;
              setCandidatePageSize(value);
              setCandidatePage(1);
            }}
          />
        </section>

        <section className="plan-editor-section selected-case-section">
          <div className="plan-editor-section-heading">
            <div>
              <span className="section-kicker">执行顺序</span>
              <h2>已选用例（{selectedCases.length}）</h2>
            </div>
            <span className="section-hint">顺序将直接用于计划执行</span>
          </div>
          {selectedPageItems.length === 0 ? (
            <div className="plan-case-empty">尚未选择用例</div>
          ) : (
            <div className="table-scroll">
              <table className="data-table plan-case-table selected-case-table">
                <thead>
                  <tr>
                    <th>序号</th>
                    <th>用例名称</th>
                    <th>用例 ID</th>
                    <th>模块</th>
                    <th>标签</th>
                    <th>排序操作</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedPageItems.map((testCase, pageIndex) => {
                    const globalIndex = selectedStart + pageIndex;
                    return (
                      <tr key={testCase.id}>
                        <td className="case-position">{globalIndex + 1}</td>
                        <td>{testCase.title}</td>
                        <td className="monospace" translate="no">
                          {testCase.id}
                        </td>
                        <td>{testCase.module ?? "-"}</td>
                        <td>
                          <CaseTags
                            tags={testCase.tags}
                            colors={registryByName}
                          />
                        </td>
                        <td>
                          <div className="selected-case-actions">
                            <button
                              type="button"
                              aria-label={`置顶 ${testCase.id}`}
                              disabled={globalIndex === 0}
                              onClick={() => moveCase(testCase.id, "top")}
                            >
                              置顶
                            </button>
                            <button
                              type="button"
                              aria-label={`上移 ${testCase.id}`}
                              disabled={globalIndex === 0}
                              onClick={() => moveCase(testCase.id, "up")}
                            >
                              上移
                            </button>
                            <button
                              type="button"
                              aria-label={`下移 ${testCase.id}`}
                              disabled={globalIndex === selectedCases.length - 1}
                              onClick={() => moveCase(testCase.id, "down")}
                            >
                              下移
                            </button>
                            <button
                              type="button"
                              className="danger"
                              aria-label={`移除 ${testCase.id}`}
                              onClick={() => removeCase(testCase.id)}
                            >
                              移除
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
          <PaginationControls
            page={selectedPage}
            pageSize={selectedPageSize}
            total={selectedCases.length}
            onPageChange={(value) => {
              if (!writePlan.isPending) setSelectedPage(value);
            }}
            onPageSizeChange={(value) => {
              if (writePlan.isPending) return;
              setSelectedPageSize(value);
              setSelectedPage(1);
            }}
          />
        </section>

        <div className="plan-editor-savebar">
          <span>
            {dirty ? "有未保存的更改" : "当前内容已同步"}
          </span>
          <div>
            <Link
              to="/test-plans"
              className="secondary-button"
              aria-disabled={writePlan.isPending}
              tabIndex={writePlan.isPending ? -1 : undefined}
              onClick={(event) => {
                if (writePlan.isPending) event.preventDefault();
              }}
            >
              取消
            </Link>
            <button
              type="button"
              className="primary-button"
              aria-label="保存测试计划"
              disabled={writePlan.isPending}
              onClick={save}
            >
              {writePlan.isPending ? "保存中…" : "保存测试计划"}
            </button>
          </div>
        </div>
      </fieldset>
      <ConfirmDialog
        open={blocker.state === "blocked" && !writePlan.isPending}
        title="离开编辑页面"
        description="当前更改尚未保存，离开后将丢失这些更改。"
        confirmLabel="确认离开"
        pendingLabel="正在离开…"
        onClose={() => {
          if (blocker.state === "blocked") {
            blocker.reset();
          }
        }}
        onConfirm={() => {
          if (blocker.state === "blocked") {
            setDirty(false);
            blocker.proceed();
          }
        }}
      />
    </div>
  );
}

function CaseTags({
  tags,
  colors,
}: {
  tags: string[];
  colors: Map<string, TagOption>;
}) {
  if (tags.length === 0) return <span className="case-empty-value">-</span>;
  return (
    <div className="test-plan-tags">
      {tags.slice(0, 3).map((tag) => (
        <span
          key={tag}
          className="registered-tag"
          style={caseTagStyle(tag, colors)}
        >
          {tag}
        </span>
      ))}
      {tags.length > 3 && <span className="tag-more">+{tags.length - 3}</span>}
    </div>
  );
}

function CaseTable({
  mode,
  items,
  selectedIds,
  selectionAtLimit,
  colors,
  loading,
  error,
  onToggle,
  onRetry,
}: {
  mode: "candidate";
  items: TestCase[];
  selectedIds: Set<string>;
  selectionAtLimit: boolean;
  colors: Map<string, TagOption>;
  loading: boolean;
  error: boolean;
  onToggle: (testCase: TestCase) => void;
  onRetry: () => void;
}) {
  if (loading) {
    return (
      <div
        className="plan-case-loading"
        role="status"
        aria-label="正在加载候选用例"
        aria-live="polite"
        aria-busy="true"
      >
        正在加载候选用例…
      </div>
    );
  }
  if (error) {
    return (
      <div className="plan-case-empty error" role="alert">
        <span>候选用例加载失败，请调整筛选或稍后重试。</span>
        <button
          type="button"
          className="secondary-button"
          aria-label="重新加载候选用例"
          onClick={onRetry}
        >
          重新加载
        </button>
      </div>
    );
  }
  if (items.length === 0) {
    return <div className="plan-case-empty">暂无匹配用例</div>;
  }
  return (
    <div className="table-scroll">
      <table className="data-table plan-case-table">
        <thead>
          <tr>
            <th>选择</th>
            <th>用例名称</th>
            <th>用例 ID</th>
            <th>模块</th>
            <th>标签</th>
            <th>最近执行</th>
          </tr>
        </thead>
        <tbody>
          {items.map((testCase) => (
            <tr key={`${mode}-${testCase.id}`}>
              <td>
                <label className="plan-case-checkbox">
                  <input
                    type="checkbox"
                    aria-label={`选择 ${testCase.title}`}
                    checked={selectedIds.has(testCase.id)}
                    disabled={
                      selectionAtLimit && !selectedIds.has(testCase.id)
                    }
                    onChange={() => onToggle(testCase)}
                  />
                  <span />
                </label>
              </td>
              <td>{testCase.title}</td>
              <td className="monospace" translate="no">
                {testCase.id}
              </td>
              <td>{testCase.module ?? "-"}</td>
              <td>
                <CaseTags tags={testCase.tags} colors={colors} />
              </td>
              <td>{formatChinaDateTime(testCase.last_executed_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
