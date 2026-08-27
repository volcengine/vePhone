import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { PodPoolResponse } from "../api/types";

export type DeviceStrategy = "automatic" | "specified";

function formatPodIdentity(pod: { pod_name?: string; pod_id: string }): string {
  const name = pod.pod_name?.trim();
  return name && name !== pod.pod_id ? `${name} · ${pod.pod_id}` : pod.pod_id;
}

export type DeviceStrategySelectorProps = {
  strategy: DeviceStrategy;
  onStrategyChange: (strategy: DeviceStrategy) => void;
  concurrency: number;
  onConcurrencyChange: (concurrency: number) => void;
  selectedPodIds: string[];
  onSelectedPodIdsChange: (podIds: string[]) => void;
  maxConcurrency?: number;
  disabled?: boolean;
  /** Controls pod-pool polling interval in ms. Set to false to disable. */
  refetchInterval?: number | false;
  /** Called with pod loading/error state and selectable pod IDs. Useful for form validation. */
  onPodStateChange?: (state: {
    isLoading: boolean;
    isError: boolean;
    isSuccess: boolean;
    selectablePodIds: Set<string>;
  }) => void;
  /** Show the selected-devices chip strip below the pod list. */
  showSelectedStrip?: boolean;
  /** Show the panel header ("可选设备" subtitle). */
  showPanelHeader?: boolean;
  /** Hide the outer "设备策略" label (for pages that have their own section heading). */
  hideLabel?: boolean;
  /** Override the hint text shown below the pod list. */
  hintText?: string;
  /** Pod status code that indicates the pod is online/runnable. Default: 1 (MUA). CUA uses 2. */
  onlineStatusCode?: number;
};

export function DeviceStrategySelector({
  strategy,
  onStrategyChange,
  concurrency,
  onConcurrencyChange,
  selectedPodIds,
  onSelectedPodIdsChange,
  maxConcurrency = 20,
  disabled = false,
  refetchInterval = 10000,
  onPodStateChange,
  showSelectedStrip = false,
  showPanelHeader = false,
  hideLabel = false,
  hintText,
  onlineStatusCode = 1,
}: DeviceStrategySelectorProps) {
  const [podSearch, setPodSearch] = useState("");

  const pods = useQuery({
    queryKey: ["pod-pool", "device-strategy-selector"],
    queryFn: () => api.post<PodPoolResponse>("/pod-pool/refresh"),
    enabled: strategy === "specified",
    refetchInterval: strategy === "specified" ? refetchInterval : false,
  });

  const selectablePods = useMemo(
    () =>
      (pods.data?.items ?? []).filter(
        (pod) =>
          pod.discovery_state === "active" && pod.pod_status_code === onlineStatusCode,
      ),
    [pods.data, onlineStatusCode],
  );

  const selectablePodIds = useMemo(
    () => new Set(selectablePods.map((pod) => pod.pod_id)),
    [selectablePods],
  );

  useEffect(() => {
    onPodStateChange?.({
      isLoading: pods.isLoading,
      isError: pods.isError,
      isSuccess: pods.isSuccess,
      selectablePodIds,
    });
  }, [pods.isLoading, pods.isError, pods.isSuccess, selectablePodIds, onPodStateChange]);

  const visiblePods = useMemo(() => {
    const keyword = podSearch.trim().toLowerCase();
    if (!keyword) return selectablePods;
    return selectablePods.filter((pod) => {
      const identity =
        `${pod.pod_name ?? ""} ${pod.pod_id} ${pod.local_state ?? ""}`.toLowerCase();
      return identity.includes(keyword);
    });
  }, [podSearch, selectablePods]);

  function togglePod(podId: string) {
    if (disabled) return;
    onSelectedPodIdsChange(
      selectedPodIds.includes(podId)
        ? selectedPodIds.filter((id) => id !== podId)
        : selectedPodIds.length >= concurrency
          ? selectedPodIds
          : [...selectedPodIds, podId],
    );
  }

  function handleStrategyChange(next: DeviceStrategy) {
    onStrategyChange(next);
    if (next === "automatic") {
      onSelectedPodIdsChange([]);
      setPodSearch("");
    }
  }

  return (
    <div>
      {!hideLabel && (
        <label className="form-label" style={{ marginBottom: 8, display: "block" }}>
          设备策略
        </label>
      )}
      <div className="plan-run-device-row">
        <div className="plan-run-strategy-grid">
          <label className={strategy === "automatic" ? "selected" : ""}>
            <input
              type="radio"
              aria-label="自动分配"
              name="device-strategy"
              value="automatic"
              checked={strategy === "automatic"}
              disabled={disabled}
              onChange={() => handleStrategyChange("automatic")}
            />
            <strong>自动分配</strong>
            <span>从当前设备池中动态分配空闲设备</span>
          </label>
          <label className={strategy === "specified" ? "selected" : ""}>
            <input
              type="radio"
              aria-label="指定设备"
              name="device-strategy"
              value="specified"
              checked={strategy === "specified"}
              disabled={disabled}
              onChange={() => handleStrategyChange("specified")}
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
            disabled={disabled}
            onChange={(event) =>
              onConcurrencyChange(
                Math.max(
                  1,
                  Math.min(maxConcurrency, Number(event.target.value) || 1),
                ),
              )}
          />
          <small>最大不超过 {maxConcurrency} 个并发任务</small>
        </label>
      </div>

      {strategy === "specified" && (
        <div className={showSelectedStrip || showPanelHeader ? "plan-run-device-select" : undefined} style={showSelectedStrip || showPanelHeader ? undefined : { marginTop: 12 }}>
          {!hideLabel && <label className="form-label">选择设备</label>}
          {pods.isLoading ? (
            <p className="muted">正在加载设备池…</p>
          ) : pods.isError ? (
            <div className="form-error">
              <span>设备池加载失败</span>
              <button
                type="button"
                className="secondary-button"
                onClick={() => void pods.refetch()}
              >
                重新加载
              </button>
            </div>
          ) : selectablePods.length === 0 ? (
            <div className="plan-case-empty">暂无可选设备</div>
          ) : (
            <div className="plan-run-field plan-run-pod-field">
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
                    disabled={disabled}
                  />
                </label>
                <span className="plan-run-pod-quota">
                  已选 {selectedPodIds.length} / {concurrency}
                </span>
              </div>
              {showPanelHeader && (
                <div className="plan-run-device-panel-header">
                  <div>
                    <strong>可选设备</strong>
                    <span>在指定范围内按并发排队执行</span>
                  </div>
                </div>
              )}
              <div className="plan-run-pod-list" role="group">
                {visiblePods.length === 0 ? (
                  <div className="plan-run-pod-empty">
                    没有匹配的设备
                  </div>
                ) : (
                  visiblePods.map((pod) => {
                    const selected = selectedPodIds.includes(pod.pod_id);
                    const isDisabled =
                      disabled || (!selected && selectedPodIds.length >= concurrency);
                    const statusText =
                      pod.local_state === "available"
                        ? "可用"
                        : "繁忙 · 将排队";
                    return (
                      <label
                        key={pod.pod_id}
                        className={[
                          "plan-run-pod-option",
                          selected ? "selected" : "",
                          isDisabled ? "disabled" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                      >
                        <input
                          type="checkbox"
                          name="pod_ids"
                          value={pod.pod_id}
                          checked={selected}
                          disabled={isDisabled}
                          aria-label={`${pod.pod_name} ${pod.pod_id}`}
                          onChange={() => togglePod(pod.pod_id)}
                        />
                        <span>
                          <strong>{formatPodIdentity(pod)}</strong>
                          <code translate="no">{pod.pod_id}</code>
                        </span>
                        <em
                          className={
                            pod.local_state === "available"
                              ? "available"
                              : "busy"
                          }
                        >
                          {statusText}
                        </em>
                      </label>
                    );
                  })
                )}
              </div>
              {showSelectedStrip && (
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
                      disabled={disabled}
                    >
                      <span>{podId}</span>
                      <span aria-hidden="true">×</span>
                    </button>
                  ))}
                </div>
              )}
              {(hintText || !showSelectedStrip) && (
                <p
                  style={{
                    fontSize: 11,
                    color: "var(--mua-neutral-500)",
                    marginTop: 8,
                  }}
                >
                  {hintText ?? "触发时若指定设备繁忙，任务将排队等待；超过等待超时时间仍不可用则失败。"}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
