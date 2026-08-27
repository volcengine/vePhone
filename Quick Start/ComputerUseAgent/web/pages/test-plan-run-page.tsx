import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  useBlocker,
  useParams,
} from "react-router";

import { ApiError, api } from "../api/client";
import { useBusinessNavigate } from "../business-context";
import type {
  PlanExecutionCreate,
  PlanExecutionResponse,
  PodPoolResponse,
  TestCaseListResponse,
  TestPlan,
} from "../api/types";
import {
  buildExecuteConfig,
  createExecutionConfigDraft,
  DeviceWaitTimeoutField,
  ExecutionConfigFields,
  type ExecutionConfigDraft,
} from "../components/execution-config-form";
import { BusinessLink as Link } from "../components/business-link";
import { PageHeader } from "../components/page-header";
import { PaginationControls } from "../components/pagination-controls";

type PageSize = 10 | 20 | 50;
type DeviceStrategy = "automatic" | "specified";

const MAX_PLAN_CONCURRENCY = 20;
const NO_ONLINE_CUA_NODE_MESSAGE = "当前没有可用的已在线 CUA 节点，请检查设备池状态或稍后重试。";
function createIdempotencyKey() {
  return `plan-run_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function friendlyRunError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "运行计划失败，请稍后重试。";
  }
  if (error.code === "runner_execution_settings_incomplete") {
    return `${error.message}，请先完善全局执行配置。`;
  }
  if (error.code === "idempotency_conflict") {
    return "本次运行配置已变化，请重新确认后提交。";
  }
  if (error.code === "concurrency_exceeds_case_count") {
    return "设备并发数不能超过计划用例数。";
  }
  return error.message || "运行计划失败，请稍后重试。";
}

function formatPodIdentity(
  pod: PodPoolResponse["items"][number],
): string {
  const podName = pod.pod_name?.trim();
  return podName && podName !== pod.pod_id
    ? `${podName} · ${pod.pod_id}`
    : pod.pod_id;
}

function formatPodSelectionLimitError(
  selectedCount: number,
  concurrency: number,
): string {
  return `已选择 ${selectedCount} 台设备，超过当前设备并发数 ${concurrency}。请减少设备数量，或提高设备并发数后再执行。`;
}

function automaticAssignablePods(pool: { items?: Array<{ discovery_state?: string; pod_status_code?: number; local_state?: string; task_id?: string | null }> } | undefined) {
  return (pool?.items ?? []).filter(
    (pod) =>
      pod.discovery_state === "active"
      && pod.pod_status_code === 2
      && pod.local_state === "available"
      && !pod.task_id,
  );
}

export function TestPlanRunPage() {
  const { planId = "" } = useParams<{ planId: string }>();
  const navigate = useBusinessNavigate();
  const queryClient = useQueryClient();
  const [deviceStrategy, setDeviceStrategy] =
    useState<DeviceStrategy>("automatic");
  const [concurrency, setConcurrency] = useState(1);
  const [selectedPodIds, setSelectedPodIds] = useState<string[]>([]);
  const [executionDraft, setExecutionDraft] =
    useState<ExecutionConfigDraft>(createExecutionConfigDraft);
  const [scopePage, setScopePage] = useState(1);
  const [scopePageSize, setScopePageSize] = useState<PageSize>(10);
  const [validationError, setValidationError] = useState("");
  const [selectionInvalidated, setSelectionInvalidated] = useState(false);
  const [podSearch, setPodSearch] = useState("");
  const [completedExecutionId, setCompletedExecutionId] = useState("");
  const keyRef = useRef<{ fingerprint: string; key: string } | null>(null);

  const plan = useQuery({
    queryKey: ["test-plan", planId],
    queryFn: () => api.get<TestPlan>(`/test-plans/${planId}`),
    enabled: Boolean(planId),
  });
  const planCases = useQuery({
    queryKey: ["test-plan", planId, "cases", "run"],
    queryFn: () =>
      api.get<TestCaseListResponse>(
        `/test-plans/${planId}/cases?page=1&page_size=100`,
      ),
    enabled: Boolean(planId),
  });
  const runPlan = useMutation({
    mutationFn: (payload: PlanExecutionCreate) =>
      api.post<PlanExecutionResponse>(
        `/test-plans/${planId}/executions`,
        payload,
      ),
    onSuccess: async (execution) => {
      keyRef.current = null;
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["test-plans"] }),
        queryClient.invalidateQueries({ queryKey: ["test-plan-stats"] }),
        queryClient.invalidateQueries({ queryKey: ["test-plan", planId] }),
        queryClient.invalidateQueries({ queryKey: ["task-reports"] }),
        queryClient.invalidateQueries({ queryKey: ["tasks"] }),
        queryClient.invalidateQueries({ queryKey: ["task-stats"] }),
        queryClient.invalidateQueries({ queryKey: ["pod-pool"] }),
      ]);
      setCompletedExecutionId(execution.id);
    },
  });
  const pods = useQuery({
    queryKey: ["pod-pool", "plan-run"],
    queryFn: () => api.post<PodPoolResponse>("/pod-pool/refresh"),
    enabled: deviceStrategy === "specified",
    refetchInterval: (
      deviceStrategy === "specified" && !runPlan.isPending
        ? 3000
        : false
    ),
  });

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      runPlan.isPending
      && currentLocation.pathname !== nextLocation.pathname,
  );
  useEffect(() => {
    if (blocker.state === "blocked") blocker.reset();
  }, [blocker]);
  useEffect(() => {
    if (!runPlan.isPending) return;
    function blockUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
    }
    window.addEventListener("beforeunload", blockUnload);
    return () => window.removeEventListener("beforeunload", blockUnload);
  }, [runPlan.isPending]);
  useEffect(() => {
    if (!completedExecutionId || runPlan.isPending) return;
    navigate(`/task-reports/${completedExecutionId}`);
  }, [completedExecutionId, navigate, runPlan.isPending]);

  useEffect(() => {
    if (!plan.data) return;
    const maxConcurrency = Math.max(
      1,
      Math.min(plan.data.case_count, MAX_PLAN_CONCURRENCY),
    );
    setConcurrency((current) =>
      Math.max(1, Math.min(current, maxConcurrency)));
    setSelectedPodIds((current) =>
      current.slice(0, maxConcurrency));
  }, [plan.data]);

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
    return selectablePods.filter((pod) => {
      const identity = `${pod.pod_name ?? ""} ${pod.pod_id} ${
        pod.local_state ?? ""
      }`.toLowerCase();
      return identity.includes(keyword);
    });
  }, [podSearch, selectablePods]);

  useEffect(() => {
    if (runPlan.isPending || !pods.isSuccess || !pods.data) return;
    const remaining = selectedPodIds.filter((podId) =>
      selectablePodIds.has(podId));
    if (remaining.length === selectedPodIds.length) return;
    setSelectedPodIds(remaining);
    setSelectionInvalidated(true);
    setValidationError("设备状态已更新，请重新选择可用设备。");
    runPlan.reset();
  }, [
    pods.data,
    pods.isSuccess,
    runPlan.isPending,
    runPlan.reset,
    selectablePodIds,
    selectedPodIds,
  ]);

  function changeConfiguration(change: () => void) {
    if (runPlan.isPending) return;
    change();
    setValidationError("");
    runPlan.reset();
  }

  function togglePod(podId: string) {
    if (runPlan.isPending || !selectablePodIds.has(podId)) return;
    const selected = selectedPodIds.includes(podId);
    if (!selected && selectedPodIds.length >= concurrency) {
      setValidationError(
        formatPodSelectionLimitError(selectedPodIds.length + 1, concurrency),
      );
      runPlan.reset();
      return;
    }
    setSelectedPodIds((current) =>
      current.includes(podId)
        ? current.filter((item) => item !== podId)
        : [...current, podId]);
    setValidationError("");
    setSelectionInvalidated(false);
    runPlan.reset();
  }

  function selectDeviceStrategy(strategy: DeviceStrategy) {
    changeConfiguration(() => {
      setDeviceStrategy(strategy);
      if (strategy === "automatic") {
        setSelectedPodIds([]);
        setPodSearch("");
      } else {
        setPodSearch("");
      }
      setSelectionInvalidated(false);
    });
  }

  async function submit() {
    if (runPlan.isPending || !plan.data) return;
    setValidationError("");
    const executionConfig = buildExecuteConfig(executionDraft);
    if (!executionConfig.config) {
      setValidationError(executionConfig.error);
      return;
    }
    if (
      deviceStrategy === "specified"
      && (!pods.isSuccess || !pods.data)
    ) {
      setValidationError("设备池刷新失败，请重新加载设备池后再提交。");
      return;
    }
    if (
      deviceStrategy === "specified"
      && (
        selectionInvalidated
        || selectedPodIds.some((podId) => !selectablePodIds.has(podId))
      )
    ) {
      setValidationError("设备状态已更新，请重新选择可用设备。");
      return;
    }
    if (
      deviceStrategy === "specified"
      && selectedPodIds.length === 0
    ) {
      setValidationError("指定设备模式至少选择 1 台设备。");
      return;
    }
    if (selectedPodIds.length > concurrency) {
      setValidationError(
        formatPodSelectionLimitError(selectedPodIds.length, concurrency),
      );
      return;
    }

    const maxEffectiveConcurrency = Math.min(
      concurrency,
      plan.data.case_count,
      MAX_PLAN_CONCURRENCY,
    );
    let effectiveConcurrency = maxEffectiveConcurrency;
    if (deviceStrategy === "automatic") {
      const refreshed = await pods.refetch();
      if (!refreshed.data) {
        setValidationError("设备池刷新失败，请重新加载设备池后再提交。");
        return;
      }
      const onlinePods = automaticAssignablePods(refreshed.data);
      if (onlinePods.length === 0) {
        setValidationError(NO_ONLINE_CUA_NODE_MESSAGE);
        return;
      }
      effectiveConcurrency = Math.min(maxEffectiveConcurrency, onlinePods.length);
      if (effectiveConcurrency < maxEffectiveConcurrency) {
        setValidationError(
          `当前仅 ${onlinePods.length} 台可用设备，本次将按 ${effectiveConcurrency} 并发执行。`,
        );
      }
    }

    const bodyWithoutKey = {
      test_type: plan.data.test_type,
      device_strategy: deviceStrategy,
      pod_ids: deviceStrategy === "specified" ? selectedPodIds : [],
      concurrency: effectiveConcurrency,
      device_wait_timeout_seconds: executionDraft.device_wait_timeout_seconds,
      timeout_seconds: executionConfig.config.timeout_seconds,
      agent_config_mode: executionConfig.config.agent_config_mode,
      agent_options: executionConfig.config.agent_options ?? null,
    };
    const fingerprint = JSON.stringify({
      ...bodyWithoutKey,
      requested_concurrency: concurrency,
    });
    if (keyRef.current?.fingerprint !== fingerprint) {
      keyRef.current = {
        fingerprint,
        key: createIdempotencyKey(),
      };
    }
    runPlan.mutate({
      ...bodyWithoutKey,
      idempotency_key: keyRef.current.key,
    });
  }

  if (plan.isLoading) {
    return (
      <div className="page-container test-plan-run-page">
        <div
          className="test-plan-detail-skeleton"
          role="status"
          aria-label="正在加载运行配置"
          aria-live="polite"
          aria-busy="true"
        />
      </div>
    );
  }

  if (plan.isError || !plan.data) {
    const notFound = plan.error instanceof ApiError
      && plan.error.code === "test_plan_not_found";
    return (
      <div className="page-container test-plan-run-page">
        <div className="empty-state error" role="alert">
          <strong>{notFound ? "测试计划不存在" : "运行配置加载失败"}</strong>
          <p>
            {notFound
              ? "该计划可能已被删除。"
              : "请检查网络状态后重试。"}
          </p>
          {notFound ? (
            <Link className="secondary-button" to="/test-plans">
              返回测试计划
            </Link>
          ) : (
            <button
              type="button"
              className="secondary-button"
              onClick={() => void plan.refetch()}
            >
              重新加载
            </button>
          )}
        </div>
      </div>
    );
  }

  const item = plan.data;
  const caseTitleById = new Map(
    (planCases.data?.items ?? []).map((testCase) => [
      testCase.id,
      testCase.title,
    ]),
  );
  const maxConcurrency = Math.max(
    1,
    Math.min(item.case_count, MAX_PLAN_CONCURRENCY),
  );
  const scopeStart = (scopePage - 1) * scopePageSize;
  const visibleCaseIds = item.case_ids.slice(
    scopeStart,
    scopeStart + scopePageSize,
  );

  return (
    <div className="page-container test-plan-run-page">
      <PageHeader
        breadcrumbs={[
          { label: "首页", to: "/tasks" },
          { label: "测试计划", to: "/test-plans" },
          { label: item.name, to: `/test-plans/${planId}` },
          { label: "运行" },
        ]}
        title="运行测试计划"
        description="本次设备、并发和执行配置将保存为不可变执行快照"
      />

      <fieldset
        className="plan-run-stack"
        disabled={runPlan.isPending}
      >
        <section className="plan-run-section plan-run-scope">
          <div className="plan-section-heading">
            <div>
              <span className="section-kicker">计划范围</span>
              <h2>{item.name}</h2>
            </div>
            <span className="section-count">{item.case_count} 个用例</span>
          </div>
          <p>{item.description ?? "未填写计划描述"}</p>
          <div className="plan-run-case-strip">
            {visibleCaseIds.map((caseId, index) => (
              <span key={caseId}>
                <b>{scopeStart + index + 1}</b>
                <span className="plan-run-case-copy">
                  <strong>{caseTitleById.get(caseId) ?? caseId}</strong>
                  <code translate="no">{caseId}</code>
                </span>
              </span>
            ))}
          </div>
          {item.case_count > scopePageSize && (
            <PaginationControls
              page={scopePage}
              pageSize={scopePageSize}
              total={item.case_count}
              onPageChange={setScopePage}
              onPageSizeChange={(value) => {
                setScopePageSize(value);
                setScopePage(1);
              }}
            />
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
            id="plan-run-device-wait-timeout-seconds"
            value={executionDraft.device_wait_timeout_seconds}
            onChange={(next) =>
              changeConfiguration(() =>
                setExecutionDraft({
                  ...executionDraft,
                  device_wait_timeout_seconds: next,
                }))}
            disabled={runPlan.isPending}
          />
        </section>

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
                  name="plan-device-strategy"
                  value="automatic"
                  checked={deviceStrategy === "automatic"}
                  onChange={() =>
                    selectDeviceStrategy("automatic")}
                />
                <strong>自动分配</strong>
                <span>从当前设备池中动态分配空闲设备</span>
              </label>
              <label className={deviceStrategy === "specified" ? "selected" : ""}>
                <input
                  type="radio"
                  aria-label="指定设备"
                  name="plan-device-strategy"
                  value="specified"
                  checked={deviceStrategy === "specified"}
                  onChange={() =>
                    selectDeviceStrategy("specified")}
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
                onChange={(event) =>
                  {
                    const next = Math.max(
                      1,
                      Math.min(
                        maxConcurrency,
                        Number(event.target.value) || 1,
                      ),
                    );
                    if (runPlan.isPending) return;
                    setConcurrency(next);
                    setValidationError(
                      selectedPodIds.length > next
                        ? formatPodSelectionLimitError(
                            selectedPodIds.length,
                            next,
                          )
                        : "",
                    );
                    runPlan.reset();
                  }}
              />
              <small>最大不超过 {maxConcurrency} 个并发任务</small>
            </label>
          </div>

          {deviceStrategy === "specified" && (
            <div className="plan-run-device-select">
              {pods.isLoading ? (
                <p
                  className="muted"
                  role="status"
                  aria-live="polite"
                  aria-busy="true"
                >
                  正在加载设备池…
                </p>
              ) : pods.isError ? (
                <div className="form-error" role="alert">
                  <span>设备池加载失败，请重新加载。</span>
                  <button
                    type="button"
                    className="secondary-button"
                    aria-label="重新加载设备池"
                    onClick={() => void pods.refetch()}
                  >
                    重新加载
                  </button>
                </div>
              ) : selectablePods.length === 0 ? (
                <div className="plan-case-empty">暂无可选设备</div>
              ) : (
                <div className="plan-run-field plan-run-pod-field">
                  <span id="plan-run-pod-list-label">设备选择</span>
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
                          disabled={runPlan.isPending}
                        />
                      </label>
                      <span className="plan-run-pod-quota">
                        {selectedPodIds.length} / {concurrency}
                      </span>
                    </div>
                    <div className="plan-run-device-panel-header">
                      <div>
                        <strong>可选设备</strong>
                        <span>在指定范围内按并发排队执行</span>
                      </div>
                    </div>
                    <div
                      className="plan-run-pod-list"
                      role="group"
                      aria-labelledby="plan-run-pod-list-label"
                    >
                      {visibleSelectablePods.length === 0 ? (
                        <div className="plan-run-pod-empty">
                          没有匹配的设备
                        </div>
                      ) : visibleSelectablePods.map((pod) => {
                        const selected = selectedPodIds.includes(pod.pod_id);
                        const disabled = (
                          runPlan.isPending
                          || (
                            !selected
                            && selectedPodIds.length >= concurrency
                          )
                        );
                        const statusText = pod.local_state === "available"
                          ? "可用"
                          : "繁忙 · 将排队";
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
                            <em className={
                              pod.local_state === "available"
                                ? "available"
                                : "busy"
                            }
                            >
                              {statusText}
                            </em>
                          </label>
                        );
                      })}
                    </div>
                    <div className="plan-run-selected-strip">
                      {selectedPodIds.length === 0 ? (
                        <span className="plan-run-selected-empty">
                          尚未选择设备
                        </span>
                      ) : selectedPodIds.map((podId) => (
                        <button
                          key={podId}
                          type="button"
                          className="plan-run-selected-chip"
                          onClick={() => togglePod(podId)}
                          disabled={runPlan.isPending}
                        >
                          <span>{podId}</span>
                          <span aria-hidden="true">×</span>
                        </button>
                      ))}
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
              <span className="section-kicker">执行配置</span>
              <h2>配置本次 Agent 运行参数</h2>
            </div>
          </div>
          <ExecutionConfigFields
            value={executionDraft}
            onChange={(next) =>
              changeConfiguration(() => setExecutionDraft(next))}
            disabled={runPlan.isPending}
            idPrefix="plan-run"
            allowCaseDefault
            customConfigLabel="自定义本次计划配置"
            caseDefaultLabel="按用例默认配置"
            showThreadId={false}
          />
        </section>
      </fieldset>

      {(validationError || runPlan.isError) && (
        <p className="wizard-error" role="alert">
          {validationError || friendlyRunError(runPlan.error)}
        </p>
      )}

      <div className="plan-run-actions">
        <Link
          to={`/test-plans/${planId}`}
          className="secondary-button"
          aria-disabled={runPlan.isPending}
          tabIndex={runPlan.isPending ? -1 : undefined}
          onClick={(event) => {
            if (runPlan.isPending) event.preventDefault();
          }}
        >
          取消
        </Link>
        <button
          type="button"
          className="primary-button"
          disabled={runPlan.isPending}
          onClick={submit}
        >
          {runPlan.isPending ? "正在创建执行…" : "确认并开始执行"}
        </button>
      </div>
    </div>
  );
}
