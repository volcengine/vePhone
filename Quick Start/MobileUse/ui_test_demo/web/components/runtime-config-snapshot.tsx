import { useId, useState } from "react";

import type { TaskExecutionConfig } from "../api/types";


function configured(value: unknown): boolean {
  if (value == null || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return true;
}

function displayValue(value: unknown, fallback = "-"): string {
  if (value == null || value === "") return fallback;
  return String(value);
}

function podIdDisplay(config: TaskExecutionConfig): string {
  if (config.pod_id) return config.pod_id;
  if (config.device_strategy === "specified" && config.pod_ids?.length) {
    return config.pod_ids.join(", ");
  }
  return "自动分配";
}

function formatJson(value: unknown): string {
  if (typeof value === "string") {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value;
    }
  }
  return JSON.stringify(value, null, 2);
}

function mcpServiceCount(value: string | null | undefined): number {
  if (!value) return 0;
  try {
    const parsed = JSON.parse(value);
    const servers = parsed?.mcpServers;
    return servers && typeof servers === "object"
      ? Object.keys(servers).length
      : 0;
  } catch {
    return 0;
  }
}

function ConfigRow({
  label,
  value,
  positive = false,
  title,
}: {
  label: string;
  value: string;
  positive?: boolean;
  title?: string;
}) {
  return (
    <div className="runtime-config-row">
      <span>{label}</span>
      <strong className={positive ? "configured" : undefined} title={title}>
        {positive && <span className="runtime-config-dot" aria-hidden="true" />}
        {value}
      </strong>
    </div>
  );
}

function AdvancedItem({
  title,
  value,
  emptyText,
}: {
  title: string;
  value: unknown;
  emptyText: string;
}) {
  const hasValue = configured(value);
  return (
    <article className="runtime-config-advanced-item">
      <div className="runtime-config-advanced-heading">
        <h4>{title}</h4>
        <span className={hasValue ? "configured" : "empty"}>
          {hasValue ? "已配置" : "未配置"}
        </span>
      </div>
      {hasValue ? (
        <pre>{formatJson(value)}</pre>
      ) : (
        <p>{emptyText}</p>
      )}
    </article>
  );
}

export function RuntimeConfigSnapshot({
  config,
}: {
  config: TaskExecutionConfig;
}) {
  const [expanded, setExpanded] = useState(false);
  const [headersOpen, setHeadersOpen] = useState(false);
  const drawerId = useId();
  const headerDialogTitleId = useId();
  const sourceLabel = config.source === "custom"
    ? "自定义配置"
    : config.source === "global"
      ? "全局配置"
      : config.source === "case_default"
        ? "用例默认配置"
        : "历史配置";
  const devicePrepareLabel = config.device_prepare_action === "reset"
    ? "重置设备"
    : config.device_prepare_action === "reboot"
      ? "重启设备"
      : "不处理";
  const requestHeaderNames = config.request_headers?.names ?? [];
  const requestHeaderItems = config.request_headers?.items?.length
    ? config.request_headers.items
    : requestHeaderNames.map((name) => ({ name, value: "-" }));
  const requestHeadersConfigured = Boolean(config.request_headers?.configured);
  const podIdText = podIdDisplay(config);
  const advanced = [
    ["SystemPrompt", config.system_prompt],
    ["McpJson", config.mcp_json],
    ["OutputSchema", config.output_schema],
    ["CallbackInfo", config.callback_info],
  ] as const;

  return (
    <section className="table-card runtime-config-card task-overview-config">
      <header className="runtime-config-header">
        <div className="runtime-config-title">
          <span className="runtime-config-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 2v3M12 19v3M4.9 4.9 7 7M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1" />
            </svg>
          </span>
          <div>
            <h2>运行配置快照</h2>
            <p>任务创建时固化，不受后续设置修改影响</p>
          </div>
        </div>
        <div className="runtime-config-badges">
          <span className={`runtime-config-source ${config.source}`}>
            {sourceLabel}
          </span>
          <span className="runtime-config-safe">
            <span aria-hidden="true" />
            已脱敏
          </span>
        </div>
      </header>

      {config.source === "global" && (
        <p className="runtime-config-notice">
          此处显示任务创建时继承的全局配置快照；之后修改系统设置，不会改变本任务记录。
        </p>
      )}

      <div className="runtime-config-identity">
        <div>
          <span>ProductID</span>
          <code translate="no" title={config.product_id ?? undefined}>
            {displayValue(config.product_id)}
          </code>
        </div>
        <div>
          <span>PodID</span>
          <code translate="no" title={podIdText === "自动分配" ? undefined : podIdText}>
            {podIdText}
          </code>
        </div>
        <div>
          <span>区域 / Bucket</span>
          <code
            translate="no"
            title={[config.tos_region, config.tos_bucket].filter(Boolean).join(" · ")}
          >
            {[config.tos_region, config.tos_bucket].filter(Boolean).join(" · ") || "-"}
          </code>
        </div>
      </div>

      <div className="runtime-config-groups">
        <section>
          <h3>执行边界</h3>
          <ConfigRow
            label="Timeout"
            value={config.timeout_seconds == null ? "-" : `${config.timeout_seconds} s`}
          />
          <ConfigRow
            label="设备等待超时"
            value={
              config.device_wait_timeout_seconds == null
                ? "-"
                : `${config.device_wait_timeout_seconds} s`
            }
          />
          <ConfigRow label="MaxStep" value={displayValue(config.max_step)} />
          <ConfigRow label="RetryLimit" value={displayValue(config.retry_limit)} />
          <ConfigRow
            label="设备启动前处理"
            value={devicePrepareLabel}
            positive={config.device_prepare_action !== "none"}
          />
          <ConfigRow
            label="MaxOutputTokens"
            value={displayValue(config.max_output_tokens, "默认")}
          />
        </section>
        <section>
          <h3>采集能力</h3>
          <ConfigRow
            label="屏幕录制"
            value={config.screen_record ? "开启" : "关闭"}
            positive={config.screen_record === true}
          />
          <ConfigRow
            label="Base64 截图"
            value={config.use_base64_screenshot ? "开启" : "关闭"}
            positive={config.use_base64_screenshot === true}
          />
          <ConfigRow
            label="GPS"
            value={configured(config.gps_info) ? "已设置" : "未设置"}
            positive={configured(config.gps_info)}
          />
          <ConfigRow
            label="回调"
            value={configured(config.callback_info) ? "已设置" : "未设置"}
            positive={configured(config.callback_info)}
          />
        </section>
        <section>
          <h3>存储与扩展</h3>
          <ConfigRow
            label="TOS Endpoint"
            value={displayValue(config.tos_endpoint, "默认端点")}
            title={config.tos_endpoint ?? undefined}
          />
          <ConfigRow
            label="MCP 服务"
            value={`${mcpServiceCount(config.mcp_json)} 项`}
          />
          <div className="runtime-config-row">
            <span>请求 Header</span>
            <button
              type="button"
              aria-label={
                requestHeadersConfigured ? "查看请求 Header" : "请求 Header 未设置"
              }
              className={`runtime-config-value-button${
                requestHeadersConfigured ? " configured" : ""
              }`}
              disabled={!requestHeadersConfigured}
              onClick={() => setHeadersOpen(true)}
            >
              {requestHeadersConfigured && (
                <span className="runtime-config-dot" aria-hidden="true" />
              )}
              {requestHeadersConfigured ? "已设置" : "未设置"}
            </button>
          </div>
          <ConfigRow
            label="输出结构"
            value={configured(config.output_schema) ? "已设置" : "未设置"}
            positive={configured(config.output_schema)}
          />
          <ConfigRow
            label="SystemPrompt"
            value={configured(config.system_prompt) ? "已设置" : "未设置"}
            positive={configured(config.system_prompt)}
          />
        </section>
      </div>

      <div className="runtime-config-advanced-bar">
        <div className="runtime-config-chips">
          {advanced.map(([label, value]) => (
            <span
              className={configured(value) ? undefined : "empty"}
              key={label}
            >
              {label}{configured(value) ? "" : " 未配置"}
            </span>
          ))}
        </div>
        <button
          type="button"
          aria-controls={drawerId}
          aria-expanded={expanded}
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? "收起高级配置" : "查看高级配置"}
          <svg
            className={expanded ? "expanded" : undefined}
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path d="m7 10 5 5 5-5" />
          </svg>
        </button>
      </div>

      {headersOpen && requestHeadersConfigured && (
        <div
          className="runtime-config-dialog-backdrop"
          onClick={() => setHeadersOpen(false)}
        >
          <div
            aria-labelledby={headerDialogTitleId}
            aria-modal="true"
            className="runtime-config-dialog"
            role="dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="runtime-config-dialog-header">
              <div>
                <span>已脱敏</span>
                <h3 id={headerDialogTitleId}>请求 Header</h3>
              </div>
              <button
                type="button"
                aria-label="关闭请求 Header 弹窗"
                onClick={() => setHeadersOpen(false)}
              >
                ×
              </button>
            </div>
            <p>Header 值已按敏感字段规则脱敏。</p>
            <ul>
              {requestHeaderItems.map((item) => (
                <li key={item.name}>
                  <code>{item.name}</code>
                  <span>{item.value}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {expanded && (
        <div
          className="runtime-config-advanced-grid"
          id={drawerId}
        >
          <AdvancedItem
            title="SystemPrompt"
            value={config.system_prompt}
            emptyText="本任务未配置 SystemPrompt。"
          />
          <AdvancedItem
            title="CallbackInfo"
            value={config.callback_info}
            emptyText="本任务未设置回调信息。"
          />
          <AdvancedItem
            title="OutputSchema"
            value={config.output_schema}
            emptyText="使用平台默认输出结构。"
          />
          <AdvancedItem
            title="McpJson"
            value={config.mcp_json}
            emptyText="本任务未挂载 MCP 服务。"
          />
        </div>
      )}
    </section>
  );
}
