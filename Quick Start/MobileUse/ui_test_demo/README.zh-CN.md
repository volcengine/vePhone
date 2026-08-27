# MUA 自动化测试平台

[English](README.md) | [简体中文](README.zh-CN.md)

MUA 自动化测试平台是一个本地优先的 Web 控制台，用于管理移动端 UI 自动化用例、执行任务、设备分配、运行 Trace 和测试计划报告。真实设备执行由 Mobile Use Runner 负责，并从已配置的 Pod 池中分配设备。

## 功能特性

- 用例库：创建、编辑、导入和复用移动端 UI 测试用例。
- 支持单用例执行和测试计划执行，并可为每次运行配置 Agent 参数。
- Mobile Use Runner 集成：支持真实设备执行、步骤轮询、取消、结果收敛、截图和用量元数据。
- Pod 池发现、分配快照、本地租约和任务设备同步。
- 任务列表、任务详情、运行面板、Trace 视图和结构化报告。
- 可从已完成的通过/失败任务中沉淀可复用脚本。
- 首个管理员初始化、多用户登录、CSRF 防护和加密 Runner 设置。
- 基于 SQLite 持久化，并支持启动后恢复排队中和运行中的任务。

## 技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy、SQLite、Pydantic、uvicorn。
- 前端：React 19、React Router、TanStack Query、Vite、TypeScript。
- 测试：pytest、Vitest、Playwright。
- 包管理：Python 使用 uv，前端使用 npm。

## 快速开始

前置要求：

- Python 3.12
- uv
- Node.js 22
- npm

安装依赖并启动应用：

```bash
uv sync
npm ci
make dev
```

打开 `http://127.0.0.1:8000`，创建第一个管理员账号，然后配置 Runner 并创建用例。默认情况下，本地数据会存储在 `./data`。如果没有提供 `APP_SECRET_KEY`，后端会自动创建 `data/secret.key`。

进行前端开发并需要热更新时，可以分别启动后端和 Vite：

```bash
uv run uvicorn mua_platform.main:app --reload
npm run dev
```

Vite 会将 `/api` 和 `/health` 代理到 `http://localhost:8000`。

## 配置

应用从环境变量和可选的 `.env` 文件读取配置。可以参考 `.env.example`，但不要提交真实密钥。

常用变量说明：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `development` | 应用运行模式。自己电脑调试可用 `development`；交付给客户或长期运行建议用 `production`。 |
| `APP_DATA_DIR` | `./data` | 数据保存目录。数据库、自动生成的密钥文件都放在这里。备份和迁移时，优先备份这个目录。 |
| `APP_SECRET_KEY` | 在 `APP_DATA_DIR` 中自动生成 | 应用加密密钥，用来保护已保存的 Runner 密钥配置。首次部署后不要随意更换，否则旧配置可能无法解密。 |
| `APP_BASE_URL` | `http://localhost:8000` | 用户访问系统的后端地址。只在服务端口、域名或反向代理地址变化时需要改。 |
| `REQUEST_MAX_BYTES` | `1048576` | 单次请求允许的最大体积。一般不用改；导入内容特别大时再调大。 |
| `TASK_EXECUTION_TIMEOUT_SECONDS` | `600` | 单个任务最多运行多久，单位秒。超过后系统会按超时处理。 |
| `CANCEL_CONFIRM_TIMEOUT_SECONDS` | `30` | 点击取消后，系统等待远端确认取消的最长时间，单位秒。 |
| `DEVICE_WAIT_TIMEOUT_SECONDS` | `300` | 指定设备离线、失联或被删除时，任务最多等待多久后失败，单位秒。 |
| `TASK_WORKER_CONCURRENCY` | `16` | 后端 Worker 的全局最大并发数。它是系统层面的上限，不等同于业务空间上限或某次执行填写的设备并发数。 |

需要真实设备执行时，可以在设置页面配置 Runner，或使用 `.env.example` 中列出的 `MOBILE_USE_*` 变量。

真实设备相关配置说明：

| 配置项 | 是否必填 | 通俗说明 |
| --- | --- | --- |
| `MOBILE_USE_ACCESS_KEY_ID` / Access Key ID | 是 | 访问云端 Mobile Use 服务的账号标识。可以理解为“用户名”。 |
| `MOBILE_USE_SECRET_ACCESS_KEY` / Secret Access Key | 是 | 和 Access Key ID 配套的密钥。可以理解为“密码”，不要截图、发群或提交到代码仓库。 |
| `MOBILE_USE_PRODUCT_ID` / Product ID | 是 | 设备池所属的产品 ID。系统会根据它去发现可用设备。 |
| `ThreadId` | 否 | 远端任务会话 ID。通常留空，系统会自动生成；只有需要把多次执行放到同一个远端会话下时才手动填写。它是单次执行/用例默认配置项，不是 `.env.example` 中的环境变量。 |
| `MOBILE_USE_TOS_BUCKET` / TOS Bucket | 是 | 存放截图、录屏或执行产物的对象存储桶名称。 |
| `MOBILE_USE_TOS_REGION` / TOS Region | 是 | TOS Bucket 所在地域，例如 `cn-beijing`。填错会导致产物上传或访问失败。 |
| `MOBILE_USE_TOS_ENDPOINT` / TOS Endpoint | 否 | TOS 服务访问地址。通常按地域自动生成；只有存储服务有特殊地址时才需要填写。 |
| `MOBILE_USE_POD_ID` / Pod ID | 否 | 固定使用某一台设备。不填时，系统会从 Pod 池自动分配。 |
| `MOBILE_USE_ACCOUNT_ID` / Volcengine AccountId | 查看实时画面时必填 | 火山账号 ID，云手机 Web SDK 初始化时会使用。只有需要在 Pod 详情中查看云手机实时画面时才必须填写。 |
| `MOBILE_USE_STS_ROLE_TRN` / STS RoleTrn | 查看实时画面时必填 | 后端用它调用 STS AssumeRole，给前端 Web SDK 签发短期 Token。未填写时无法打开实时画面。 |
| `MOBILE_USE_STREAM_TOKEN_TTL_SECONDS` | 查看实时画面时必填 | Web SDK 实时画面短期 Token 有效期，单位秒。默认 `600`，允许范围 `60` 到 `3600`。 |
| `MOBILE_USE_USE_BASE64_SCREENSHOT` | 否 | 是否用 Base64 文本形式传输截图。普通使用保持默认即可。 |
| `MOBILE_USE_MAX_STEP` | 否 | Agent 最多执行多少步。任务很复杂时可适当调大。 |
| `MOBILE_USE_TIMEOUT_SECONDS` | 否 | 远端单次任务超时时间，单位秒。任务经常没跑完就失败时可适当调大。 |
| `MOBILE_USE_RETRY_LIMIT` | 否 | AI 调用失败后的重试次数。一般保持默认即可。 |
| `MOBILE_USE_SCREEN_RECORD` | 否 | 是否开启云手机录屏。开启后更方便排查问题，但会产生更多产物。 |
| `MOBILE_USE_SYSTEM_PROMPT` | 否 | 给 Agent 的系统提示词。没有定制需求时保持为空即可。 |
| `MOBILE_USE_OUTPUT_SCHEMA` | 否 | 要求 Agent 按指定 JSON 结构输出结果。只有需要固定格式结果时再配置。 |
| `MOBILE_USE_CALLBACK_INFO` | 否 | 任务结束后的回调配置。没有外部系统接收结果时保持为空。 |
| `MOBILE_USE_MCP_JSON` | 否 | 第三方 MCP 工具配置。没有外部工具接入时保持为空。 |
| `MOBILE_USE_MAX_OUTPUT_TOKENS` | 否 | 限制模型单次最多输出多少 token。普通使用可以不填。 |
| `MOBILE_USE_GPS_INFO` | 否 | 给设备注入 GPS 位置信息。只有测试定位相关场景时需要。 |

云手机实时画面查看走的是 Web SDK 独立链路。只执行用例时，可以不配置
`MOBILE_USE_ACCOUNT_ID`、`MOBILE_USE_STS_ROLE_TRN` 和
`MOBILE_USE_STREAM_TOKEN_TTL_SECONDS`；但如果要在 Pod 详情里点击“查看画面”，
这三个变量必须填写。

`MOBILE_USE_STS_ROLE_TRN` 的获取方式：

1. 打开火山引擎控制台，进入 IAM / 访问控制。
2. 创建或选择一个可被当前 AK/SK AssumeRole 的角色。
3. 给该角色授予云手机 Web SDK 拉流所需的 ACEP 权限，例如
   `ACEPReadOnlyAccess`。
   建议尽量把权限限制在目标 Product ID、Pod ID 范围和用户 ID 范围内。
4. 在角色详情页复制角色 TRN，格式通常类似
   `trn:iam::<account-id>:role/<role-name>`。
5. 将这个值填入 `MOBILE_USE_STS_ROLE_TRN`，然后重启后端服务。

## 小包客户使用说明

面向小包客户交付时，可以把本项目按单机应用使用：一个后端进程、一个 SQLite 数据目录、一个可通过浏览器访问的 Web 控制台。

### 首次部署

1. 将交付包解压到目标机器。
2. 运行 `uv sync` 和 `npm ci` 安装依赖。
3. 复制 `.env.example` 为 `.env`，至少配置：

```bash
APP_ENV=production
APP_DATA_DIR=./data
APP_SECRET_KEY=replace-with-a-stable-random-string-at-least-32-bytes
APP_BASE_URL=http://127.0.0.1:8000
TASK_WORKER_CONCURRENCY=16
TASK_WORKER_DRAIN_TIMEOUT_SECONDS=30
```

上面配置的作用：

| 配置 | 建议值 | 作用 |
| --- | --- | --- |
| `APP_ENV` | `production` | 告诉系统按交付/生产方式运行，避免使用开发环境默认行为。 |
| `APP_DATA_DIR` | `./data` | 指定数据保存位置。以后备份、迁移、排查问题时主要看这个目录。 |
| `APP_SECRET_KEY` | 自己生成一串至少 32 字节的随机字符串 | 用来加密保存云端密钥等敏感配置。部署后请固定不变。 |
| `APP_BASE_URL` | `http://127.0.0.1:8000` 或实际访问地址 | 告诉系统自己的访问地址。换端口、换域名、加反向代理时需要同步修改。 |
| `TASK_WORKER_CONCURRENCY` | `16` | 控制后端最多同时处理多少个任务。修改 `.env` 后需要重启服务才会生效。 |
| `TASK_WORKER_DRAIN_TIMEOUT_SECONDS` | `30` | 收到 `SIGTERM` 后等待本地 Worker 排空的最长秒数，合法范围为 `1..30`。 |

关于并发数要特别注意：

- `TASK_WORKER_CONCURRENCY` 是整个后端服务的全局上限。
- 每个业务空间默认上限为 `4`，可配置范围为 `1-8`。
- 页面中测试计划/批次填写的“设备并发数”是本次运行的上限。
- 本轮实际新增并发取全局剩余、业务剩余、批次剩余和当前业务可用设备数中的最小值。
- 服务重启期间 readiness 会返回 `503`。已保存 `remote_run_id` 的远端任务会在新进程启动后恢复轮询，不会重新发起远端执行。

4. 运行 `make dev` 启动服务。
5. 打开 `http://127.0.0.1:8000`，创建第一个管理员账号，并在设置页面配置 Runner。

`APP_SECRET_KEY` 用于解密已保存的 Runner 设置。请随数据目录一起备份，并在升级或迁移时保持不变。

### 真实设备配置

小规模部署可以直接在设置页面配置 Mobile Use：

1. 打开 `设置` 页面。
2. 将 Runner 模式设置为 `mobile_use`。
3. 填写 Access Key ID、Secret Access Key、Product ID、TOS Bucket 和 TOS Region。
4. 保存设置并执行诊断。
5. 打开 Pod 池页面，确认设备已被发现。
6. 创建用例或测试计划，并使用 Mobile Use Runner 执行。

如果需要脚本化部署，也可以在 `.env` 中通过 `MOBILE_USE_*` 环境变量提供默认值。页面中保存的配置优先级高于环境变量默认值。

### 日常运行

```bash
make dev
```

该命令会构建前端，并在 `127.0.0.1:8000` 启动 FastAPI。长期运行时，可以用现有进程管理工具托管同一条启动命令，并确保重启前后保留 `APP_DATA_DIR`。

外部健康检查可以使用：

```text
GET /health/live
GET /health/ready
```

### 升级与备份

替换交付包前：

- 停止正在运行的进程。
- 备份 `APP_DATA_DIR`，包括 `app.db` 和自动生成的 `secret.key`。
- 保持同一个 `APP_SECRET_KEY`。
- 重新运行 `uv sync` 和 `npm ci` 安装依赖。
- 启动服务，并检查 `/health/ready`。

## 部署方式说明

当前仓库提供了一个 `Dockerfile` 示例，可用于构建单实例镜像。Docker 部署时必须把 `APP_DATA_DIR` 挂载为持久化卷，并且只运行一个后端实例。

### Docker 示例部署

1. 准备 `.env`，至少配置 `APP_ENV`、`APP_SECRET_KEY`、`APP_BASE_URL` 和 `TASK_WORKER_CONCURRENCY`。Docker 运行时建议显式覆盖 `APP_DATA_DIR=/app/data`。
2. 构建镜像：

```bash
docker build -t mua-platform:latest .
```

3. 创建本地数据目录：

```bash
mkdir -p data
```

4. 启动容器：

```bash
docker run -d \
  --name mua-platform \
  --restart unless-stopped \
  --env-file .env \
  -e APP_DATA_DIR=/app/data \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  mua-platform:latest
```

5. 访问 `http://127.0.0.1:8000`，并检查健康状态：

```bash
curl http://127.0.0.1:8000/health/ready
```

Docker 部署注意事项：

- `./data` 会保存 SQLite 数据库和密钥文件，必须长期保留。
- `APP_SECRET_KEY` 必须固定不变，否则已保存的 Runner 密钥配置可能无法解密。
- 不要启动多个容器同时挂载同一个 `./data` 目录写入 SQLite。
- 如果在 Linux 上遇到数据目录写入失败，请确认宿主机 `./data` 目录对容器内用户可写。

### 非 Docker 部署

推荐的正式部署方式是单机单实例：

1. 在服务器安装 Python 3.12、uv、Node.js 22 和 npm。
2. 拉取或解压代码包。
3. 安装依赖并构建前端：

```bash
uv sync
npm ci
npm run build
```

4. 准备 `.env`，至少配置 `APP_ENV`、`APP_DATA_DIR`、`APP_SECRET_KEY`、`APP_BASE_URL` 和 `TASK_WORKER_CONCURRENCY`。
5. 启动后端服务：

```bash
uv run uvicorn mua_platform.main:app --host 0.0.0.0 --port 8000
```

6. 用 systemd、supervisor、pm2 或其他进程管理工具托管上面的启动命令。
7. 如需域名和 HTTPS，在前面加 Nginx、Caddy 或网关反向代理到 `127.0.0.1:8000`。
8. 部署后访问 `/health/ready`，确认数据库、数据目录和 Worker 都是 ready。

注意事项：

- 当前架构是单租户、单 FastAPI 实例、单 SQLite 数据库，不建议直接多实例横向扩容。
- 不要让多个容器或多个进程同时写同一个 SQLite 数据库。
- `APP_DATA_DIR` 必须持久化保存，不能放在容器临时层或会被清理的目录里。
- `APP_SECRET_KEY` 必须稳定，升级、迁移、重启都不要随意更换。
- `make dev` 会带 `--reload`，适合本地开发；正式部署建议直接使用上面的 `uvicorn` 命令，并交给进程管理工具守护。

### Devbox `systemd --user` 部署

如果你是在内部开发机上通过 HTTP 访问，并使用 `systemd --user`、用户
`linger` 和仓库内脚本
[`scripts/mua-platform-systemd.sh`](scripts/mua-platform-systemd.sh)
托管服务，请参考
[docs/devbox-systemd-deployment.md](docs/devbox-systemd-deployment.md)。

## Runner 模式

### Mobile Use Runner

Mobile Use Runner 面向真实移动设备执行。它需要：

- Access Key ID
- Secret Access Key
- Product ID
- TOS Bucket
- TOS Region，例如 `cn-beijing`

平台会通过 `ListPod` 发现 Pod，通过 `DetailPod` 确认可用性，并在创建任务时记录执行配置快照。远端执行流程为 `RunAgentTaskOneStep -> ListAgentRunCurrentStep -> GetAgentResult`。

敏感值在 UI 中按只写方式处理。Access Key 和 API Key 不应写入 fixture、截图、日志、shell history、issue 或 commit。

相关 OpenAPI 文档：

- 运行任务 `RunAgentTaskOneStep`：https://docs.volcengine.com/docs/6394/2105943?lang=zh
- 取消任务：https://docs.volcengine.com/docs/6394/1953044?lang=zh
- 查询任务当前步骤 `ListAgentRunCurrentStep`：https://docs.volcengine.com/docs/6394/1953039?lang=zh
- 获取任务运行结果 `GetAgentResult`：https://docs.volcengine.com/docs/6394/1953054?lang=zh
- 查询实例详情 `DetailPod`：https://docs.volcengine.com/docs/6394/2189048?lang=zh

## 开发命令

```bash
make test          # 后端 pytest + 前端 Vitest
make test-backend  # pytest tests/backend
make test-frontend # npm test
npm run build      # TypeScript 检查 + Vite 生产构建
make e2e           # 使用临时应用服务运行 Playwright E2E
```

`make dev` 会先运行 `npm run build`，再由 FastAPI 通过 `uvicorn --reload` 托管构建后的前端。

## 项目结构

```text
Dockerfile            Docker 镜像构建示例
.dockerignore         Docker 构建上下文排除规则
ARCHITECTURE.md       系统架构、运行流程、数据模型和边界说明
src/mua_platform/      FastAPI 应用、领域服务、Runner、设置、任务
web/                   React 应用、API client、页面、组件、样式
tests/backend/         pytest 后端与领域测试
tests/frontend/        Vitest + Testing Library 测试
tests/e2e/             Playwright 浏览器流程和可控测试服务
```

关键后端模块：

- `main.py`：应用工厂、路由、Worker 启动、SPA 托管和健康检查。
- `config.py`：环境配置和 secret key 解析。
- `tasks/`：任务状态机、仓储、调度器、Worker 和执行配置。
- `runners/`：Mobile Use Runner、Universal API gateway 和结果解析器。
- `settings/`：加密 Runner 设置、校验和审计事件。
- `pods/`：Pod 发现、分配、租约和任务同步。
- `test_plans/`：测试计划模型、执行编排和报告。

## 健康检查

- `GET /health/live`：进程存活检查。
- `GET /health/ready`：数据库、数据目录和 Worker 就绪检查。

就绪检查失败会返回 HTTP 503，并给出失败项名称。这不一定表示进程已经退出。

## 交付前检查清单

交付小包或公开副本前，请先确认：

- 移除本地运行产物，例如 `data/`、`dist/`、`app.db`、临时截图和临时验证脚本。
- 确认 `.env` 和其他包含密钥的文件未被跟踪。
- 如果凭证曾出现在本地日志或截图中，轮换相关凭证。
- 在干净 checkout 上运行 `make test`、`npm run build` 和 `make e2e`。

## Agent 说明

自动化 Agent 在修改代码前应阅读 `AGENTS.md`。该文件包含项目特定的架构说明、安全规则和验证命令，这些内容有意不放在面向用户的 README 中。
