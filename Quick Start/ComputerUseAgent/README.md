# Computer Use Test Demo

[English](README.md) | [简体中文](README.zh-CN.md)

Computer Use Test Demo is a local-first web console for managing test cases,
test plans, Computer Use Agent (CUA) nodes, execution records, runtime traces,
screenshots, files, and reports.

The platform calls Volcengine CUA OpenAPI to discover CUA nodes, start agent
tasks, poll task progress, collect execution results, cancel running tasks, and
open noVNC sessions for live desktop viewing.

## Features

- Test case library with create, edit, import, tagging, and default execution
  configuration.
- Single-case execution and test-plan execution.
- Business spaces with per-space concurrency limits.
- CUA node pool discovery based on `ListCuaNode`.
- Automatic or specified-node task allocation.
- Runtime detail pages with result summary, screenshots, files, task metadata,
  configuration snapshots, and trace timeline.
- noVNC live desktop view through a same-origin backend proxy.
- First-admin setup, multi-user login, CSRF protection, and encrypted settings.
- Local SQLite persistence, with startup recovery for queued/running tasks.

## Tech Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy, SQLite, Pydantic, uvicorn.
- Frontend: React 19, React Router, TanStack Query, Vite, TypeScript.
- Tests: pytest, Vitest, Playwright.
- Package managers: uv for Python, npm for frontend assets.

## OpenAPI References

This project integrates with the following CUA OpenAPI documents:

| Purpose | OpenAPI |
| --- | --- |
| CUA OpenAPI overview | <https://docs.volcengine.com/docs/6394/2558649?lang=zh> |
| Start an agent task, `RunAgentTaskOneStep` | <https://docs.volcengine.com/docs/6394/2556367?lang=zh> |
| Cancel an agent task, `CancelTask` | <https://docs.volcengine.com/docs/6394/2557342?lang=zh> |
| Query current task step, `ListAgentRunCurrentStep` | <https://docs.volcengine.com/docs/6394/2557345?lang=zh> |
| Get task result, `GetAgentResult` | <https://docs.volcengine.com/docs/6394/2557346?lang=zh> |
| Create noVNC session, `CreateCuaNodeNoVNCSession` | <https://docs.volcengine.com/docs/6394/2550025?lang=zh> |

The node pool uses `ListCuaNode` and `GetCuaNode` in the same CUA API family
(`ipaas`, `2023-08-01`).

## Quick Start

Prerequisites:

- Python 3.12
- uv
- Node.js 22
- npm

Install dependencies:

```bash
uv sync
npm ci
```

Create an environment file:

```bash
cp .env.example .env
```

Edit `.env` and configure at least:

```dotenv
APP_SECRET_KEY=replace-with-a-stable-random-string-at-least-32-bytes
APP_DATA_DIR=./data/computer_use_test_demo
APP_BASE_URL=http://localhost:8001

COMPUTER_USE_ACCESS_KEY_ID=your-access-key-id
COMPUTER_USE_SECRET_ACCESS_KEY=your-secret-access-key
COMPUTER_USE_ACCOUNT_ID=your-volcengine-account-id
```

Start backend and frontend separately for local development:

```bash
uv run uvicorn cua_platform.main:app --host 0.0.0.0 --port 8001 --reload
npm run dev
```

Vite runs on `http://localhost:5174` and proxies `/api`, `/health`, and
`/novnc` to `http://localhost:8001`.

Open:

```text
http://localhost:5174
```

On first visit, create the initial administrator account, then open
`Settings` to verify or update CUA credentials.

## Configuration

The application reads environment variables from the process environment and
optionally from `.env`. Use `.env.example` as a template and never commit real
credentials.

### Application Settings

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `development` | Runtime environment. Use `production` behind HTTPS or a trusted reverse proxy. |
| `APP_DATA_DIR` | `./data/computer_use_test_demo` | Directory for SQLite database and generated `secret.key`. Back it up before upgrades. |
| `APP_SECRET_KEY` | generated in `APP_DATA_DIR` | Encryption secret for saved credentials. Keep it stable after first deployment. |
| `APP_BASE_URL` | `http://localhost:8001` | Public backend base URL used by the service. |
| `REQUEST_MAX_BYTES` | `1048576` | Maximum accepted request body size. |
| `TASK_EXECUTION_TIMEOUT_SECONDS` | `600` | Local timeout for one task. |
| `CANCEL_CONFIRM_TIMEOUT_SECONDS` | `30` | Maximum wait time for cancel confirmation. |
| `DEVICE_WAIT_TIMEOUT_SECONDS` | `300` | Maximum wait time when a specified node is unavailable. |
| `TASK_WORKER_DRAIN_TIMEOUT_SECONDS` | `30` | Maximum time to let active Worker tasks finish during shutdown. Range: 1-30 seconds. |
| `TASK_WORKER_CONCURRENCY` | `16` | Global backend worker concurrency limit. |

### CUA Settings

| Variable | Required | Description |
| --- | --- | --- |
| `COMPUTER_USE_ACCESS_KEY_ID` | yes | Volcengine Access Key ID. |
| `COMPUTER_USE_SECRET_ACCESS_KEY` | yes | Volcengine Secret Access Key. |
| `COMPUTER_USE_ACCOUNT_ID` | yes | Volcengine account ID used by `ListCuaNode`. |
| `COMPUTER_USE_TOS_BUCKET` | optional | TOS bucket for screenshots and files. |
| `COMPUTER_USE_TOS_ENDPOINT` | optional | TOS endpoint, for example `tos-s3-cn-beijing.volces.com`. |
| `COMPUTER_USE_TOS_REGION` | optional | TOS region, for example `cn-beijing`. |
| `COMPUTER_USE_MAX_STEP` | optional | Max CUA agent steps. API default is 100. |
| `COMPUTER_USE_TIMEOUT_SECONDS` | optional | Remote task timeout in seconds. API default is 120. |
| `COMPUTER_USE_RETRY_LIMIT` | optional | AI retry count. |
| `COMPUTER_USE_SYSTEM_PROMPT` | optional | System prompt override. |
| `COMPUTER_USE_OUTPUT_SCHEMA` | optional | JSON output schema string. |
| `COMPUTER_USE_CALLBACK_INFO` | optional | Callback configuration JSON object. |
| `COMPUTER_USE_MCP_JSON` | optional | MCP server configuration JSON string. |
| `COMPUTER_USE_MAX_OUTPUT_TOKENS` | optional | Maximum output tokens. |
| `COMPUTER_USE_REQUEST_HEADERS` | optional | Additional upstream request headers as a JSON object. |

Settings saved in the web UI take precedence over environment defaults.
Secret values are write-only in the UI and encrypted at rest.

## CUA Data Flow

### Node Pool

The node pool loads CUA nodes from `ListCuaNode` by `AccountId`.

Important CUA node fields:

| UI Meaning | CUA Field |
| --- | --- |
| Node ID | `Ecsid` |
| Name | `Name` |
| Public IP | `PublicIp` |
| Private IP | `PrivateIp` |
| Provider | `Provider` |
| Region / zone | `Region` / `ZoneId` |
| Plugin version | `PluginVersion` |
| Status | `Status` / `StatusName` |
| OS | `OsName` / `ImageName` |
| Specification | `Specification`, `InstanceType`, `Vcpu`, `MemoryGiB` |

Only status `2` is treated as allocatable. Status `3` means online but occupied.

### Task Start

The backend calls `RunAgentTaskOneStep` with CUA-specific payload fields:

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

`RunAgentTaskOneStep` returns `RunId`. The platform stores it on the local task
record and uses it for later polling, cancellation, result retrieval, and trace
display.

### Progress, Result, and Cancellation

- Progress polling calls `ListAgentRunCurrentStep` with `RunId`.
- Result retrieval calls `GetAgentResult` with `RunId` and `IsDetail=true`.
- Cancellation calls `CancelTask` with `RunId`.
- Task details display `TotalSteps`, duration fields, `ScreenShots`, `Usage`,
  `Files`, `Content`, and `StructOutput` when returned by CUA.

### Live Desktop View

Live desktop viewing calls `CreateCuaNodeNoVNCSession` with `Ecsid`. The backend
then exposes a same-origin `/novnc` proxy so the frontend can embed the noVNC
viewer without third-party cookie issues.

For local Vite development, `vite.config.ts` proxies `/novnc` to the backend.

## Deployment

### Single-Host Deployment

This project is designed for one backend process writing one SQLite database.
Do not run multiple backend instances against the same `APP_DATA_DIR`.

Typical non-Docker deployment:

```bash
uv sync
npm ci
npm run build
uv run uvicorn cua_platform.main:app --host 0.0.0.0 --port 8001
```

For HTTPS, put Nginx, Caddy, or another reverse proxy in front of the backend
and set `APP_BASE_URL` to the public URL.

Health checks:

```text
GET /health/live
GET /health/ready
```

### Docker

Build:

```bash
docker build -t computer-use-test-demo:latest .
```

Run:

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

The Docker image listens on port `8000` inside the container. The host port can
be changed as needed. Always mount `/app/data` to persistent storage.

### Devbox systemd User Service

For a Linux development machine with `systemd --user`, use:

```bash
./scripts/cua-platform-systemd.sh enable-linger
./scripts/cua-platform-systemd.sh install
./scripts/cua-platform-systemd.sh start
./scripts/cua-platform-systemd.sh status
./scripts/cua-platform-systemd.sh logs 100
```

Defaults:

```text
SERVICE_NAME=computer-use-test
PORT=8001
```

The script requires `.env` and `.venv/bin/uvicorn` to exist in the repository.
It writes logs under `data/runtime/`.

## Development Commands

```bash
make test          # backend pytest + frontend Vitest
make test-backend  # pytest tests/backend
make test-frontend # npm test
npm run build      # TypeScript check + Vite production build
make e2e           # Playwright E2E tests
```

`make dev` builds the frontend and starts uvicorn on the default backend port.
For active frontend development, prefer separate backend and Vite processes as
shown in Quick Start.

## Project Layout

```text
Dockerfile                 Docker image example
ARCHITECTURE.md            Architecture and runtime boundaries
scripts/                   Deployment helper scripts
src/cua_platform/          FastAPI app and domain services
web/                       React app, pages, components, styles
tests/backend/             pytest backend tests
tests/frontend/            Vitest frontend tests
tests/e2e/                 Playwright tests
```

The Python backend package is `cua_platform`. Public product behavior and
documentation in this repository are for Computer Use Agent (CUA).

## Operational Notes

- Keep `.env`, `APP_DATA_DIR`, SQLite databases, screenshots, logs, and secret
  keys out of commits and public artifacts.
- Back up `APP_DATA_DIR` before upgrades.
- Keep `APP_SECRET_KEY` stable across restarts and migrations.
- Rotate credentials if they were ever exposed in logs, screenshots, or shell
  history.
- Use a single backend process per SQLite data directory.
