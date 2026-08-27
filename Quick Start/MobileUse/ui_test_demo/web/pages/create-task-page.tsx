import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { ApiError, api } from "../api/client";
import { useBusinessNavigate } from "../business-context";
import type {
  PodPoolResponse,
  Task,
  TaskBatch,
  TaskBatchCreateRequest,
  TestCase,
  TestCaseListResponse,
} from "../api/types";
import {
  ExecuteDialog,
  type ExecuteConfig,
} from "../components/execute-dialog";
import { BusinessLink as Link } from "../components/business-link";
import { PageHeader } from "../components/page-header";

type WizardStep = "type" | "scope" | "device" | "review";
type TestType = "new_feature" | "regression";
type SelectionMode = "single" | "multi_cases" | "tags";
type DeviceStrategy = "automatic" | "specified";

const STEPS: Array<{ key: WizardStep; label: string; hint: string }> = [
  { key: "type", label: "测试类型", hint: "确定执行目标" },
  { key: "scope", label: "用例范围", hint: "选择执行内容" },
  { key: "device", label: "设备策略", hint: "配置并发资源" },
  { key: "review", label: "确认提交", hint: "核对执行计划" },
];

function generateIdempotencyKey(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export function CreateTaskPage() {
  const navigate = useBusinessNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedStep = searchParams.get("step") as WizardStep | null;
  const step = STEPS.some((item) => item.key === requestedStep)
    ? requestedStep as WizardStep
    : "type";
  const preselectedId = searchParams.get("case_id") ?? "";

  const [testType, setTestType] = useState<TestType>("new_feature");
  const [selectionMode, setSelectionMode] = useState<SelectionMode>(
    preselectedId ? "single" : "multi_cases",
  );
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>(
    preselectedId ? [preselectedId] : [],
  );
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [caseSearch, setCaseSearch] = useState("");
  const [deviceStrategy, setDeviceStrategy] = useState<DeviceStrategy>("automatic");
  const [concurrency, setConcurrency] = useState(1);
  const [selectedPodIds, setSelectedPodIds] = useState<string[]>([]);
  const [executeDialogOpen, setExecuteDialogOpen] = useState(false);
  const [createdBatchId, setCreatedBatchId] = useState("");
  const [validationError, setValidationError] = useState("");

  const casesQuery = useQuery({
    queryKey: ["cases", "all-for-task-wizard"],
    queryFn: () => api.get<TestCaseListResponse>("/cases?page=1&page_size=100"),
  });
  const podsQuery = useQuery({
    queryKey: ["pod-pool", "task-wizard"],
    queryFn: () => api.get<PodPoolResponse>("/pod-pool"),
    enabled: step === "device" || step === "review",
    refetchInterval: step === "device" ? 3000 : false,
  });

  const singleMutation = useMutation({
    mutationFn: ({
      caseId,
      config,
    }: {
      caseId: string;
      config: ExecuteConfig;
    }) => api.post<Task>(`/cases/${caseId}/execute`, {
      idempotency_key: generateIdempotencyKey("exec"),
      pod_id: deviceStrategy === "specified" ? selectedPodIds[0] : null,
      timeout_seconds: config.timeout_seconds,
      agent_config_mode: config.agent_config_mode,
      agent_options: config.agent_options,
    }),
    onSuccess: (task) => navigate(`/tasks/${task.id}`),
  });
  const batchMutation = useMutation({
    mutationFn: (payload: TaskBatchCreateRequest) =>
      api.post<TaskBatch>("/task-batches", payload),
    onSuccess: (batch) => {
      setExecuteDialogOpen(false);
      setCreatedBatchId(batch.id);
    },
  });

  const allCases = casesQuery.data?.items ?? [];
  const allTags = useMemo(
    () => Array.from(new Set(allCases.flatMap((item) => item.tags))).sort(),
    [allCases],
  );
  const tagMatchedCases = useMemo(
    () => allCases.filter((item) =>
      selectedTags.length > 0
      && item.tags.some((tag) => selectedTags.includes(tag))),
    [allCases, selectedTags],
  );
  const effectiveCaseIds = selectionMode === "tags"
    ? tagMatchedCases.map((item) => item.id)
    : selectedCaseIds;
  const selectedCases = effectiveCaseIds
    .map((caseId) => allCases.find((item) => item.id === caseId))
    .filter((item): item is TestCase => Boolean(item));
  const filteredCases = useMemo(() => {
    const query = caseSearch.trim().toLowerCase();
    if (!query) return allCases;
    return allCases.filter((item) =>
      item.title.toLowerCase().includes(query)
      || item.id.toLowerCase().includes(query)
      || item.module?.toLowerCase().includes(query)
      || item.tags.some((tag) => tag.toLowerCase().includes(query)));
  }, [allCases, caseSearch]);
  const pods = podsQuery.data?.items ?? [];
  const pending = singleMutation.isPending || batchMutation.isPending;
  const mutationError = singleMutation.error ?? batchMutation.error;
  const errorMessage = mutationError instanceof ApiError
    ? mutationError.message
    : mutationError
      ? "创建任务失败，请检查配置后重试。"
      : "";

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (!createdBatchId && (selectedCaseIds.length > 0 || selectedTags.length > 0)) {
        event.preventDefault();
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [createdBatchId, selectedCaseIds.length, selectedTags.length]);

  useEffect(() => {
    const maxConcurrency = Math.max(1, effectiveCaseIds.length);
    setConcurrency((current) => Math.min(current, maxConcurrency));
    setSelectedPodIds((current) => current.slice(0, maxConcurrency));
  }, [effectiveCaseIds.length]);

  function goTo(next: WizardStep) {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("step", next);
    setSearchParams(nextParams, { replace: true });
    setValidationError("");
  }

  function toggleCase(caseId: string) {
    setSelectedCaseIds((current) => {
      if (selectionMode === "single") return [caseId];
      return current.includes(caseId)
        ? current.filter((item) => item !== caseId)
        : [...current, caseId];
    });
  }

  function nextFromScope() {
    const minimum = selectionMode === "multi_cases" ? 2 : 1;
    if (effectiveCaseIds.length < minimum) {
      setValidationError(
        selectionMode === "multi_cases"
          ? "多用例模式至少选择 2 个用例。"
          : "请至少选择 1 个用例。",
      );
      return;
    }
    setConcurrency(Math.min(Math.max(1, concurrency), effectiveCaseIds.length));
    goTo("device");
  }

  function nextFromDevice() {
    if (deviceStrategy === "specified" && selectedPodIds.length === 0) {
      setValidationError("指定设备模式至少选择 1 台设备。");
      return;
    }
    if (selectedPodIds.length > concurrency) {
      setValidationError("指定设备数量不能大于批次设备并发数。");
      return;
    }
    goTo("review");
  }

  function submit(config: ExecuteConfig) {
    if (selectionMode === "single") {
      singleMutation.mutate({ caseId: effectiveCaseIds[0], config });
      return;
    }
    const mode = selectionMode === "tags" ? "tags" : "multi_cases";
    batchMutation.mutate({
      name: `${testType === "regression" ? "回归测试" : "新功能测试"} · ${effectiveCaseIds.length} 个用例`,
      test_type: testType,
      selection_mode: mode,
      case_ids: effectiveCaseIds,
      selection_snapshot: mode === "tags"
        ? { tags: selectedTags, case_ids: effectiveCaseIds }
        : { case_ids: effectiveCaseIds },
      device_strategy: deviceStrategy,
      pod_ids: deviceStrategy === "specified" ? selectedPodIds : [],
      concurrency: Math.min(concurrency, effectiveCaseIds.length),
      device_wait_timeout_seconds: config.device_wait_timeout_seconds,
      timeout_seconds: config.timeout_seconds,
      agent_config_mode: config.agent_config_mode,
      agent_options: config.agent_options,
      idempotency_key: generateIdempotencyKey("batch"),
    });
  }

  if (createdBatchId) {
    return (
      <section className="wizard-success" aria-live="polite">
        <span className="wizard-success-mark" aria-hidden="true">✓</span>
        <p className="eyebrow">批次已进入调度队列</p>
        <h1>任务创建成功</h1>
        <code translate="no">{createdBatchId}</code>
        <p>子任务将按照设备可用性和设备并发上限自动调度。</p>
        <Link className="primary-button" to="/tasks">
          查看执行记录
        </Link>
      </section>
    );
  }

  return (
    <div className="create-task-page wizard-page">
      <PageHeader
        className="wizard-header"
        breadcrumbs={[{ label: "首页", to: "/tasks" }, { label: "新建任务" }]}
        title="新建测试任务"
        description="按步骤配置执行范围，系统将创建独立任务或批次子任务。"
      />

      <nav className="task-wizard-stepper" aria-label="创建任务步骤">
        <ol>
          {STEPS.map((item, index) => {
            const currentIndex = STEPS.findIndex((candidate) => candidate.key === step);
            const active = item.key === step;
            const completed = index < currentIndex;
            return (
              <li key={item.key} className={active ? "active" : completed ? "completed" : ""}>
                <button
                  type="button"
                  aria-current={active ? "step" : undefined}
                  onClick={() => {
                    if (completed) goTo(item.key);
                  }}
                  disabled={!completed && !active}
                >
                  <span className="step-index">{completed ? "✓" : index + 1}</span>
                  <span className="step-copy">
                    <strong>{item.label}</strong>
                    <small>{item.hint}</small>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <section className="wizard-card" aria-label="任务创建表单">
        {step === "type" && (
          <section aria-labelledby="wizard-type-title">
            <WizardSectionHeading
              id="wizard-type-title"
              eyebrow="执行意图"
              title="这次要验证什么？"
              description="测试类型会写入批次元数据，不会修改用例内容。"
            />
            <div className="wizard-choice-grid">
              <ChoiceCard
                name="test-type"
                value="new_feature"
                checked={testType === "new_feature"}
                onChange={() => setTestType("new_feature")}
                title="新功能测试"
                description="验证新上线、刚变更或正在开发的能力。"
                accent="01"
              />
              <ChoiceCard
                name="test-type"
                value="regression"
                checked={testType === "regression"}
                onChange={() => setTestType("regression")}
                title="回归测试"
                description="复验核心链路，确认已有能力保持稳定。"
                accent="02"
              />
            </div>
          </section>
        )}

        {step === "scope" && (
          <section aria-labelledby="wizard-scope-title">
            <WizardSectionHeading
              id="wizard-scope-title"
              eyebrow="执行范围"
              title="选择需要执行的用例"
              description="多用例按选择顺序创建子任务；标签模式会在提交时固化匹配结果。"
            />
            <fieldset className="wizard-segmented">
              <legend className="sr-only">用例选择方式</legend>
              {[
                ["single", "单用例"],
                ["multi_cases", "多用例"],
                ["tags", "按标签"],
              ].map(([value, label]) => (
                <label key={value}>
                  <input
                    type="radio"
                    name="selection-mode"
                    value={value}
                    checked={selectionMode === value}
                    onChange={() => {
                      setSelectionMode(value as SelectionMode);
                      setSelectedCaseIds([]);
                      setSelectedTags([]);
                    }}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </fieldset>

            {selectionMode === "tags" ? (
              <div className="tag-scope-panel">
                <div className="tag-picker" aria-label="标签筛选">
                  {allTags.map((tag) => (
                    <label key={tag}>
                      <input
                        type="checkbox"
                        name={`tag-${tag}`}
                        checked={selectedTags.includes(tag)}
                        onChange={() => setSelectedTags((current) =>
                          current.includes(tag)
                            ? current.filter((item) => item !== tag)
                            : [...current, tag])}
                      />
                      <span>{tag}</span>
                    </label>
                  ))}
                </div>
                <p className="wizard-count" aria-live="polite">
                  匹配 {tagMatchedCases.length} 个用例
                </p>
              </div>
            ) : (
              <>
                <div className="case-search-box wizard-search">
                  <span aria-hidden="true">⌕</span>
                  <input
                    type="search"
                    name="case_search"
                    autoComplete="off"
                    aria-label="搜索用例"
                    placeholder="搜索用例名称、ID、模块或标签…"
                    value={caseSearch}
                    onChange={(event) => setCaseSearch(event.target.value)}
                  />
                </div>
                <div className="wizard-case-list">
                  {casesQuery.isLoading && <p className="muted">正在加载用例…</p>}
                  {casesQuery.isError && <p className="form-error">用例加载失败，请刷新后重试。</p>}
                  {filteredCases.map((item) => (
                    <label
                      key={item.id}
                      className={selectedCaseIds.includes(item.id) ? "selected" : ""}
                    >
                      <input
                        type={selectionMode === "single" ? "radio" : "checkbox"}
                        name={selectionMode === "single" ? "selected-case" : `case-${item.id}`}
                        checked={selectedCaseIds.includes(item.id)}
                        onChange={() => toggleCase(item.id)}
                        aria-label={`${item.title} ${item.id}`}
                      />
                      <span className="case-main">
                        <strong>{item.title}</strong>
                        <code title={item.id} translate="no">{item.id}</code>
                      </span>
                      <span className="case-context">
                        {item.module ?? "未分组"}
                        {item.tags.slice(0, 2).map((tag) => (
                          <em key={tag}>{tag}</em>
                        ))}
                      </span>
                    </label>
                  ))}
                </div>
                <p className="wizard-count" aria-live="polite">
                  已选择 {selectedCaseIds.length} 个用例
                </p>
              </>
            )}
          </section>
        )}

        {step === "device" && (
          <section aria-labelledby="wizard-device-title">
            <WizardSectionHeading
              id="wizard-device-title"
              eyebrow="调度策略"
              title="如何分配执行设备？"
              description="设备繁忙时保持排队；指定设备不会自动切换到未选择的设备。"
            />
            <div className="wizard-choice-grid compact">
              <ChoiceCard
                name="device-strategy"
                value="automatic"
                checked={deviceStrategy === "automatic"}
                onChange={() => {
                  setDeviceStrategy("automatic");
                  setSelectedPodIds([]);
                }}
                title="自动分配"
                description="从当前设备池中动态选择空闲云机。"
                accent="A"
              />
              <ChoiceCard
                name="device-strategy"
                value="specified"
                checked={deviceStrategy === "specified"}
                onChange={() => setDeviceStrategy("specified")}
                title="指定设备"
                description="仅在选中的设备白名单内持续调度。"
                accent="B"
              />
            </div>
            <div className="concurrency-control">
              <label htmlFor="batch-concurrency">批次设备并发数</label>
              <input
                id="batch-concurrency"
                name="batch_concurrency"
                autoComplete="off"
                inputMode="numeric"
                type="number"
                min={1}
                max={Math.max(1, effectiveCaseIds.length)}
                value={concurrency}
                onChange={(event) => {
                  const next = Math.max(
                    1,
                    Math.min(effectiveCaseIds.length, Number(event.target.value) || 1),
                  );
                  setConcurrency(next);
                  setSelectedPodIds((current) => current.slice(0, next));
                }}
              />
              <p>
                实际并发不超过 {effectiveCaseIds.length} 个用例和当前可租用设备数。
              </p>
            </div>
            {deviceStrategy === "specified" && (
              <div className="wizard-pod-list">
                {podsQuery.isLoading && <p className="muted">正在加载设备池…</p>}
                {podsQuery.isError && <p className="form-error">设备池加载失败，请重试。</p>}
                {pods.map((pod) => {
                  const selected = selectedPodIds.includes(pod.pod_id);
                  const selectable = pod.local_state === "available" || selected;
                  return (
                    <label key={pod.pod_id} className={selected ? "selected" : ""}>
                      <input
                        type="checkbox"
                        name={`pod-${pod.pod_id}`}
                        checked={selected}
                        disabled={!selectable}
                        aria-label={`${pod.pod_name} ${pod.pod_id}`}
                        onChange={() => setSelectedPodIds((current) => {
                          if (current.includes(pod.pod_id)) {
                            return current.filter((item) => item !== pod.pod_id);
                          }
                          if (current.length >= concurrency) return current;
                          return [...current, pod.pod_id];
                        })}
                      />
                      <span>
                        <strong>{pod.pod_name}</strong>
                        <code translate="no">{pod.pod_id}</code>
                      </span>
                      <em>{pod.local_state === "available" ? "可用" : pod.local_state}</em>
                    </label>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {step === "review" && (
          <section aria-labelledby="wizard-review-title">
            <WizardSectionHeading
              id="wizard-review-title"
              eyebrow="执行计划"
              title="确认后进入调度队列"
              description="系统会创建独立子任务，状态和结果分别记录。"
            />
            <dl className="wizard-review-grid">
              <ReviewItem label="测试类型" value={testType === "regression" ? "回归测试" : "新功能测试"} />
              <ReviewItem label="用例范围" value={`${effectiveCaseIds.length} 个用例`} />
              <ReviewItem label="选择方式" value={
                selectionMode === "tags" ? "按标签" : selectionMode === "single" ? "单用例" : "多用例"
              } />
              <ReviewItem label="设备策略" value={deviceStrategy === "specified" ? "指定设备" : "自动分配"} />
              <ReviewItem label="设备并发上限" value={`${concurrency}`} />
              <ReviewItem label="指定设备" value={
                deviceStrategy === "specified" ? `${selectedPodIds.length} 台` : "动态设备池"
              } />
            </dl>
            <div className="review-case-strip">
              {selectedCases.map((item, index) => (
                <div key={item.id}>
                  <span>{index + 1}</span>
                  <strong>{item.title}</strong>
                  <code translate="no">{item.id}</code>
                </div>
              ))}
            </div>
          </section>
        )}

        {validationError && (
          <p className="wizard-error" role="alert">{validationError}</p>
        )}
        <div className="wizard-actions">
          <div>
            {step !== "type" && (
              <button
                type="button"
                className="secondary-button"
                onClick={() => goTo(STEPS[Math.max(0, STEPS.findIndex((item) => item.key === step) - 1)].key)}
              >
                上一步
              </button>
            )}
          </div>
          <div>
            <Link className="ghost-button" to="/tasks">取消</Link>
            {step === "type" && (
              <button type="button" className="primary-button" onClick={() => goTo("scope")}>
                下一步：选择用例
              </button>
            )}
            {step === "scope" && (
              <button type="button" className="primary-button" onClick={nextFromScope}>
                下一步：设备策略
              </button>
            )}
            {step === "device" && (
              <button type="button" className="primary-button" onClick={nextFromDevice}>
                下一步：确认提交
              </button>
            )}
            {step === "review" && (
              <button
                type="button"
                className="primary-button"
                onClick={() => setExecuteDialogOpen(true)}
              >
                打开执行配置
              </button>
            )}
          </div>
        </div>
      </section>

      <ExecuteDialog
        open={executeDialogOpen}
        caseTitle={`${effectiveCaseIds.length} 个用例 · ${deviceStrategy === "specified" ? "指定设备" : "自动分配"}`}
        showDeviceSelection={false}
        showDeviceWaitTimeout={selectionMode !== "single"}
        onClose={() => {
          if (!pending) setExecuteDialogOpen(false);
        }}
        onConfirm={submit}
        isPending={pending}
        errorMessage={errorMessage}
      />
    </div>
  );
}

function WizardSectionHeading({
  id,
  eyebrow,
  title,
  description,
}: {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <header className="wizard-section-heading">
      <p>{eyebrow}</p>
      <h2 id={id}>{title}</h2>
      <span>{description}</span>
    </header>
  );
}

function ChoiceCard({
  name,
  value,
  checked,
  onChange,
  title,
  description,
  accent,
}: {
  name: string;
  value: string;
  checked: boolean;
  onChange: () => void;
  title: string;
  description: string;
  accent: string;
}) {
  return (
    <label className={`wizard-choice-card${checked ? " selected" : ""}`}>
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={onChange}
      />
      <span className="choice-accent" aria-hidden="true">{accent}</span>
      <span>
        <strong>{title}</strong>
        <small>{description}</small>
      </span>
      <i aria-hidden="true" />
    </label>
  );
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
