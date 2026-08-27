import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { FormEvent, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router";

import { api } from "../api/client";
import type { RunnerSettingsUpdate, User } from "../api/types";
import { defaultBusiness, useBusinessContext } from "../business-context";

function NavIcon({ path }: { path: string }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

const NAV_ITEMS = [
  { to: "/cases", label: "用例库", icon: "M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2zM22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" },
  { to: "/test-plans", label: "测试计划", icon: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" },
  { to: "/task-reports", label: "测试报告", icon: "M4 4h16v16H4zM8 9h8M8 13h6M8 17h4" },
  { to: "/", end: true, label: "执行记录", icon: "M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" },
  { to: "/pods", label: "设备池", icon: "M10.5 1.5H8.25A2.25 2.25 0 0 0 6 3.75v16.5a2.25 2.25 0 0 0 2.25 2.25h7.5A2.25 2.25 0 0 0 18 20.25V3.75a2.25 2.25 0 0 0-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3" },
  { to: "/users", label: "用户管理", adminOnly: true, icon: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" },
  { to: "/settings", label: "设置", icon: "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" },
];

type BusinessConfigField =
  | "account_id"
  | "access_key_id"
  | "secret_access_key"
  | "tos_bucket"
  | "tos_region"
  | "timeout_seconds"
  | "max_step"
  | "request_headers";

const EMPTY_BUSINESS_CONFIG: Record<BusinessConfigField, string> = {
  account_id: "",
  access_key_id: "",
  secret_access_key: "",
  tos_bucket: "",
  tos_region: "",
  timeout_seconds: "120",
  max_step: "100",
  request_headers: "",
};

function parseBusinessConcurrencyLimit(value: string): number | null {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= 8
    ? parsed
    : null;
}

type BusinessRunnerSettingsUpdate = RunnerSettingsUpdate & {
  mobile_use: NonNullable<RunnerSettingsUpdate["mobile_use"]>;
};

function LogoIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10 2v7.31M14 9.3V1.99M8.5 2h7M14 9.3a6.5 6.5 0 1 1-4 0" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
    </svg>
  );
}

function UserInitials({ name }: { name: string }) {
  const trimmed = name.trim();
  return <>{trimmed ? trimmed.slice(0, 2).toUpperCase() : "MU"}</>;
}

export function AppShell({ children, user }: { children: ReactNode; user: User }) {
  const queryClient = useQueryClient();
  const businessContext = useBusinessContext();
  const currentBusiness = businessContext?.currentBusiness ?? defaultBusiness();
  const linkFor = businessContext?.businessPath ?? ((path = "/tasks") => path);
  const businessSwitcherRef = useRef<HTMLDivElement | null>(null);
  const [businessMenuOpen, setBusinessMenuOpen] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [businessName, setBusinessName] = useState("");
  const [businessDescription, setBusinessDescription] = useState("");
  const [businessConcurrencyLimit, setBusinessConcurrencyLimit] = useState("4");
  const [businessConfig, setBusinessConfig] =
    useState<Record<BusinessConfigField, string>>(EMPTY_BUSINESS_CONFIG);
  const [businessError, setBusinessError] = useState("");
  const [businessCreatePending, setBusinessCreatePending] = useState(false);
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [renameName, setRenameName] = useState("");
  const [renameDescription, setRenameDescription] = useState("");
  const [renameConcurrencyLimit, setRenameConcurrencyLimit] = useState("4");
  const [renameError, setRenameError] = useState("");
  const [renamePending, setRenamePending] = useState(false);
  const logout = useMutation({
    mutationFn: () => api.post("/auth/logout"),
    onSuccess: () => {
      queryClient.setQueryData(["current-user"], null);
    },
  });

  useEffect(() => {
    if (!businessMenuOpen) return;
    function closeOnOutsidePointer(event: PointerEvent) {
      const target = event.target;
      if (
        target instanceof Node
        && businessSwitcherRef.current
        && !businessSwitcherRef.current.contains(target)
      ) {
        setBusinessMenuOpen(false);
      }
    }
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    return () => document.removeEventListener("pointerdown", closeOnOutsidePointer);
  }, [businessMenuOpen]);

  function resetBusinessDialog() {
    setBusinessName("");
    setBusinessDescription("");
    setBusinessConcurrencyLimit("4");
    setBusinessConfig(EMPTY_BUSINESS_CONFIG);
    setBusinessError("");
  }

  function updateBusinessConfig(field: BusinessConfigField, value: string) {
    setBusinessConfig((current) => ({ ...current, [field]: value }));
    setBusinessError("");
  }

  function openRenameDialog() {
    setRenameName(currentBusiness.name);
    setRenameDescription(currentBusiness.description ?? "");
    setRenameConcurrencyLimit(String(currentBusiness.task_concurrency_limit));
    setRenameError("");
    setRenameDialogOpen(true);
  }

  async function submitBusinessRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!businessContext) return;
    const name = renameName.trim();
    if (!name) {
      setRenameError("业务名称不能为空");
      return;
    }
    const concurrencyLimit = parseBusinessConcurrencyLimit(renameConcurrencyLimit);
    if (concurrencyLimit === null) {
      setRenameError("任务并发上限必须是 1 到 8 之间的整数");
      return;
    }
    setRenamePending(true);
    setRenameError("");
    try {
      await businessContext.updateBusiness(currentBusiness.id, {
        name,
        description: renameDescription.trim() || null,
        task_concurrency_limit: concurrencyLimit,
      });
      setRenameDialogOpen(false);
      setBusinessMenuOpen(false);
    } catch (error) {
      setRenameError(error instanceof Error ? error.message : "重命名失败");
    } finally {
      setRenamePending(false);
    }
  }

  async function submitBusinessCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!businessContext) return;
    const name = businessName.trim();
    if (!name) {
      setBusinessError("业务名称不能为空");
      return;
    }
    const concurrencyLimit = parseBusinessConcurrencyLimit(businessConcurrencyLimit);
    if (concurrencyLimit === null) {
      setBusinessError("任务并发上限必须是 1 到 8 之间的整数");
      return;
    }
    const settingsPayload = buildBusinessSettingsPayload(businessConfig);
    if (typeof settingsPayload === "string") {
      setBusinessError(settingsPayload);
      return;
    }
    setBusinessCreatePending(true);
    setBusinessError("");
    try {
      const created = await businessContext.createBusiness({
        name,
        description: businessDescription.trim() || null,
        task_concurrency_limit: concurrencyLimit,
      });
      if (settingsPayload) {
        await api.put<unknown>(
          "/settings/runner",
          settingsPayload,
          { "X-Business-Id": created.id },
        );
      }
      resetBusinessDialog();
      setCreateDialogOpen(false);
      setBusinessMenuOpen(false);
    } catch (error) {
      setBusinessError(error instanceof Error ? error.message : "创建业务失败");
    } finally {
      setBusinessCreatePending(false);
    }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主内容
      </a>
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <span className="sidebar-logo-mark">
              <LogoIcon />
            </span>
          </div>
          <div className="sidebar-brand">
            <span className="sidebar-brand-name">CUA</span>
            <span className="sidebar-brand-tag">自动化测试平台</span>
          </div>
          <div className="business-switcher" ref={businessSwitcherRef}>
            <button
              type="button"
              className="business-switcher-trigger"
              aria-label={`当前业务：${currentBusiness.name}`}
              aria-expanded={businessMenuOpen}
              onClick={() => setBusinessMenuOpen((open) => !open)}
            >
              <span>当前业务</span>
              <strong>{currentBusiness.name}</strong>
            </button>
            {businessMenuOpen && (
              <div className="business-switcher-menu" role="dialog" aria-label="业务空间">
                <div className="business-switcher-menu-head">
                  <span>业务空间</span>
                  <button
                    type="button"
                    onClick={() => {
                      resetBusinessDialog();
                      setCreateDialogOpen(true);
                    }}
                  >
                    新建业务
                  </button>
                </div>
                <div className="business-switcher-list">
                  {(businessContext?.businesses ?? [currentBusiness]).map((business) => (
                    <button
                      type="button"
                      key={business.id}
                      className={business.id === currentBusiness.id ? "active" : ""}
                      onClick={() => {
                        businessContext?.setCurrentBusinessId(business.id);
                        setBusinessMenuOpen(false);
                      }}
                    >
                      <span>{business.name}</span>
                      {business.is_default && <em>默认</em>}
                    </button>
                  ))}
                </div>
                {businessContext && (
                  <div className="business-switcher-actions">
                    <button
                      type="button"
                      onClick={openRenameDialog}
                    >
                      编辑
                    </button>
                    {!currentBusiness.is_default && (
                      <button
                        type="button"
                        className="danger"
                        onClick={() => {
                          void businessContext.archiveBusiness(currentBusiness.id);
                          setBusinessMenuOpen(false);
                        }}
                      >
                        停用
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <nav aria-label="主导航">
          {NAV_ITEMS.filter((item) => !item.adminOnly || user.role === "admin").map((item) => (
            <NavLink
              key={item.to}
              to={linkFor(item.to)}
              end={item.end}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <NavIcon path={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button
            type="button"
            className="sidebar-user"
            aria-label={`退出登录，当前用户 ${user.username}`}
            onClick={() => logout.mutate()}
          >
            <div className="sidebar-avatar">
              <UserInitials name={user.username} />
            </div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">{user.username}</div>
            </div>
            <span className="sidebar-user-logout" aria-hidden="true">
              <LogoutIcon />
            </span>
          </button>
        </div>
      </aside>

      {createDialogOpen && (
        <div className="business-modal-backdrop" role="presentation">
          <form
            className="business-modal"
            role="dialog"
            aria-modal="true"
            aria-label="新建业务空间"
            onSubmit={submitBusinessCreate}
          >
            <div className="business-modal-header">
              <div>
                <span>业务空间</span>
                <h2>新建业务空间</h2>
                <p>创建后会自动切换到该业务；默认执行配置可现在填写，也可以稍后在设置页补齐。</p>
              </div>
              <button
                type="button"
                aria-label="关闭新建业务空间弹窗"
                onClick={() => {
                  setCreateDialogOpen(false);
                  resetBusinessDialog();
                }}
              >
                ×
              </button>
            </div>

            <div className="business-modal-body">
              <section>
                <h3>业务信息</h3>
                <div className="business-modal-grid two">
                  <label>
                    <span className="required">业务名称</span>
                    <input
                      aria-label="业务名称"
                      aria-required="true"
                      value={businessName}
                      onChange={(event) => setBusinessName(event.target.value)}
                      placeholder="例如：支付业务"
                    />
                  </label>
                  <label>
                    <span>业务描述</span>
                    <input
                      aria-label="业务描述"
                      value={businessDescription}
                      onChange={(event) => setBusinessDescription(event.target.value)}
                      placeholder="可选"
                    />
                  </label>
                  <label>
                    <span className="required">任务并发上限</span>
                    <input
                      aria-label="任务并发上限"
                      aria-required="true"
                      type="number"
                      min={1}
                      max={8}
                      step={1}
                      value={businessConcurrencyLimit}
                      onChange={(event) => {
                        setBusinessConcurrencyLimit(event.target.value);
                        setBusinessError("");
                      }}
                    />
                  </label>
                </div>
              </section>

              <section>
                <h3>默认执行配置</h3>
                <div className="business-modal-grid">
                  <BusinessConfigInput
                    label="CUA AccountId"
                    required
                    value={businessConfig.account_id}
                    onChange={(value) => updateBusinessConfig("account_id", value)}
                  />
                  <BusinessConfigInput
                    label="Access Key ID"
                    required
                    value={businessConfig.access_key_id}
                    onChange={(value) => updateBusinessConfig("access_key_id", value)}
                  />
                  <BusinessConfigInput
                    label="Secret Access Key"
                    required
                    secret
                    value={businessConfig.secret_access_key}
                    onChange={(value) => updateBusinessConfig("secret_access_key", value)}
                  />
                  <BusinessConfigInput
                    label="TOS Bucket"
                    value={businessConfig.tos_bucket}
                    onChange={(value) => updateBusinessConfig("tos_bucket", value)}
                  />
                  <BusinessConfigInput
                    label="TOS Region"
                    value={businessConfig.tos_region}
                    onChange={(value) => updateBusinessConfig("tos_region", value)}
                  />
                  <BusinessConfigInput
                    label="任务超时 Timeout（秒）"
                    value={businessConfig.timeout_seconds}
                    onChange={(value) => updateBusinessConfig("timeout_seconds", value)}
                  />
                  <BusinessConfigInput
                    label="MaxStep"
                    value={businessConfig.max_step}
                    onChange={(value) => updateBusinessConfig("max_step", value)}
                  />
                  <label className="business-modal-wide">
                    <span>请求 Header（JSON 对象）</span>
                    <textarea
                      aria-label="请求 Header（JSON 对象）"
                      value={businessConfig.request_headers}
                      onChange={(event) => updateBusinessConfig("request_headers", event.target.value)}
                      placeholder='{"X-Env":"test"}'
                    />
                  </label>
                </div>
              </section>
            </div>

            {businessError && <p className="business-modal-error">{businessError}</p>}

            <div className="business-modal-footer">
              <button
                type="button"
                className="secondary-button"
                onClick={() => {
                  setCreateDialogOpen(false);
                  resetBusinessDialog();
                }}
              >
                取消
              </button>
              <button type="submit" className="primary-button" disabled={businessCreatePending}>
                {businessCreatePending ? "创建中..." : "创建业务"}
              </button>
            </div>
          </form>
        </div>
      )}

      {renameDialogOpen && (
        <div className="business-modal-backdrop" role="presentation">
          <form
            className="business-modal business-modal-compact"
            role="dialog"
            aria-modal="true"
            aria-label="编辑业务空间"
            onSubmit={submitBusinessRename}
          >
            <div className="business-modal-header">
              <div>
                <span>业务空间</span>
                <h2>编辑业务空间</h2>
                <p>修改后会影响左上角业务切换展示，历史执行仍保留创建时的业务快照。</p>
              </div>
              <button
                type="button"
                aria-label="关闭编辑业务空间弹窗"
                onClick={() => {
                  setRenameDialogOpen(false);
                  setRenameError("");
                }}
              >
                ×
              </button>
            </div>

            <div className="business-modal-body">
              <section>
                <div className="business-modal-grid">
                  <label>
                    <span className="required">业务名称</span>
                    <input
                      aria-label="业务名称"
                      aria-required="true"
                      value={renameName}
                      onChange={(event) => {
                        setRenameName(event.target.value);
                        setRenameError("");
                      }}
                      placeholder="业务名称"
                    />
                  </label>
                  <label>
                    <span>业务描述</span>
                    <input
                      aria-label="业务描述"
                      value={renameDescription}
                      onChange={(event) => {
                        setRenameDescription(event.target.value);
                        setRenameError("");
                      }}
                      placeholder="可选"
                    />
                  </label>
                  <label>
                    <span className="required">任务并发上限</span>
                    <input
                      aria-label="任务并发上限"
                      aria-required="true"
                      type="number"
                      min={1}
                      max={8}
                      step={1}
                      value={renameConcurrencyLimit}
                      onChange={(event) => {
                        setRenameConcurrencyLimit(event.target.value);
                        setRenameError("");
                      }}
                    />
                  </label>
                </div>
              </section>
            </div>

            {renameError && <p className="business-modal-error">{renameError}</p>}

            <div className="business-modal-footer">
              <button
                type="button"
                className="secondary-button"
                onClick={() => {
                  setRenameDialogOpen(false);
                  setRenameError("");
                }}
              >
                取消
              </button>
              <button type="submit" className="primary-button" disabled={renamePending}>
                {renamePending ? "保存中..." : "保存修改"}
              </button>
            </div>
          </form>
        </div>
      )}

      <main id="main-content" className="content" tabIndex={-1}>
        <div className="content-inner">{children}</div>
      </main>
    </div>
  );
}

function BusinessConfigInput({
  label,
  value,
  onChange,
  secret = false,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  secret?: boolean;
  required?: boolean;
}) {
  return (
    <label>
      <span className={required ? "required" : undefined}>{label}</span>
      <input
        aria-label={label}
        aria-required={required || undefined}
        type={secret ? "password" : "text"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function buildBusinessSettingsPayload(
  values: Record<BusinessConfigField, string>,
): BusinessRunnerSettingsUpdate | string {
  for (const field of ["account_id", "access_key_id", "secret_access_key"] as const) {
    if (!values[field].trim()) {
      return "默认执行配置必须完整：CUA AccountId、AK/SK 都必填。";
    }
  }

  const mobileUse: NonNullable<RunnerSettingsUpdate["mobile_use"]> = {
    account_id: values.account_id.trim(),
    access_key_id: values.access_key_id.trim(),
    secret_access_key: values.secret_access_key.trim(),
  };
  if (values.tos_bucket.trim()) {
    mobileUse.tos_bucket = values.tos_bucket.trim();
  }
  if (values.tos_region.trim()) {
    mobileUse.tos_region = values.tos_region.trim();
  }
  if (values.timeout_seconds.trim()) {
    mobileUse.timeout_seconds = Number(values.timeout_seconds.trim());
  }
  if (values.max_step.trim()) {
    mobileUse.max_step = Number(values.max_step.trim());
  }
  if (values.request_headers.trim()) {
    try {
      const parsed = JSON.parse(values.request_headers.trim());
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        return "请求 Header 必须是 JSON 对象。";
      }
      mobileUse.request_headers = parsed as Record<string, string>;
    } catch {
      return "请求 Header 不是合法 JSON。";
    }
  }
  return { mode: "mobile_use", mobile_use: mobileUse };
}
