# Computer Use Test Demo

[English](README.md) | [简体中文](README.zh-CN.md)

Computer Use Test Demo 是一个本地优先的 Web 控制台，用于管理测试用例、测试计划、CUA 节点、执行记录、运行轨迹、截图、文件和报告。

平台通过火山引擎 Computer Use Agent（CUA）OpenAPI 完成节点发现、任务启动、进度查询、结果收集、任务取消和 noVNC 实时桌面查看。

## 功能特性

- 用例库：创建、编辑、导入、打标签，并配置用例默认执行参数。
- 支持单用例执行和测试计划执行。
- 支持业务空间隔离和业务维度并发上限。
- 基于 `ListCuaNode` 的 CUA 节点池发现。
- 支持自动分配节点和指定节点执行。
- 任务详情展示执行结果、截图、文件、任务信息、运行配置快照和执行轨迹。
- 通过 noVNC 查看 CUA 节点实时桌面，后端提供同源代理。
- 首个管理员初始化、多用户登录、CSRF 防护和加密设置存储。
- 使用 SQLite 本地持久化，并支持启动后恢复排队中和运行中的任务。

## 技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy、SQLite、Pydantic、uvicorn。
- 前端：React 19、React Router、TanStack Query、Vite、TypeScript。
- 测试：pytest、Vitest、Playwright。
- 包管理：Python 使用 uv，前端使用 npm。

## CUA OpenAPI 文档

| 用途 | 文档 |
| --- | --- |
| CUA OpenAPI 概览 | <https://docs.volcengine.com/docs/6394/2558649?lang=zh> |
| 运行代理任务 `RunAgentTaskOneStep` | <https://docs.volcengine.com/docs/6394/2556367?lang=zh> |
| 取消代理任务 `CancelTask` | <https://docs.volcengine.com/docs/6394/2557342?lang=zh> |
| 查询当前任务步骤 `ListAgentRunCurrentStep` | <https://docs.volcengine.com/docs/6394/2557345?lang=zh> |
| 获取任务结果 `GetAgentResult` | <https://docs.volcengine.com/docs/6394/2557346?lang=zh> |
| 创建 noVNC 拉流会话 `CreateCuaNodeNoVNCSession` | <https://docs.volcengine.com/docs/6394/2550025?lang=zh> |

节点池使用同一组 CUA OpenAPI 下的 `ListCuaNode` 和 `GetCuaNode`，服务为 `ipaas`，版本为 `2023-08-01`。

## 快速开始

前置要求：

- Python 3.12
- uv
- Node.js 22
- npm

安装依赖：

```bash
uv sync
npm ci
```

准备环境变量：

```bash
cp .env.example .env
```

编辑 `.env`，至少配置：

```dotenv
APP_SECRET_KEY=replace-with-a-stable-random-string-at-least-32-bytes
APP_DATA_DIR=./data/computer_use_test_demo
APP_BASE_URL=http://localhost:8001

COMPUTER_USE_ACCESS_KEY_ID=your-access-key-id
COMPUTER_USE_SECRET_ACCESS_KEY=your-secret-access-key
COMPUTER_USE_ACCOUNT_ID=your-volcengine-account-id
```

本地开发建议分别启动后端和前端：

```bash
uv run uvicorn cua_platform.main:app --host 0.0.0.0 --port 8001 --reload
npm run dev
```

Vite 默认运行在：

```text
http://localhost:5174
```

并将 `/api`、`/health`、`/novnc` 代理到：

```text
http://localhost:8001
```

首次打开页面后，先创建管理员账号，再进入 `设置` 页面确认 CUA 凭证。

## 配置说明

应用从环境变量和可选 `.env` 文件读取配置。可以参考 `.env.example`，但不要提交真实密钥。

### 应用配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `development` | 运行环境。使用 HTTPS 或可信反向代理时建议设为 `production`。 |
| `APP_DATA_DIR` | `./data/computer_use_test_demo` | 数据目录。SQLite 数据库和自动生成的 `secret.key` 会放在这里。升级前请备份。 |
| `APP_SECRET_KEY` | 自动生成到 `APP_DATA_DIR` | 用于加密已保存凭证。首次部署后应保持稳定。 |
| `APP_BASE_URL` | `http://localhost:8001` | 后端访问地址。更换端口、域名或反向代理时同步修改。 |
| `REQUEST_MAX_BYTES` | `1048576` | 单次请求体最大字节数。 |
| `TASK_EXECUTION_TIMEOUT_SECONDS` | `600` | 单个本地任务的最长运行时间，单位秒。 |
| `CANCEL_CONFIRM_TIMEOUT_SECONDS` | `30` | 取消任务后等待远端确认的最长时间，单位秒。 |
| `DEVICE_WAIT_TIMEOUT_SECONDS` | `300` | 指定节点不可用时任务最多等待多久后失败。 |
| `TASK_WORKER_DRAIN_TIMEOUT_SECONDS` | `30` | 服务停机时等待当前 Worker 任务自然结束的最长时间，范围 1-30 秒。 |
| `TASK_WORKER_CONCURRENCY` | `16` | 后端 Worker 全局最大并发数。 |

### CUA 配置

| 变量 | 是否必填 | 说明 |
| --- | --- | --- |
| `COMPUTER_USE_ACCESS_KEY_ID` | 是 | 火山引擎 Access Key ID。 |
| `COMPUTER_USE_SECRET_ACCESS_KEY` | 是 | 火山引擎 Secret Access Key。 |
| `COMPUTER_USE_ACCOUNT_ID` | 是 | 火山账号 ID。节点池按该账号调用 `ListCuaNode`。 |
| `COMPUTER_USE_TOS_BUCKET` | 否 | 存放截图和文件的 TOS Bucket。 |
| `COMPUTER_USE_TOS_ENDPOINT` | 否 | TOS Endpoint，例如 `tos-s3-cn-beijing.volces.com`。 |
| `COMPUTER_USE_TOS_REGION` | 否 | TOS 地域，例如 `cn-beijing`。 |
| `COMPUTER_USE_MAX_STEP` | 否 | CUA Agent 最大步骤数，接口默认 100。 |
| `COMPUTER_USE_TIMEOUT_SECONDS` | 否 | 远端任务超时时间，单位秒，接口默认 120。 |
| `COMPUTER_USE_RETRY_LIMIT` | 否 | AI 调用失败后的重试次数。 |
| `COMPUTER_USE_SYSTEM_PROMPT` | 否 | 自定义系统提示词。 |
| `COMPUTER_USE_OUTPUT_SCHEMA` | 否 | JSON 输出结构字符串。 |
| `COMPUTER_USE_CALLBACK_INFO` | 否 | 回调配置 JSON 对象。 |
| `COMPUTER_USE_MCP_JSON` | 否 | MCP 服务配置 JSON 字符串。 |
| `COMPUTER_USE_MAX_OUTPUT_TOKENS` | 否 | 模型单次最大输出 token 数。 |
| `COMPUTER_USE_REQUEST_HEADERS` | 否 | 传给 CUA 上游接口的自定义 Header，JSON 对象格式。 |

页面中保存的配置优先于环境变量默认值。密钥在页面中只写不读，并会加密落库。

## CUA 执行链路

### 节点池

节点池通过 `ListCuaNode` 按 `AccountId` 查询 CUA 节点。

常见字段映射：

| 页面含义 | CUA 字段 |
| --- | --- |
| 节点 ID | `Ecsid` |
| 名称 | `Name` |
| 公网 IP | `PublicIp` |
| 私网 IP | `PrivateIp` |
| 来源 | `Provider` |
| 地域 / 可用区 | `Region` / `ZoneId` |
| CUA 套件版本 | `PluginVersion` |
| 状态 | `Status` / `StatusName` |
| 操作系统 | `OsName` / `ImageName` |
| 规格 | `Specification`、`InstanceType`、`Vcpu`、`MemoryGiB` |

平台只把 `Status=2` 视为可分配节点。`Status=3` 表示在线但占用中。

### 启动任务

后端调用 `RunAgentTaskOneStep`，核心请求体如下：

```json
{
  "RunName": "task_<task_id>",
  "ThreadId": "generated-or-configured-thread-id",
  "AgentType": "cua",
  "Ecsid": "<selected-cua-node-ecsid>",
  "UserPrompt": "<rendered-test-case-prompt>",
  "SystemPrompt": "<configured-or-default-system-prompt>",
  "MaxStep": 100,
  "Timeout": 120,
  "RetryLimit": 3,
  "TosBucket": "<optional-bucket>",
  "TosEndpoint": "<optional-endpoint>",
  "TosRegion": "<optional-region>"
}
```

`RunAgentTaskOneStep` 返回 `RunId`。平台会把 `RunId` 保存到本地任务，用于后续查询步骤、取消、查询结果和展示轨迹。

### 查询步骤、结果和取消

- 查询进度：调用 `ListAgentRunCurrentStep`，参数为 `RunId`。
- 查询结果：调用 `GetAgentResult`，参数为 `RunId` 和 `IsDetail=true`。
- 取消任务：调用 `CancelTask`，参数为 `RunId`。
- 任务详情展示 CUA 返回的 `TotalSteps`、耗时、`ScreenShots`、`Usage`、`Files`、`Content`、`StructOutput` 等字段。

### 实时桌面

实时桌面通过 `CreateCuaNodeNoVNCSession` 创建 noVNC 会话，参数使用 `Ecsid`。

后端提供 `/novnc` 同源代理，避免浏览器第三方 Cookie 限制导致 noVNC 黑屏。前端默认内嵌代理地址，并保留新窗口打开作为兜底。

## 部署说明

### 单机部署

本项目设计为一个后端进程写一个 SQLite 数据库。不要让多个后端实例同时写同一个 `APP_DATA_DIR`。

常规部署命令：

```bash
uv sync
npm ci
npm run build
uv run uvicorn cua_platform.main:app --host 0.0.0.0 --port 8001
```

如果需要 HTTPS 或域名访问，建议在前面加 Nginx、Caddy 或其他网关，并把 `APP_BASE_URL` 设置为外部访问地址。

健康检查：

```text
GET /health/live
GET /health/ready
```

### Docker 部署

构建镜像：

```bash
docker build -t computer-use-test-demo:latest .
```

启动容器：

```bash
mkdir -p data
docker run -d \
  --name computer-use-test-demo \
  --restart unless-stopped \
  --env-file .env \
  -e APP_DATA_DIR=/app/data \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  computer-use-test-demo:latest
```

Docker 镜像内部监听 `8000`。宿主机端口可以按需映射。务必把 `/app/data` 挂载到持久化目录。

### 开发机 systemd 用户服务

如果部署在 Linux 开发机上，并希望服务在退出 SSH 后继续运行，可以使用：

```bash
./scripts/cua-platform-systemd.sh enable-linger
./scripts/cua-platform-systemd.sh install
./scripts/cua-platform-systemd.sh start
./scripts/cua-platform-systemd.sh status
./scripts/cua-platform-systemd.sh logs 100
```

脚本默认值：

```text
SERVICE_NAME=computer-use-test
PORT=8001
```

脚本要求仓库内已经存在 `.env` 和 `.venv/bin/uvicorn`。日志会写到 `data/runtime/`。

## 开发命令

```bash
make test          # 后端 pytest + 前端 Vitest
make test-backend  # pytest tests/backend
make test-frontend # npm test
npm run build      # TypeScript 检查 + Vite 生产构建
make e2e           # Playwright E2E
```

`make dev` 会先构建前端，再启动 uvicorn。前端频繁开发时，建议按“快速开始”里的方式分别启动后端和 Vite。

## 项目结构

```text
Dockerfile                 Docker 镜像构建示例
ARCHITECTURE.md            架构说明和运行边界
scripts/                   部署辅助脚本
src/cua_platform/          FastAPI 应用和领域服务
web/                       React 应用、页面、组件和样式
tests/backend/             pytest 后端测试
tests/frontend/            Vitest 前端测试
tests/e2e/                 Playwright E2E 测试
```

Python 后端包名为 `cua_platform`。当前公开行为和文档均面向 Computer Use Agent（CUA）。

## 运维注意事项

- 不要提交 `.env`、`APP_DATA_DIR`、SQLite 数据库、截图、日志和密钥。
- 升级前备份 `APP_DATA_DIR`。
- `APP_SECRET_KEY` 在重启、升级和迁移时必须保持稳定。
- 如果凭证曾出现在日志、截图或 shell history 中，请及时轮换。
- 每个 SQLite 数据目录只运行一个后端实例。
