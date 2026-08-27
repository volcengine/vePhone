import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  useBlocker,
  useParams,
} from "react-router";

import { ApiError, api } from "../api/client";
import { useBusinessNavigate } from "../business-context";
import type {
  PlanExecutionCreate,
  PlanExecutionResponse,
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
import { DeviceStrategySelector, type DeviceStrategy } from "../components/device-strategy-selector";
import { PageHeader } from "../components/page-header";
import { PaginationControls } from "../components/pagination-controls";

type PageSize = 10 | 20 | 50;

const MAX_PLAN_CONCURRENCY = 20;
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

function formatPodSelectionLimitError(
  selectedCount: number,
  concurrency: number,
): string {
  return `已选择 ${selectedCount} 台设备，超过当前设备并发数 ${concurrency}。请减少设备数量，或提高设备并发数后再执行。`;
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
  const [completedExecutionId, setCompletedExecutionId] = useState("");
  const keyRef = useRef<{ fingerprint: string; key: string } | null>(null);
  const podStateRef = useRef<{
    isLoading: boolean;
    isError: boolean;
    isSuccess: boolean;
    selectablePodIds: Set<string>;
  }>({ isLoading: false, isError: false, isSuccess: false, selectablePodIds: new Set() });

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

  function changeConfiguration(change: () => void) {
    if (runPlan.isPending) return;
    change();
    setValidationError("");
    runPlan.reset();
  }

  function handleConcurrencyChange(next: number) {
    if (runPlan.isPending) return;
    const maxConc = Math.max(
      1,
      Math.min(plan.data?.case_count ?? MAX_PLAN_CONCURRENCY, MAX_PLAN_CONCURRENCY),
    );
    const clamped = Math.max(1, Math.min(maxConc, next));
    setConcurrency(clamped);
    if (selectedPodIds.length > clamped) {
      setValidationError(
        formatPodSelectionLimitError(selectedPodIds.length, clamped),
      );
    } else {
      setValidationError("");
    }
    runPlan.reset();
  }

  function handleSelectedPodIdsChange(next: string[]) {
    if (runPlan.isPending) return;
    setSelectedPodIds(next);
    setValidationError("");
    runPlan.reset();
  }

  function submit() {
    if (runPlan.isPending || !plan.data) return;
    setValidationError("");
    const executionConfig = buildExecuteConfig(executionDraft);
    if (!executionConfig.config) {
      setValidationError(executionConfig.error);
      return;
    }
    if (
      deviceStrategy === "specified"
      && (!podStateRef.current.isSuccess)
    ) {
      setValidationError("设备池刷新失败，请重新加载设备池后再提交。");
      return;
    }
    if (
      deviceStrategy === "specified"
      && selectedPodIds.some((podId) => !podStateRef.current.selectablePodIds.has(podId))
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

    const bodyWithoutKey = {
      test_type: plan.data.test_type,
      device_strategy: deviceStrategy,
      pod_ids: deviceStrategy === "specified" ? selectedPodIds : [],
      concurrency: Math.min(
        concurrency,
        plan.data.case_count,
        MAX_PLAN_CONCURRENCY,
      ),
      timeout_seconds: executionConfig.config.timeout_seconds,
      device_wait_timeout_seconds: executionDraft.device_wait_timeout_seconds,
      agent_config_mode: executionConfig.config.agent_config_mode,
      agent_options: executionConfig.config.agent_options ?? null,
    };
    const fingerprint = JSON.stringify(bodyWithoutKey);
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
              <span className="section-kicker">设备策略</span>
              <h2>配置并发和设备范围</h2>
            </div>
          </div>
          <DeviceStrategySelector
            strategy={deviceStrategy}
            onStrategyChange={(next) => changeConfiguration(() => {
              setDeviceStrategy(next);
              if (next === "automatic") setSelectedPodIds([]);
            })}
            concurrency={concurrency}
            onConcurrencyChange={handleConcurrencyChange}
            selectedPodIds={selectedPodIds}
            onSelectedPodIdsChange={handleSelectedPodIdsChange}
            maxConcurrency={Math.max(
              1,
              Math.min(plan.data?.case_count ?? MAX_PLAN_CONCURRENCY, MAX_PLAN_CONCURRENCY),
            )}
            disabled={runPlan.isPending}
            refetchInterval={!runPlan.isPending ? 3000 : false}
            onPodStateChange={(state) => { podStateRef.current = state; }}
            showSelectedStrip
            showPanelHeader
            hideLabel
            hintText=""
          />
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
