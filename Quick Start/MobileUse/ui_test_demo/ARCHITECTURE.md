# MUA 自动化测试平台架构说明

本文档说明 MUA 自动化测试平台的系统边界、模块分层、核心数据流和运行时约束。面向需要二次开发、排障或小包交付维护的工程人员。

## 设计目标

- 本地优先：单机即可运行，不依赖外部数据库或队列。
- 真实设备执行：Mobile Use Runner 负责远端任务创建、轮询、取消和结果收敛。
- 结果可追溯：任务事件、步骤、Trace、Runner 配置快照和报告都持久化。
- 秘密最小暴露：真实凭证加密保存，接口和页面不回显敏感值。

## 总体架构

```text
Browser
  |
  | HTTP / JSON / Cookie + CSRF
  v
FastAPI app
  |
  | routers
  v
Domain services
  |
  | repositories
  v
SQLite in APP_DATA_DIR

FastAPI lifespan
  |
  +-- TaskWorker
  +-- BatchScheduler loop
  +-- SPA static file serving

RunnerAdapter
  |
  +-- MobileUseRunner -> UniversalGateway -> Mobile Use remote APIs
```

当前部署边界是单租户、单实例、SQLite。Pod 租约只保证单实例内互斥，不是分布式锁。

## 前端分层

前端位于 `web/`，使用 React 19、React Router、TanStack Query 和 Vite。

- `web/app.tsx`：路由、登录态门禁和页面懒加载。
- `web/api/client.ts`：统一 API 请求、CSRF、未授权订阅。
- `web/api/types.ts`：前后端 API 契约类型。
- `web/pages/`：页面级容器，例如任务、用例、测试计划、设置、Pod 池和报告。
- `web/components/`：跨页面复用组件，例如执行配置表单、分页、状态徽标、运行配置快照。
- `web/utils/`：时间、主题、任务状态等纯工具逻辑。

前端不保存真实凭证。Secret 输入框为空表示保留已保存值，页面只展示配置状态或脱敏提示。

## 后端分层

后端位于 `src/mua_platform/`，入口是 `mua_platform.main:create_app`。

- `api/`：FastAPI router 层，负责请求校验、调用服务、返回 schema。
- `auth/`：首个管理员初始化、多用户登录、角色权限、会话、CSRF 和登录限流。
- `cases/`：测试用例模型、导入、统计和用例默认 Agent 配置。
- `test_plans/`：测试计划、用例编排、计划执行和报告快照。
- `tasks/`：任务模型、状态机、仓储、批次调度、执行配置和 Worker。
- `runners/`：Runner 抽象、Mobile Use Runner、远端结果解析和 Universal API gateway。
- `pods/`：Pod 发现、可用性判断、分配、冷却和本地租约。
- `settings/`：Runner 设置、加密存储、审计和运行配置 schema。
- `traces/`：任务 Trace span 的持久化与查询。
- `diagnostics/`：Runner 和远端服务诊断。

推荐保持 router 较薄，把业务规则放在 service、repository 或 runner 层。

## 数据存储

默认数据目录由 `APP_DATA_DIR` 指定，SQLite 数据库位于该目录下。未配置 `APP_SECRET_KEY` 时，系统会生成 `secret.key` 并写入同一数据目录。

核心表按领域划分：

- 认证：`users`、`auth_sessions`。
- 设置：`settings`，保存加密后的 Runner 配置。
- 用例：`test_cases`。
- 测试计划：`test_plans`、`test_plan_cases`、`plan_executions`。
- 任务：`tasks`、`task_batches`、`task_runner_configs`、`task_events`、`task_steps`。
- Pod：`discovered_pods`、`pod_pool_refreshes`、`pod_leases`。
- Trace：`task_trace_spans`。
- 可复用脚本：`reusable_scripts` 相关表。

任务创建时会写入 Runner 配置快照。后续修改全局设置不会改变历史任务或历史报告。

## 任务生命周期

任务状态由 `tasks/state_machine.py` 约束：

```text
script_pending -> queued
queued -> running
queued -> result_ready
queued -> cancelled
running -> result_ready
running -> cancelled
```

终态：

- `result_ready`：必须带 `pass` 或 `fail` verdict。
- `cancelled`：不带 verdict。

任务执行路径：

1. 页面创建单任务或测试计划执行。
2. 后端写入任务、批次、配置快照和幂等键。
3. `BatchScheduler` 把满足条件的 queued 任务推给 `TaskWorker`。
4. `TaskWorker` 根据任务的 `runner_type` 创建 Runner。
5. 远端启动前，任务先从 `start_state=pending` 原子切换为 `dispatching`。
6. 远端返回 RunId 后，任务切换为 `start_state=attached`，后续只能通过原 `remote_run_id` 轮询或取消。
7. Runner 产生事件，`TaskService` 将事件收敛为任务状态、步骤、结果、资产和 Trace。
8. 前端通过任务详情、报告和 Trace 页面读取持久化结果。

证据不足、结构化输出非法、must 断言缺失或自然语言成功描述都不能生成通过结论。

服务收到 `SIGTERM` 后进入 draining：readiness 返回未就绪，scheduler 不再分配新任务，Worker 最多等待 `TASK_WORKER_DRAIN_TIMEOUT_SECONDS` 秒。排空超时只取消本地协程；已保存 `remote_run_id` 的远端任务保持 `running`，由新进程启动后恢复轮询。

如果任务处于 `dispatching` 且没有 RunId，系统认为远端启动结果未知，终结为 `start_outcome_unknown` 并保留隔离租约，避免静默重复提交远端任务。

## Runner 抽象

`runners/base.py` 定义 `RunnerAdapter` 协议：

- `validate(config)`：校验 Runner 配置。
- `list_pods(config)`：获取设备诊断信息。
- `start(request, idempotency_key)`：启动远端或本地执行，返回 `RunHandle`。
- `poll(handle, after_sequence)`：轮询增量事件。
- `cancel(handle)`：请求取消。
- `run(request)`：流式执行接口。

### Mobile Use Runner

Mobile Use Runner 会将用例内容渲染为远端 Agent prompt，并通过 Universal Gateway 调用远端 API：

```text
RunAgentTaskOneStep -> ListAgentRunCurrentStep -> GetAgentResult
```

关键约束：

- 启动和取消 POST 不做盲目重放。
- GET 轮询只做有界重试。
- 远端 `Status=3` 和 `Status=6` 均视为终态，需要触发本地结果收敛。
- 结果资产和截图必须按 `remote_run_id` 过滤，不能只按 `ThreadID` 查询。
- 只持久化清洗后的结构化字段，不保存真实凭证或原始敏感响应。

## Pod 分配

Pod 模块负责把真实设备执行从“配置问题”变成“任务调度问题”。

1. `PodGateway` 通过远端 `ListPod` 拉取设备。
2. `pods/service.py` 将设备写入 `discovered_pods`，并记录 last seen、状态、冷却等信息。
3. 创建任务时根据设备策略选择 Pod。
4. 执行前通过本地 `pod_leases` 做单实例互斥。
5. 任务终态、取消、中断或安全的启动重排时释放租约。
6. 启动结果未知时不释放租约，而是延长为隔离租约，直到可能的远端执行窗口结束。

该机制不提供云机启停、重建或多实例 fencing。

## 测试计划执行

测试计划是用例集合和执行策略的组合：

1. `test_plans` 保存计划基础信息。
2. `test_plan_cases` 保存计划内用例顺序。
3. 发起运行时创建 `task_batches` 和一组 `tasks`。
4. `plan_executions` 保存计划名、标签、用例列表、设备策略、并发、Runner 类型和配置快照。
5. 报告页面基于 `plan_executions`、批次任务和任务结果汇总展示。

计划执行使用快照，保证报告不受后续计划编辑影响。

## 安全边界

- `APP_SECRET_KEY` 用于派生设置加密密钥，必须随数据备份并保持稳定。
- `settings` 表只保存加密值。
- Secret 字段不回显，空输入表示保留原值。
- API 错误使用结构化错误，不应泄露原始异常、远端响应体或凭证。
- Trace 和报告只保存安全结构化字段。
- `.env`、`data/`、`app.db`、截图和临时真实执行脚本不应进入交付包或公开副本。

## 运行时边界

当前架构刻意保持简单：

- 单租户。
- 单 FastAPI 进程。
- 单 SQLite 数据库。
- 后端内置 asyncio Worker。
- 无外部消息队列。
- 无分布式锁。
- 无多实例任务 fencing。

需要横向扩展时，应优先重新设计任务领取、Pod 租约、调度和数据库层，而不是直接启动多个进程共享同一个 SQLite 数据库。

## 关键验证命令

```bash
make test
npm run build
make e2e
```

涉及具体模块时，优先先跑最小相关测试，再扩大到上述命令。
