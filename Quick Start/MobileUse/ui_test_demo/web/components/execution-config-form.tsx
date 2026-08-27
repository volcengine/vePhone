import { useEffect, useState } from "react";

import type { AgentRuntimeOptions, DevicePrepareAction } from "../api/types";

export type ExecuteConfig = {
  pod_id: string | null;
  timeout_seconds: number | null;
  device_wait_timeout_seconds: number;
  agent_config_mode: "global" | "custom" | "case_default";
  agent_options?: AgentRuntimeOptions | null;
};

export type CustomExecutionForm = {
  thread_id: string;
  use_base64_screenshot: boolean;
  max_step: number;
  timeout_seconds: number;
  callback_info: string;
  output_schema: string;
  retry_limit: number;
  system_prompt: string;
  tos_bucket: string;
  tos_endpoint: string;
  tos_region: string;
  screen_record: boolean;
  mcp_json: string;
  max_output_tokens: string;
  gps_info: string;
  request_headers: string;
};

export type ExecutionConfigDraft = {
  timeout_seconds: number;
  device_wait_timeout_seconds: number;
  customTimeout: boolean;
  device_prepare_action: DevicePrepareAction;
  agent_config_mode: "global" | "custom" | "case_default";
  custom: CustomExecutionForm;
};

export const DEFAULT_EXECUTION_CONFIG: ExecutionConfigDraft = {
  timeout_seconds: 120,
  device_wait_timeout_seconds: 300,
  customTimeout: false,
  device_prepare_action: "none",
  agent_config_mode: "global",
  custom: {
    thread_id: "",
    use_base64_screenshot: false,
    max_step: 100,
    timeout_seconds: 120,
    callback_info: "",
    output_schema: "",
    retry_limit: 3,
    system_prompt: "",
    tos_bucket: "",
    tos_endpoint: "",
    tos_region: "cn-beijing",
    screen_record: false,
    mcp_json: "",
    max_output_tokens: "",
    gps_info: "",
    request_headers: "",
  },
};

const REQUEST_HEADERS_PLACEHOLDER = '{"X-Env":"test","X-Request-Source":"mua"}';
const RESERVED_REQUEST_HEADERS = new Set([
  "accept",
  "authorization",
  "content-length",
  "content-type",
  "host",
  "user-agent",
  "x-content-sha256",
  "x-date",
]);

const AGENT_CONFIG_OPTIONS = [
  { value: "global", label: "使用全局配置" },
  { value: "custom", label: "自定义本次执行配置" },
  { value: "case_default", label: "用例默认配置" },
] as const;
const DEVICE_PREPARE_OPTIONS = [
  { value: "none", label: "不处理" },
  { value: "reset", label: "重置设备" },
  { value: "reboot", label: "重启设备" },
] as const;
const CLEARABLE_CUSTOM_FIELDS = new Set<keyof CustomExecutionForm>([
  "max_output_tokens",
  "system_prompt",
  "callback_info",
  "output_schema",
  "mcp_json",
  "gps_info",
  "request_headers",
]);
const DEVICE_WAIT_TIMEOUT_MIN = 1;
const DEVICE_WAIT_TIMEOUT_MAX = 86400;

function clampDeviceWaitTimeout(value: number): number {
  return Math.max(
    DEVICE_WAIT_TIMEOUT_MIN,
    Math.min(DEVICE_WAIT_TIMEOUT_MAX, value),
  );
}

export function DeviceWaitTimeoutField({
  id,
  name = "device_wait_timeout_seconds",
  value,
  onChange,
  disabled = false,
  wrapperClassName = "plan-run-field plan-run-schedule-timeout",
  labelClassName,
  inputClassName,
  hintClassName,
}: {
  id: string;
  name?: string;
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  wrapperClassName?: string;
  labelClassName?: string;
  inputClassName?: string;
  hintClassName?: string;
}) {
  const [inputValue, setInputValue] = useState(String(value));

  useEffect(() => {
    setInputValue(String(value));
  }, [value]);

  function commit(raw: string) {
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return;
    onChange(clampDeviceWaitTimeout(parsed));
  }

  function resetIfEmptyOrInvalid() {
    if (inputValue.trim() === "" || !Number.isFinite(Number(inputValue))) {
      setInputValue(String(value));
      return;
    }
    commit(inputValue);
  }

  return (
    <label className={wrapperClassName}>
      <span className={labelClassName}>设备不可用后最大等待时间（秒）</span>
      <input
        id={id}
        name={name}
        autoComplete="off"
        className={inputClassName}
        type="number"
        aria-label="设备不可用后最大等待时间（秒）"
        min={DEVICE_WAIT_TIMEOUT_MIN}
        max={DEVICE_WAIT_TIMEOUT_MAX}
        value={inputValue}
        onChange={(event) => {
          const next = event.target.value;
          setInputValue(next);
          if (next.trim() !== "") commit(next);
        }}
        onBlur={resetIfEmptyOrInvalid}
        disabled={disabled}
      />
      <small className={hintClassName}>
        平台会定期刷新设备状态；超过该时间且设备仍不可用时，剩余任务将失败。
      </small>
    </label>
  );
}

export function createExecutionConfigDraft(): ExecutionConfigDraft {
  return {
    ...DEFAULT_EXECUTION_CONFIG,
    custom: { ...DEFAULT_EXECUTION_CONFIG.custom },
  };
}

export function createExecutionConfigDraftFromOptions(
  options: AgentRuntimeOptions | null | undefined,
): ExecutionConfigDraft {
  const draft = createExecutionConfigDraft();
  if (!options) return { ...draft, agent_config_mode: "custom" };
  return {
    ...draft,
    timeout_seconds: options.timeout_seconds ?? draft.timeout_seconds,
    device_prepare_action: options.device_prepare_action
      ?? draft.device_prepare_action,
    agent_config_mode: "custom",
    custom: {
      ...draft.custom,
      thread_id: options.thread_id ?? "",
      use_base64_screenshot: Boolean(options.use_base64_screenshot),
      max_step: options.max_step ?? draft.custom.max_step,
      timeout_seconds: options.timeout_seconds ?? draft.custom.timeout_seconds,
      callback_info: options.callback_info
        ? JSON.stringify(options.callback_info, null, 2)
        : "",
      output_schema: options.output_schema ?? "",
      retry_limit: options.retry_limit ?? draft.custom.retry_limit,
      system_prompt: options.system_prompt ?? "",
      tos_bucket: options.tos_bucket ?? "",
      tos_endpoint: options.tos_endpoint ?? "",
      tos_region: options.tos_region ?? draft.custom.tos_region,
      screen_record: Boolean(options.screen_record),
      mcp_json: options.mcp_json ?? "",
      max_output_tokens: options.max_output_tokens
        ? String(options.max_output_tokens)
        : "",
      gps_info: options.gps_info ?? "",
      request_headers: options.request_headers
        ? JSON.stringify(options.request_headers, null, 2)
        : "",
    },
  };
}

export function buildExecuteConfig(
  draft: ExecutionConfigDraft,
): { config: ExecuteConfig | null; error: string } {
  if (draft.agent_config_mode === "global") {
    return {
      config: {
        pod_id: null,
        timeout_seconds: null,
          device_wait_timeout_seconds: draft.device_wait_timeout_seconds,
        agent_config_mode: "global",
        agent_options: null,
      },
      error: "",
    };
  }
  if (draft.agent_config_mode === "case_default") {
    return {
      config: {
        pod_id: null,
        timeout_seconds: null,
          device_wait_timeout_seconds: draft.device_wait_timeout_seconds,
        agent_config_mode: "case_default",
        agent_options: null,
      },
      error: "",
    };
  }

  const callbackInfo = parseJsonObject(
    draft.custom.callback_info,
    "CallbackInfo",
  );
  if (typeof callbackInfo === "string") {
    return { config: null, error: callbackInfo };
  }
  const outputError = validateJsonString(
    draft.custom.output_schema,
    "OutputSchema",
  );
  if (outputError) return { config: null, error: outputError };
  const mcpError = validateJsonString(draft.custom.mcp_json, "McpJson");
  if (mcpError) return { config: null, error: mcpError };
  const requestHeaders = parseRequestHeaders(draft.custom.request_headers);
  if (typeof requestHeaders === "string") {
    return { config: null, error: requestHeaders };
  }

  const options: AgentRuntimeOptions = {
    thread_id: optionalString(draft.custom.thread_id),
    use_base64_screenshot: draft.custom.use_base64_screenshot,
    max_step: draft.custom.max_step,
    timeout_seconds: draft.custom.timeout_seconds,
    callback_info: callbackInfo,
    output_schema: optionalString(draft.custom.output_schema),
    retry_limit: draft.custom.retry_limit,
    system_prompt: optionalString(draft.custom.system_prompt),
    tos_bucket: optionalString(draft.custom.tos_bucket),
    tos_endpoint: optionalString(draft.custom.tos_endpoint),
    tos_region: optionalString(draft.custom.tos_region),
    screen_record: draft.custom.screen_record,
    mcp_json: optionalString(draft.custom.mcp_json),
    max_output_tokens: draft.custom.max_output_tokens
      ? Number(draft.custom.max_output_tokens)
      : null,
    gps_info: optionalString(draft.custom.gps_info),
    request_headers: requestHeaders,
    device_prepare_action: draft.device_prepare_action,
  };
  return {
    config: {
      pod_id: null,
      timeout_seconds: draft.custom.timeout_seconds,
        device_wait_timeout_seconds: draft.device_wait_timeout_seconds,
      agent_config_mode: "custom",
      agent_options: options,
    },
    error: "",
  };
}

export function ExecutionConfigFields({
  value,
  onChange,
  disabled = false,
  idPrefix = "execute",
  allowCaseDefault = false,
  customConfigLabel = "自定义本次执行配置",
  caseDefaultLabel = "用例默认配置",
  showModeSelector = true,
  showThreadId = true,
  showDeviceWaitTimeout = false,
}: {
  value: ExecutionConfigDraft;
  onChange: (value: ExecutionConfigDraft) => void;
  disabled?: boolean;
  idPrefix?: string;
  allowCaseDefault?: boolean;
  customConfigLabel?: string;
  caseDefaultLabel?: string;
  showModeSelector?: boolean;
  showThreadId?: boolean;
  showDeviceWaitTimeout?: boolean;
}) {
  const customMode = value.agent_config_mode === "custom";
  const caseDefaultMode = value.agent_config_mode === "case_default";
  const modeOptions = AGENT_CONFIG_OPTIONS
    .filter((option) => allowCaseDefault || option.value !== "case_default")
    .map((option) => {
      if (option.value === "case_default") {
        return { ...option, label: caseDefaultLabel };
      }
      if (option.value === "custom") {
        return { ...option, label: customConfigLabel };
      }
      return option;
    });

  function updateCustom<K extends keyof CustomExecutionForm>(
    field: K,
    next: CustomExecutionForm[K],
  ) {
    onChange({
      ...value,
      custom: { ...value.custom, [field]: next },
    });
  }

  function clearCustom(field: keyof CustomExecutionForm) {
    updateCustom(field as never, "" as never);
  }

  function fieldHeading(field: keyof CustomExecutionForm, label: string, inputId: string) {
    const canClear = CLEARABLE_CUSTOM_FIELDS.has(field)
      && String(value.custom[field] ?? "").trim().length > 0
      && !disabled;
    return (
      <div className="execution-config-field-heading">
        <label className="form-label" htmlFor={inputId}>{label}</label>
        {canClear && (
          <button
            type="button"
            className="text-button execution-config-clear"
            onClick={() => clearCustom(field)}
          >
            清除
            <span className="sr-only">{` ${label}`}</span>
          </button>
        )}
      </div>
    );
  }

  function renderNumberField(
    field: "max_step" | "timeout_seconds" | "retry_limit",
    label: string,
    min: number,
    max: number,
  ) {
    const inputId = `${idPrefix}-custom-${field}`;
    return (
      <div className="form-group">
        {fieldHeading(field, label, inputId)}
        <input
          id={inputId}
          name={inputId}
          autoComplete="off"
          className="form-input"
          max={max}
          min={min}
          type="number"
          disabled={disabled}
          value={value.custom[field]}
          onChange={(event) =>
            updateCustom(
              field,
              Math.max(
                min,
                Math.min(max, Number(event.target.value) || min),
              ),
            )}
        />
      </div>
    );
  }

  function renderTextField(
    field: keyof CustomExecutionForm,
    label: string,
  ) {
    const inputId = `${idPrefix}-custom-${field}`;
    return (
      <div className="form-group">
        {fieldHeading(field, label, inputId)}
        <input
          id={inputId}
          name={inputId}
          autoComplete="off"
          className="form-input"
          disabled={disabled}
          value={String(value.custom[field] ?? "")}
          onChange={(event) =>
            updateCustom(field as never, event.target.value as never)}
        />
      </div>
    );
  }

  function renderTextArea(
    field: keyof CustomExecutionForm,
    label: string,
    placeholder = "",
  ) {
    const inputId = `${idPrefix}-custom-${field}`;
    return (
      <div className="form-group">
        {fieldHeading(field, label, inputId)}
        <textarea
          id={inputId}
          name={inputId}
          autoComplete="off"
          className="form-input"
          rows={3}
          placeholder={placeholder}
          disabled={disabled}
          value={String(value.custom[field] ?? "")}
          onChange={(event) =>
            updateCustom(field as never, event.target.value as never)}
        />
      </div>
    );
  }

  return (
    <div className="execution-config-fields">
      {showModeSelector && (
      <div className="form-group">
        <span className="form-label" id={`${idPrefix}-agent-config-label`}>
          代理任务配置
        </span>
        <div
          className="execution-agent-mode-seg"
          role="radiogroup"
          aria-labelledby={`${idPrefix}-agent-config-label`}
        >
          {modeOptions.map((option) => {
            const selected = value.agent_config_mode === option.value;
            return (
              <label
                key={option.value}
                className={`agent-mode-seg-option${selected ? " on" : ""}`}
              >
                <input
                  type="radio"
                  name={`${idPrefix}-agent-config-mode`}
                  value={option.value}
                  checked={selected}
                  disabled={disabled}
                  onChange={() =>
                    onChange({
                      ...value,
                      agent_config_mode: option.value,
                    })}
                />
                <span>{option.label}</span>
              </label>
            );
          })}
        </div>
        <p className="form-hint execution-config-hint">
          {caseDefaultMode
            ? "读取用例编辑页保存的默认 Agent 参数。"
            : customMode
              ? "自定义配置仅影响当前任务，不会保存到全局设置。"
              : "读取设置页保存的 Agent 参数，可在下方摘要中确认。"}
        </p>
      </div>
      )}

      {showDeviceWaitTimeout && (
        <DeviceWaitTimeoutField
          id={`${idPrefix}-device-wait-timeout-seconds`}
          name={`${idPrefix}-device-wait-timeout-seconds`}
          value={value.device_wait_timeout_seconds}
          onChange={(next) =>
            onChange({
              ...value,
              device_wait_timeout_seconds: next,
            })}
          disabled={disabled}
          wrapperClassName="form-group"
          labelClassName="form-label"
          inputClassName="form-input"
          hintClassName="form-hint execution-config-hint"
        />
      )}

      {!showModeSelector ? null : caseDefaultMode ? (
        <div className="agent-global-summary">
          <div className="agent-global-summary-head">
            <span className="agent-global-summary-bar" />
            <h4>将套用用例默认配置</h4>
            <span className="agent-global-summary-tag">来自用例</span>
          </div>
          <p className="agent-global-summary-note">
            本次执行将读取当前用例保存的默认 Agent 参数；如需临时覆盖，切换到「自定义本次执行配置」。
          </p>
        </div>
      ) : !customMode && (
        <div className="agent-global-summary">
          <div className="agent-global-summary-head">
            <span className="agent-global-summary-bar" />
            <h4>将套用的全局配置</h4>
            <span className="agent-global-summary-tag">来自设置页</span>
          </div>
          <p className="agent-global-summary-note">
            本次执行将直接读取设置页保存的 Agent 参数，无需在此调整。如需临时覆盖，切换到「自定义本次执行配置」。
          </p>
        </div>
      )}

      {(customMode || !showModeSelector) && (
        <div className="custom-agent-config">
          <section className="custom-agent-section">
            <h4>运行控制</h4>
            <div className="form-group">
              <span
                className="form-label"
                id={`${idPrefix}-device-prepare-label`}
              >
                设备启动前处理
              </span>
              <div
                className="execution-agent-mode-seg"
                role="radiogroup"
                aria-labelledby={`${idPrefix}-device-prepare-label`}
              >
                {DEVICE_PREPARE_OPTIONS.map((option) => {
                  const selected = value.device_prepare_action === option.value;
                  return (
                    <label
                      key={option.value}
                      className={`agent-mode-seg-option${selected ? " on" : ""}`}
                    >
                      <input
                        type="radio"
                        name={`${idPrefix}-device-prepare-action`}
                        value={option.value}
                        checked={selected}
                        disabled={disabled}
                        onChange={() =>
                          onChange({
                            ...value,
                            device_prepare_action: option.value,
                          })}
                      />
                      <span>{option.label}</span>
                    </label>
                  );
                })}
              </div>
              <p className="form-hint execution-config-hint">
                默认不处理；选择重置或重启后，将在任务启动 Agent 前处理设备。
              </p>
            </div>
            <div className="form-grid custom-agent-number-grid">
              {showThreadId && renderTextField("thread_id", "ThreadId")}
              {renderNumberField("max_step", "最大步骤数 MaxStep", 1, 500)}
              {renderNumberField(
                "timeout_seconds",
                "任务超时 Timeout（秒）",
                1,
                86400,
              )}
              {renderNumberField(
                "retry_limit",
                "重试次数 RetryLimit",
                1,
                10,
              )}
              <div className="form-group">
                {fieldHeading(
                  "max_output_tokens",
                  "最大输出 Token",
                  `${idPrefix}-custom-max-output-tokens`,
                )}
                <input
                  id={`${idPrefix}-custom-max-output-tokens`}
                  name={`${idPrefix}-custom-max-output-tokens`}
                  autoComplete="off"
                  className="form-input"
                  min={1}
                  type="number"
                  disabled={disabled}
                  value={value.custom.max_output_tokens}
                  onChange={(event) =>
                    updateCustom("max_output_tokens", event.target.value)}
                />
              </div>
            </div>
          </section>

          <section className="custom-agent-section">
            <h4>开关</h4>
            <div className="custom-agent-switches">
              <label className="checkbox-row">
                <input
                  name={`${idPrefix}-custom-use-base64-screenshot`}
                  checked={value.custom.use_base64_screenshot}
                  type="checkbox"
                  disabled={disabled}
                  onChange={(event) =>
                    updateCustom(
                      "use_base64_screenshot",
                      event.target.checked,
                    )}
                />
                <span className="checkbox-box" aria-hidden="true" />
                <span>UseBase64Screenshot：截图以 Base64 编码返回</span>
              </label>
              <label className="checkbox-row">
                <input
                  name={`${idPrefix}-custom-screen-record`}
                  checked={value.custom.screen_record}
                  type="checkbox"
                  disabled={disabled}
                  onChange={(event) =>
                    updateCustom("screen_record", event.target.checked)}
                />
                <span className="checkbox-box" aria-hidden="true" />
                <span>IsScreenRecord：开启云手机录屏</span>
              </label>
            </div>
          </section>

          <section className="custom-agent-section">
            <h4>对象存储与定位</h4>
            <div className="form-grid custom-agent-storage-grid">
              {renderTextField("tos_bucket", "TosBucket")}
              {renderTextField("tos_endpoint", "TosEndpoint")}
              {renderTextField("tos_region", "TosRegion")}
              {renderTextField("gps_info", "GpsInfo")}
            </div>
          </section>

          <section className="custom-agent-section">
            <h4>高级参数</h4>
            <div className="form-grid custom-agent-advanced-grid">
              {renderTextArea("system_prompt", "SystemPrompt")}
              {renderTextArea(
                "callback_info",
                "CallbackInfo（JSON 对象）",
              )}
              {renderTextArea(
                "output_schema",
                "OutputSchema（JSON 字符串）",
              )}
              {renderTextArea("mcp_json", "McpJson（JSON 字符串）")}
              {renderTextArea(
                "request_headers",
                "请求 Header（JSON 对象）",
                REQUEST_HEADERS_PLACEHOLDER,
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function optionalString(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function parseJsonObject(
  value: string,
  label: string,
): Record<string, unknown> | null | string {
  const trimmed = value.trim();
  if (!trimmed) return null;
  try {
    const parsed = JSON.parse(trimmed);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      return `${label} 必须是 JSON 对象`;
    }
    return parsed as Record<string, unknown>;
  } catch {
    return `${label} 不是合法 JSON`;
  }
}

function validateJsonString(value: string, label: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";
  try {
    JSON.parse(trimmed);
    return "";
  } catch {
    return `${label} 不是合法 JSON 字符串`;
  }
}

function parseRequestHeaders(
  value: string,
): Record<string, string> | null | string {
  const parsed = parseJsonObject(value, "请求 Header");
  if (parsed === null || typeof parsed === "string") return parsed;
  for (const [name, headerValue] of Object.entries(parsed)) {
    if (RESERVED_REQUEST_HEADERS.has(name.trim().toLowerCase())) {
      return `请求 Header 包含不允许覆盖的保留字段：${name}`;
    }
    if (typeof headerValue !== "string") {
      return "请求 Header 的值必须是字符串";
    }
  }
  return parsed as Record<string, string>;
}
