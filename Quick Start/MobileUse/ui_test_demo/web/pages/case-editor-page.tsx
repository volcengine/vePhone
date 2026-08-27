import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useParams } from "react-router";
import { useEffect, useState } from "react";

import { ApiError, api } from "../api/client";
import { useBusinessNavigate } from "../business-context";
import type {
  CaseBoundTestPlan,
  CaseBoundTestPlanListResponse,
  ModuleListResponse,
  TagListResponse,
  Task,
  TestCase,
  TestCaseCreate,
} from "../api/types";
import { CaseExecutionRecords } from "../components/case-execution-records";
import { BusinessLink as Link } from "../components/business-link";
import { ConfirmDialog } from "../components/confirm-dialog";
import { ExecuteDialog, type ExecuteConfig } from "../components/execute-dialog";
import {
  buildExecuteConfig,
  createExecutionConfigDraft,
  createExecutionConfigDraftFromOptions,
  ExecutionConfigFields,
  type ExecutionConfigDraft,
} from "../components/execution-config-form";
import { PageHeader } from "../components/page-header";
import { PaginationControls } from "../components/pagination-controls";
import { formatChinaDateTime } from "../utils/time";

const BOUND_PLAN_PAGE_SIZE = 5;

const DEFAULT_TEMPLATE = `## 执行任务（必填）

> 用自然语言描述要完成的任务目标

示例：

- 打开抖音APP，查看3个视频。

---

## 用例通过标准（可选）

> 明确"什么情况下算通过"，用可验证的条件表述，方便 Agent 在结果中结构化输出。

建议按「必要条件」/「可选条件」描述：

- 必要条件（全部满足）：
  - 抖音APP已成功打开。
  - 抖音APP首页显示3个视频。
- 可选增强验证（满足越多，可信度越高）：
  - 抖音APP首页每个视频都有标题。

---

## 失败判定与错误场景（可选）

> 明确"什么情况下算失败"，并列出典型异常场景，方便 Agent 在 reason / content / struct_output 中给出有区分度的结论。

常见失败判定：

- 页面未能进入目标位置：
  - 抖音APP首页未显示3个视频。
- 异常弹窗与系统错误：
  - 出现"网络异常""系统错误""请求过于频繁"等弹窗；
  - App 崩溃或卡死在某个 loading 界面。

建议在本节中列出 2–3 个典型失败模式，比如：

- 失败场景 A：抖音APP首页显示的视频数量不是3个。
- 失败场景 B：点击视频后出现错误弹窗或黑屏。

---

## 前置条件 / 环境约束（可选）

> 记录对环境的显式要求，方便后续结合 AospVersion/ImageName/ImageId、pod_id 等字段排查问题。

示例：

- 设备 / 镜像要求：
  - AospVersion 要求：Android 13；
  - ImageName 推荐：最新公共镜像版本或自定义镜像版本。
- 网络：
  - 正常外网访问。

---

## 调试备注（可选）

> 用于给未来的自己或同事一点"使用说明"，常见包括：

- 如果经常失败在同一个步骤，可以写明如何人工复现。
- 如果某些弹窗经常挡住关键控件，可以备注：
  - 例如："如出现隐私弹窗，请先点击'同意/允许'，再继续后续步骤。"
`;

function SaveIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" /><polyline points="17 21 17 13 7 13 7 21" /><polyline points="7 3 7 8 15 8" />
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

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

export function CaseEditorPage() {
  const navigate = useBusinessNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { caseId } = useParams<{ caseId: string }>();
  const isNew = location.pathname.endsWith("/cases/new");
  const existingId = isNew ? null : caseId;

  const [title, setTitle] = useState("");
  const [module, setModule] = useState("");
  const [contentMarkdown, setContentMarkdown] = useState(DEFAULT_TEMPLATE);
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [execDialogOpen, setExecDialogOpen] = useState(false);
  const [savedCaseId, setSavedCaseId] = useState<string | null>(null);
  const [defaultConfigEnabled, setDefaultConfigEnabled] = useState(false);
  const [defaultConfigDialogOpen, setDefaultConfigDialogOpen] = useState(false);
  const [removePlanTarget, setRemovePlanTarget] = useState<CaseBoundTestPlan | null>(null);
  const [boundPlanError, setBoundPlanError] = useState("");
  const [boundPlanPage, setBoundPlanPage] = useState(1);
  const [defaultConfigDraft, setDefaultConfigDraft] =
    useState<ExecutionConfigDraft>(() => ({
      ...createExecutionConfigDraft(),
      agent_config_mode: "custom",
    }));

  const existingCase = useQuery({
    queryKey: ["case-detail", existingId],
    queryFn: () => api.get<TestCase>(`/cases/${existingId}`),
    enabled: !isNew && !!existingId,
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

  const boundPlansQuery = useQuery({
    queryKey: ["case-bound-test-plans", existingId, boundPlanPage],
    queryFn: () =>
      api.get<CaseBoundTestPlanListResponse>(
        `/cases/${existingId}/test-plans?page=${boundPlanPage}&page_size=${BOUND_PLAN_PAGE_SIZE}`,
      ),
    enabled: !isNew && Boolean(existingId),
  });

  useEffect(() => {
    if (existingCase.data) {
      setTitle(existingCase.data.title);
      setModule(existingCase.data.module || "");
      setContentMarkdown(existingCase.data.content_markdown);
      setTags(existingCase.data.tags);
      setDefaultConfigEnabled(Boolean(existingCase.data.default_agent_options));
      setDefaultConfigDraft(
        createExecutionConfigDraftFromOptions(
          existingCase.data.default_agent_options,
        ),
      );
    }
  }, [existingCase.data]);

  const templateQuery = useQuery({
    queryKey: ["case-template"],
    queryFn: () => api.get<{ template: string }>("/cases/template"),
    enabled: isNew,
  });

  useEffect(() => {
    if (isNew && templateQuery.data?.template) {
      setContentMarkdown(templateQuery.data.template);
    }
  }, [isNew, templateQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async (payload: TestCaseCreate) => {
      if (isNew) {
        return api.post<TestCase>("/cases", payload);
      }
      return api.put<TestCase>(`/cases/${existingId}`, payload);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      queryClient.setQueryData(["case-detail", data.id], data);
      queryClient.invalidateQueries({ queryKey: ["case-detail", data.id] });
      queryClient.invalidateQueries({ queryKey: ["case-tags"] });
      queryClient.invalidateQueries({ queryKey: ["case-modules"] });
      navigate(`/cases/${data.id}/edit`);
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("保存失败");
      }
    },
  });

  const executeMutation = useMutation({
    mutationFn: async ({ cid, config }: { cid: string; config: ExecuteConfig }) => {
      return api.post<Task>(`/cases/${cid}/execute`, {
        idempotency_key: `exec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        pod_id: config.pod_id,
        timeout_seconds: config.timeout_seconds,
        agent_config_mode: config.agent_config_mode,
        agent_options: config.agent_options,
      });
    },
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      void queryClient.invalidateQueries({ queryKey: ["case-detail", data.case_id] });
      void queryClient.invalidateQueries({ queryKey: ["case-tasks", data.case_id] });
      void queryClient.invalidateQueries({ queryKey: ["pod-pool"] });
      setExecDialogOpen(false);
      navigate(`/tasks/${data.id}`);
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setError(`执行失败：${err.message}`);
      }
    },
  });

  const removePlanCaseMutation = useMutation({
    mutationFn: (planId: string) =>
      api.delete(`/test-plans/${planId}/cases/${existingId}`),
    onMutate: () => {
      setBoundPlanError("");
    },
    onSuccess: (_data, planId) => {
      setRemovePlanTarget(null);
      void queryClient.invalidateQueries({
        queryKey: ["case-bound-test-plans", existingId],
      });
      void queryClient.invalidateQueries({ queryKey: ["test-plans"] });
      void queryClient.invalidateQueries({ queryKey: ["test-plan", planId] });
      void queryClient.invalidateQueries({ queryKey: ["test-plan-cases", planId] });
    },
    onError: (error) => {
      setBoundPlanError(
        error instanceof ApiError
          ? casePlanRemoveMessage(error.code)
          : "移除失败，请稍后重试。",
      );
    },
  });

  function addTag() {
    const t = tagInput.trim();
    if (!t) return;
    if (tags.includes(t)) {
      setTagInput("");
      return;
    }
    setTags([...tags, t]);
    setTagInput("");
  }

  function removeTag(t: string) {
    setTags(tags.filter((x) => x !== t));
  }

  function handleSave() {
    setError(null);
    if (!title.trim()) {
      setError("请输入用例名称");
      return;
    }
    if (!contentMarkdown.trim()) {
      setError("请输入用例内容");
      return;
    }
    const defaultOptions = buildDefaultAgentOptions();
    if (defaultOptions === false) return;
    const payload: TestCaseCreate = {
      title: title.trim(),
      module: module.trim() || null,
      content_markdown: contentMarkdown,
      tags,
      automation_level: "auto",
      default_agent_options: defaultOptions,
    };
    saveMutation.mutate(payload);
  }

  function handleSaveAndExecute() {
    if (!title.trim() || !contentMarkdown.trim()) {
      setError("请填写用例名称和内容后再执行");
      return;
    }
    const defaultOptions = buildDefaultAgentOptions();
    if (defaultOptions === false) return;
    const payload: TestCaseCreate = {
      title: title.trim(),
      module: module.trim() || null,
      content_markdown: contentMarkdown,
      tags,
      automation_level: "auto",
      default_agent_options: defaultOptions,
    };
    saveMutation.mutate(payload, {
      onSuccess: (data) => {
        setSavedCaseId(data.id);
        setExecDialogOpen(true);
      },
    });
  }

  function handleExecuteConfirm(config: ExecuteConfig) {
    const cid = savedCaseId || existingId;
    if (cid) {
      executeMutation.mutate({ cid, config });
    }
  }

  function enableDefaultConfig() {
    setDefaultConfigEnabled(true);
    setDefaultConfigDialogOpen(true);
  }

  const defaultSummary = {
    threadId: defaultConfigDraft.custom.thread_id.trim() || "自动生成",
    maxStep: defaultConfigDraft.custom.max_step,
    timeout: `${defaultConfigDraft.custom.timeout_seconds}s`,
    retry: defaultConfigDraft.custom.retry_limit,
    screenRecord: defaultConfigDraft.custom.screen_record,
    base64: defaultConfigDraft.custom.use_base64_screenshot,
    tos: Boolean(
      defaultConfigDraft.custom.tos_bucket.trim()
      || defaultConfigDraft.custom.tos_endpoint.trim(),
    ),
    mcp: Boolean(defaultConfigDraft.custom.mcp_json.trim()),
  };

  function buildDefaultAgentOptions() {
    if (!defaultConfigEnabled) return null;
    const result = buildExecuteConfig({
      ...defaultConfigDraft,
      agent_config_mode: "custom",
    });
    if (!result.config?.agent_options) {
      setError(result.error || "默认执行配置不完整");
      return false;
    }
    return result.config.agent_options;
  }

  if (!isNew && existingCase.isLoading) {
    return <div className="page-container case-editor-page"><div className="empty-state">加载中...</div></div>;
  }

  if (!isNew && existingCase.isError) {
    return (
      <div className="page-container case-editor-page">
        <div className="empty-state error">
          加载失败：{existingCase.error instanceof ApiError ? existingCase.error.message : "未知错误"}
          <Link to="/cases" className="secondary-button" style={{ marginTop: 12 }}>返回用例库</Link>
        </div>
      </div>
    );
  }

  const suggestedTags = (tagsQuery.data?.items || []).filter((t) => !tags.includes(t));

  return (
    <div className="page-container case-editor-page">
      <PageHeader
        breadcrumbs={[
          { label: "首页", to: "/tasks" },
          { label: "用例库", to: "/cases" },
          { label: isNew ? "新建用例" : "编辑用例" },
        ]}
        title={isNew ? "新建用例" : "编辑用例"}
        description="使用 Markdown 编写测试用例，支持执行任务、通过标准、失败判定等章节"
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <Link to="/cases" className="secondary-button">
              <span>取消</span>
            </Link>
            {!isNew && (
              <button
                type="button"
                className="secondary-button"
                onClick={() => { setSavedCaseId(existingId ?? null); setError(null); setExecDialogOpen(true); }}
                disabled={executeMutation.isPending || saveMutation.isPending}
              >
                <PlayIcon />
                <span>执行</span>
              </button>
            )}
            <button
              type="button"
              className="primary-button"
              onClick={handleSave}
              disabled={saveMutation.isPending}
            >
              <SaveIcon />
              <span>{saveMutation.isPending ? "保存中..." : "保存"}</span>
            </button>
            {isNew && (
              <button
                type="button"
                className="primary-button"
                style={{ backgroundColor: "var(--state-success)" }}
                onClick={handleSaveAndExecute}
                disabled={saveMutation.isPending || executeMutation.isPending}
              >
                <PlayIcon />
                <span>保存并执行</span>
              </button>
            )}
          </div>
        }
      />

      <div className="page-content">
        {error && (
          <div className="error-banner">{error}</div>
        )}

        <div className="editor-layout">
          <div className="editor-main">
            <div className="form-card">
              <div className="form-group">
                <label className="form-label">用例名称 <span className="required">*</span></label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="例如：打开抖音APP查看3个视频"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={200}
                />
              </div>

              <div className="form-row case-metadata-row">
                <div className="form-group" style={{ flex: 1 }}>
                  <label className="form-label">所属模块</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="例如：登录注册、首页、商品"
                    value={module}
                    onChange={(e) => setModule(e.target.value)}
                    maxLength={100}
                    list="module-suggestions"
                  />
                  <datalist id="module-suggestions">
                    {Array.from(new Set([module, ...(modulesQuery.data?.items || [])])).slice(0, 10).map((m) => (
                      <option key={m} value={m} />
                    ))}
                  </datalist>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">标签</label>
                <div className="tag-input-area">
                  <div className="tag-list editable">
                    {tags.map((t) => (
                      <span key={t} className="tag tag-primary tag-removable">
                        {t}
                        <button type="button" onClick={() => removeTag(t)} aria-label={`移除标签 ${t}`}>
                          <XIcon />
                        </button>
                      </span>
                    ))}
                    <input
                      type="text"
                      className="tag-text-input"
                      placeholder={tags.length === 0 ? "输入标签后按回车添加" : ""}
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === ",") {
                          e.preventDefault();
                          addTag();
                        }
                        if (e.key === "Backspace" && !tagInput && tags.length > 0) {
                          setTags(tags.slice(0, -1));
                        }
                      }}
                      onBlur={addTag}
                    />
                  </div>
                </div>
                {suggestedTags.length > 0 && (
                  <div className="tag-suggestions">
                    <span style={{ fontSize: "0.75rem", color: "var(--mua-neutral-500)", marginRight: 4 }}>常用标签：</span>
                    {suggestedTags.slice(0, 8).map((t) => (
                      <button key={t} type="button" className="tag-suggestion" onClick={() => { if (!tags.includes(t)) setTags([...tags, t]); }}>
                        {t}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="form-card">
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">用例内容（Markdown） <span className="required">*</span></label>
                <textarea
                  className="form-textarea markdown-editor"
                  value={contentMarkdown}
                  onChange={(e) => setContentMarkdown(e.target.value)}
                  placeholder="使用 Markdown 格式编写测试用例..."
                  spellCheck={false}
                />
              </div>
            </div>
          </div>

          <div className="editor-sidebar">
            <div className="form-card">
              <div className="sidebar-section-title">用例结构说明</div>
              <div className="help-list">
                <div className="help-item">
                  <code>## 执行任务（必填）</code>
                  <p>自然语言描述任务目标</p>
                </div>
                <div className="help-item">
                  <code>## 用例通过标准（可选）</code>
                  <p>可验证的通过条件，必要/可选</p>
                </div>
                <div className="help-item">
                  <code>## 失败判定与错误场景（可选）</code>
                  <p>典型失败模式和异常场景</p>
                </div>
                <div className="help-item">
                  <code>## 前置条件/环境约束（可选）</code>
                  <p>设备、镜像、网络等要求</p>
                </div>
                <div className="help-item">
                  <code>## 调试备注（可选）</code>
                  <p>人工复现提示、弹窗处理等</p>
                </div>
              </div>
            </div>

            {!isNew && existingCase.data && (
              <>
              <div className="form-card case-default-config-card">
                <div className="case-default-config-head">
                  <div>
                    <div className="sidebar-section-title">
                      用例默认执行配置
                    </div>
                    <p className="muted">
                      复用当前用例的 Agent 参数。
                    </p>
                  </div>
                  <div className="case-default-config-actions">
                    <span className={`case-default-status${
                      defaultConfigEnabled ? " on" : ""
                    }`}>
                      {defaultConfigEnabled ? "已启用" : "未启用"}
                    </span>
                    {defaultConfigEnabled && (
                      <button
                        type="button"
                        className="case-default-disable-button"
                        onClick={() => setDefaultConfigEnabled(false)}
                      >
                        关闭配置
                      </button>
                    )}
                  </div>
                </div>
                {defaultConfigEnabled ? (
                  <div className="case-default-summary">
                    <div className="case-default-summary-line">
                      <span>ThreadId</span>
                      <strong title={defaultSummary.threadId}>
                        {defaultSummary.threadId}
                      </strong>
                    </div>
                    <div className="case-default-metrics">
                      <div>
                        <span>MaxStep</span>
                        <strong>{defaultSummary.maxStep}</strong>
                      </div>
                      <div>
                        <span>Timeout</span>
                        <strong>{defaultSummary.timeout}</strong>
                      </div>
                      <div>
                        <span>Retry</span>
                        <strong>{defaultSummary.retry}</strong>
                      </div>
                    </div>
                    <div className="case-default-chip-row">
                      <span className={defaultSummary.screenRecord ? "on" : ""}>
                        录屏
                      </span>
                      <span className={defaultSummary.base64 ? "on" : ""}>
                        Base64
                      </span>
                      <span className={defaultSummary.tos ? "on" : ""}>
                        TOS
                      </span>
                      <span className={defaultSummary.mcp ? "on" : ""}>
                        MCP
                      </span>
                    </div>
                    <button
                      type="button"
                      className="case-default-edit-button"
                      onClick={() => setDefaultConfigDialogOpen(true)}
                    >
                      编辑默认配置
                    </button>
                  </div>
                ) : (
                  <div className="case-default-empty">
                    <span>未启用默认配置，执行时使用全局或临时配置。</span>
                    <button
                      type="button"
                      className="case-default-edit-button"
                      onClick={enableDefaultConfig}
                    >
                      启用配置
                    </button>
                  </div>
                )}
              </div>
              <div className="form-card">
                <div className="sidebar-section-title">执行统计</div>
                <div className="stats-grid">
                  <div className="stat-item">
                    <div className="stat-value">{existingCase.data.execution_count}</div>
                    <div className="stat-label">总执行次数</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-value" style={{ color: "var(--state-success-fg)" }}>{existingCase.data.pass_count}</div>
                    <div className="stat-label">通过</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-value" style={{ color: "var(--state-error-fg)" }}>{existingCase.data.fail_count}</div>
                    <div className="stat-label">失败</div>
                  </div>
                </div>
                {existingCase.data.last_executed_at && (
                  <div className="stat-meta">最近执行：{formatChinaDateTime(existingCase.data.last_executed_at)}</div>
                )}
                <div className="stat-meta">创建人：{existingCase.data.created_by}</div>
                <div className="stat-meta">创建时间：{formatChinaDateTime(existingCase.data.created_at)}</div>
                <div className="stat-meta">更新时间：{formatChinaDateTime(existingCase.data.updated_at)}</div>
                <div className="stat-meta monospace" style={{ fontSize: "0.7rem", color: "var(--mua-neutral-400)" }}>ID: {existingCase.data.id}</div>
              </div>
              </>
            )}
          </div>
        </div>

        {!isNew && existingId && (
          <>
            <section
              className="form-card case-bound-plans-card"
              aria-label="已绑定测试计划"
            >
              <div className="case-bound-plans-head">
                <div>
                  <div className="sidebar-section-title">已绑定测试计划</div>
                  <p className="muted">
                    {boundPlansQuery.isLoading
                      ? "正在加载绑定关系..."
                      : (boundPlansQuery.data?.total ?? 0) > 0
                        ? `该用例被 ${boundPlansQuery.data?.total ?? 0} 个有效测试计划引用。`
                        : "暂无绑定测试计划"}
                  </p>
                </div>
              </div>
              {boundPlansQuery.isError ? (
                <div className="exec-records-empty error">
                  加载失败：{boundPlansQuery.error instanceof ApiError ? boundPlansQuery.error.message : "未知错误"}
                </div>
              ) : !boundPlansQuery.isLoading && (boundPlansQuery.data?.total ?? 0) > 0 ? (
                <div className="case-bound-plan-list">
                  {boundPlansQuery.data?.items.map((plan) => (
                    <div className="case-bound-plan-item" key={plan.id}>
                      <div className="case-bound-plan-main">
                        <Link to={`/test-plans/${plan.id}`} className="case-bound-plan-name">
                          {plan.name}
                        </Link>
                        <div className="case-bound-plan-meta">
                          <span>{testTypeLabel(plan.test_type)}</span>
                          <span>{plan.case_count} 个用例</span>
                          <span className={`badge-tag ${plan.has_active_execution ? "warning" : "success"}`}>
                            {plan.has_active_execution ? "执行中" : "空闲"}
                          </span>
                        </div>
                      </div>
                      <div className="case-bound-plan-actions">
                        <Link to={`/test-plans/${plan.id}`} className="text-button">查看</Link>
                        <button
                          type="button"
                          className="text-button danger"
                          aria-label={`移除 ${plan.name}`}
                          title={plan.has_active_execution ? "计划正在执行中，结束后才可移除用例" : undefined}
                          disabled={plan.has_active_execution}
                          onClick={() => {
                            setBoundPlanError("");
                            setRemovePlanTarget(plan);
                          }}
                        >
                          移除
                        </button>
                      </div>
                    </div>
                  ))}
                  {(boundPlansQuery.data?.total ?? 0) > BOUND_PLAN_PAGE_SIZE && (
                    <PaginationControls
                      page={boundPlanPage}
                      pageSize={BOUND_PLAN_PAGE_SIZE}
                      total={boundPlansQuery.data?.total ?? 0}
                      onPageChange={setBoundPlanPage}
                      onPageSizeChange={() => setBoundPlanPage(1)}
                      showPageSize={false}
                    />
                  )}
                </div>
              ) : null}
            </section>
            <CaseExecutionRecords caseId={existingId} />
          </>
        )}
      </div>

      <ExecuteDialog
        open={execDialogOpen}
        caseTitle={title || "新建用例"}
        onClose={() => { setExecDialogOpen(false); setError(null); }}
        onConfirm={handleExecuteConfirm}
        isPending={executeMutation.isPending}
        allowCaseDefault={Boolean(existingCase.data?.default_agent_options)}
      />
      {defaultConfigDialogOpen && (
        <div className="modal-overlay">
          <div
            className="modal-panel case-default-config-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="编辑用例默认执行配置"
          >
            <div className="modal-header">
              <h3>编辑用例默认执行配置</h3>
              <button
                type="button"
                className="icon-action"
                aria-label="关闭"
                onClick={() => setDefaultConfigDialogOpen(false)}
              >
                <XIcon />
              </button>
            </div>
            <div className="modal-body">
              <ExecutionConfigFields
                value={defaultConfigDraft}
                onChange={setDefaultConfigDraft}
                idPrefix="case-default"
                showModeSelector={false}
              />
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="primary-button"
                onClick={() => setDefaultConfigDialogOpen(false)}
              >
                完成
              </button>
            </div>
          </div>
        </div>
      )}
      <ConfirmDialog
        open={removePlanTarget !== null}
        title="从测试计划中移除用例"
        description={removePlanTarget
          ? `确认将「${title || existingCase.data?.title || "当前用例"}」从「${removePlanTarget.name}」中移除？这不会删除用例，也不会删除测试计划。`
          : ""}
        confirmLabel="确认移除"
        pendingLabel="移除中..."
        isPending={removePlanCaseMutation.isPending}
        errorMessage={boundPlanError}
        onClose={() => {
          setRemovePlanTarget(null);
          setBoundPlanError("");
        }}
        onConfirm={() => {
          if (removePlanTarget) removePlanCaseMutation.mutate(removePlanTarget.id);
        }}
      />
    </div>
  );
}

function testTypeLabel(value: string): string {
  return value === "new_feature" ? "新功能" : "回归测试";
}

function casePlanRemoveMessage(code: string): string {
  if (code === "test_plan_execution_active") return "计划正在执行中，结束后才可移除用例。";
  if (code === "test_plan_requires_one_case") return "测试计划至少需要保留 1 个用例。";
  if (code === "case_not_in_test_plan") return "该用例已不在此测试计划中。";
  if (code === "test_plan_not_found") return "测试计划不存在或已删除。";
  return "移除失败，请稍后重试。";
}
