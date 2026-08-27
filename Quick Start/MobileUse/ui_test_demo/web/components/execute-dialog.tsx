import { useEffect, useId, useRef, useState } from "react";

import { ApiError, api } from "../api/client";
import type { PodPoolItem } from "../api/types";
import {
  buildExecuteConfig,
  createExecutionConfigDraft,
  ExecutionConfigFields,
  type ExecuteConfig,
  type ExecutionConfigDraft,
} from "./execution-config-form";

function XIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points="6 3 20 12 6 21 6 3" />
    </svg>
  );
}

export function ExecuteDialog({
  open,
  caseTitle,
  onClose,
  onConfirm,
  isPending,
  errorMessage = "",
  showDeviceSelection = true,
  allowCaseDefault = false,
  showDeviceWaitTimeout = false,
}: {
  open: boolean;
  caseTitle: string;
  onClose: () => void;
  onConfirm: (config: ExecuteConfig) => void;
  isPending?: boolean;
  errorMessage?: string;
  showDeviceSelection?: boolean;
  allowCaseDefault?: boolean;
  showDeviceWaitTimeout?: boolean;
}) {
  const [podId, setPodId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ExecutionConfigDraft>(
    createExecutionConfigDraft,
  );
  const [formError, setFormError] = useState("");
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const podsQuery = usePodPoolRefresh(open && showDeviceSelection);

  useEffect(() => {
    if (open) {
      setPodId(null);
      setDraft(createExecutionConfigDraft());
      setFormError("");
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !isPending) onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isPending, onClose, open]);

  if (!open) return null;

  const availablePods = podsQuery.data?.items ?? [];
  const idlePods = availablePods.filter(
    (pod) => !pod.task_id && pod.local_state === "available",
  );

  function submit() {
    const result = buildExecuteConfig(draft);
    setFormError(result.error);
    if (!result.config) return;
    onConfirm({ ...result.config, pod_id: podId });
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
        aria-labelledby={titleId}
      >
        <div className="modal-header">
          <h3 id={titleId}>执行配置</h3>
          <button
            ref={closeRef}
            type="button"
            className="icon-action"
            onClick={onClose}
            aria-label="关闭"
            disabled={isPending}
          >
            <XIcon />
          </button>
        </div>
        <div className="modal-body">
          <p className="modal-case-title">
            <PlayIcon />
            <span>{caseTitle}</span>
          </p>

          {showDeviceSelection && (
            <div className="form-group">
              <label className="form-label" htmlFor="execute-target-pod">
                目标设备
              </label>
              <select
                id="execute-target-pod"
                name="execute-target-pod"
                className="form-select"
                value={podId ?? ""}
                onChange={(event) =>
                  setPodId(event.target.value || null)}
                disabled={Boolean(isPending) || podsQuery.isLoading}
              >
                <option value="">自动分配空闲设备</option>
                {podsQuery.error ? (
                  <option value="" disabled>刷新设备列表失败</option>
                ) : idlePods.length === 0 ? (
                  <option value="" disabled>暂无空闲设备</option>
                ) : (
                  idlePods.map((pod) => (
                    <option key={pod.pod_id} value={pod.pod_id}>
                      {pod.pod_name || pod.pod_id}
                      {pod.config_name ? ` (${pod.config_name})` : ""}
                    </option>
                  ))
                )}
              </select>
              {podId && (
                <p className="form-hint">
                  将在指定设备上执行，如设备繁忙将返回错误
                </p>
              )}
            </div>
          )}

          <ExecutionConfigFields
            value={draft}
            onChange={(next) => {
              setDraft(next);
              setFormError("");
            }}
            disabled={Boolean(isPending)}
            allowCaseDefault={allowCaseDefault}
            showDeviceWaitTimeout={showDeviceWaitTimeout}
          />
          {formError && (
            <p className="form-error" role="alert">{formError}</p>
          )}
          {errorMessage && (
            <p className="form-error" role="alert">{errorMessage}</p>
          )}
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
            onClick={submit}
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

function usePodPoolRefresh(enabled: boolean) {
  const [data, setData] = useState<{ items: PodPoolItem[] } | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    setIsLoading(true);
    setError(null);
    setData(null);
    api.post<{ items: PodPoolItem[] }>("/pod-pool/refresh")
      .then((response) => {
        if (active) setData({ items: response.items });
      })
      .catch((caught) => {
        if (active) {
          setError(caught instanceof ApiError ? caught : null);
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [enabled]);

  return { data, error, isLoading };
}

export type { ExecuteConfig };
