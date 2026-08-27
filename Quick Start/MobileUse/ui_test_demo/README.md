# MUA Automation Platform

[English](README.md) | [简体中文](README.zh-CN.md)

MUA Automation Platform is a local-first web console for managing mobile UI
automation cases, execution tasks, device allocation, runtime traces, and
test-plan reports. Real-device execution is handled by the Mobile Use Runner,
which allocates devices from a configured Pod pool.

## Features

- Case library for creating, editing, importing, and reusing mobile UI test cases.
- Single-case execution and test-plan execution with per-run Agent options.
- Mobile Use Runner integration for real device execution, step polling,
  cancellation, result convergence, screenshots, and usage metadata.
- Pod pool discovery, allocation snapshots, local leases, and task-device sync.
- Task list, task detail, runtime dashboard, trace view, and structured reports.
- Reusable script extraction from completed pass/fail tasks.
- Single-admin setup, password login, CSRF protection, and encrypted runner settings.
- SQLite-backed persistence with startup recovery for queued and running tasks.

## Tech Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy, SQLite, Pydantic, uvicorn.
- Frontend: React 19, React Router, TanStack Query, Vite, TypeScript.
- Tests: pytest, Vitest, Playwright.
- Package managers: uv for Python, npm for frontend dependencies.

## Quick Start

Prerequisites:

- Python 3.12
- uv
- Node.js 22
- npm

Install dependencies and start the app:

```bash
uv sync
npm ci
make dev
```

Open `http://127.0.0.1:8000`, create the first admin account, then configure
the runner and create a case. Local data is stored under `./data` by default.
If `APP_SECRET_KEY` is not provided, the backend creates `data/secret.key`
automatically.

For frontend hot reload during UI work, run the backend and Vite separately:

```bash
uv run uvicorn mua_platform.main:app --reload
npm run dev
```

Vite proxies `/api` and `/health` to `http://localhost:8000`.

## Configuration

Configuration is read from environment variables and an optional `.env` file.
Use `.env.example` as a reference, but do not commit real secrets.

Common variables:

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `development` | Runtime mode. Use `development` for local debugging and `production` for a delivered or long-running instance. |
| `APP_DATA_DIR` | `./data` | Data directory. SQLite data and generated secret files are stored here. Back this directory up before migration or upgrade. |
| `APP_SECRET_KEY` | generated in `APP_DATA_DIR` | Encryption key for saved runner secrets. It must be at least 32 UTF-8 bytes and should stay unchanged after first deployment. |
| `APP_BASE_URL` | `http://localhost:8000` | Backend address users open in the browser or through a reverse proxy. Change it when the port, host, or public URL changes. |
| `REQUEST_MAX_BYTES` | `1048576` | Maximum request body size. Usually leave it unchanged unless imports become too large. |
| `TASK_EXECUTION_TIMEOUT_SECONDS` | `600` | Maximum runtime for one task, in seconds. Timed-out tasks are treated as failed/interrupted. |
| `CANCEL_CONFIRM_TIMEOUT_SECONDS` | `30` | How long the app waits for remote cancellation confirmation, in seconds. |
| `DEVICE_WAIT_TIMEOUT_SECONDS` | `300` | How long queued tasks wait when selected devices are offline, missing, or unavailable, in seconds. |
| `TASK_WORKER_CONCURRENCY` | `16` | Global backend Worker concurrency limit. This system-wide cap is separate from business-space and run-level device concurrency limits. |

To run on real devices, configure the runner from the Settings page or through
the `MOBILE_USE_*` variables shown in `.env.example`.

Real-device configuration:

| Setting | Required | Plain-language description |
| --- | --- | --- |
| `MOBILE_USE_ACCESS_KEY_ID` / Access Key ID | Yes | Account identifier for the Mobile Use cloud service. Think of it as the username. |
| `MOBILE_USE_SECRET_ACCESS_KEY` / Secret Access Key | Yes | Secret paired with the Access Key ID. Treat it like a password; do not commit, screenshot, or share it in chat. |
| `MOBILE_USE_PRODUCT_ID` / Product ID | Yes | Product ID for the device pool. The app uses it to discover available devices. |
| `ThreadId` | No | Remote task session ID. Usually leave it empty and let the app generate one. Set it only when multiple executions must use the same remote session. It is a per-run or case-default option, not an environment variable in `.env.example`. |
| `MOBILE_USE_TOS_BUCKET` / TOS Bucket | Yes | Object storage bucket for screenshots, recordings, and execution artifacts. |
| `MOBILE_USE_TOS_REGION` / TOS Region | Yes | Region of the TOS bucket, for example `cn-beijing`. Wrong values can break artifact upload or access. |
| `MOBILE_USE_TOS_ENDPOINT` / TOS Endpoint | No | Object storage endpoint. Usually derived from the region; set it only when storage uses a special endpoint. |
| `MOBILE_USE_POD_ID` / Pod ID | No | Pin execution to one device. Leave it empty to let the app allocate from the Pod pool. |
| `MOBILE_USE_ACCOUNT_ID` / Volcengine AccountId | Required for live view | Volcengine account ID used by the cloud phone Web SDK. Required if users need to view real-time cloud phone video from the Pod detail panel. |
| `MOBILE_USE_STS_ROLE_TRN` / STS RoleTrn | Required for live view | IAM role TRN used by the backend to issue short-lived STS credentials for the Web SDK. Real-time video cannot be opened without it. |
| `MOBILE_USE_STREAM_TOKEN_TTL_SECONDS` | Required for live view | Lifetime of the short-lived Web SDK token, in seconds. Default `600`; allowed range is `60` to `3600`. |
| `MOBILE_USE_USE_BASE64_SCREENSHOT` | No | Sends screenshots as Base64 text. Keep the default for normal use. |
| `MOBILE_USE_MAX_STEP` | No | Maximum number of Agent steps. Increase it for complex tasks. |
| `MOBILE_USE_TIMEOUT_SECONDS` | No | Remote task timeout in seconds. Increase it if tasks often stop before finishing. |
| `MOBILE_USE_RETRY_LIMIT` | No | Retry count for failed AI calls. The default is usually enough. |
| `MOBILE_USE_SCREEN_RECORD` | No | Enables cloud phone screen recording. Useful for debugging but creates more artifacts. |
| `MOBILE_USE_SYSTEM_PROMPT` | No | Custom system prompt for the Agent. Leave empty unless you need custom behavior. |
| `MOBILE_USE_OUTPUT_SCHEMA` | No | JSON schema for structured Agent output. Use only when a fixed result format is required. |
| `MOBILE_USE_CALLBACK_INFO` | No | Callback settings after task completion. Leave empty if no external system receives results. |
| `MOBILE_USE_MCP_JSON` | No | Third-party MCP tool configuration. Leave empty if no external tools are used. |
| `MOBILE_USE_MAX_OUTPUT_TOKENS` | No | Maximum model output tokens per response. Usually leave empty. |
| `MOBILE_USE_GPS_INFO` | No | Injected GPS location. Use only for location-related test cases. |

Real-time cloud phone video is a separate Web SDK flow. Task execution can run
without `MOBILE_USE_ACCOUNT_ID`, `MOBILE_USE_STS_ROLE_TRN`, and
`MOBILE_USE_STREAM_TOKEN_TTL_SECONDS`, but the "view live screen" action in Pod
details requires all three values.

How to get `MOBILE_USE_STS_ROLE_TRN`:

1. Open the Volcengine console and go to IAM / Access Control.
2. Create or choose a role that can be assumed by the AK/SK configured in this app.
3. Grant the role the ACEP permissions needed by the cloud phone Web SDK, such as
   `ACEPReadOnlyAccess`.
   Restrict the policy to the target Product ID, Pod ID range, and user ID range
   where possible.
4. Copy the role TRN from the role details page. It looks like
   `trn:iam::<account-id>:role/<role-name>`.
5. Put that value into `MOBILE_USE_STS_ROLE_TRN` and restart the backend.

## Lightweight Package Usage

For lightweight customer delivery, treat this repository as a self-contained
single-node application. The simplest operating model is one backend process,
one SQLite data directory, and one browser-accessible web console.

### First-time setup

1. Extract the package on the target machine.
2. Install dependencies with `uv sync` and `npm ci`.
3. Copy `.env.example` to `.env` and set at least:

```bash
APP_ENV=production
APP_DATA_DIR=./data
APP_SECRET_KEY=replace-with-a-stable-random-string-at-least-32-bytes
APP_BASE_URL=http://127.0.0.1:8000
TASK_WORKER_CONCURRENCY=16
TASK_WORKER_DRAIN_TIMEOUT_SECONDS=30
```

What these settings do:

| Setting | Suggested value | Purpose |
| --- | --- | --- |
| `APP_ENV` | `production` | Runs the app in delivery/production mode instead of local development mode. |
| `APP_DATA_DIR` | `./data` | Where app data is stored. Back up this directory for migration, upgrade, and troubleshooting. |
| `APP_SECRET_KEY` | A stable random string with at least 32 bytes | Encrypts saved cloud credentials and other sensitive settings. Keep it unchanged after deployment. |
| `APP_BASE_URL` | `http://127.0.0.1:8000` or the real access URL | Tells the app its own access address. Update it when host, port, domain, or reverse proxy changes. |
| `TASK_WORKER_CONCURRENCY` | `16` | Controls how many tasks the backend can process at once. Restart the service after changing it in `.env`. |
| `TASK_WORKER_DRAIN_TIMEOUT_SECONDS` | `30` | Maximum time the backend waits for active local Worker tasks during `SIGTERM`; valid range is `1..30`. |

Concurrency notes:

- `TASK_WORKER_CONCURRENCY` is the global backend service limit.
- Each business space defaults to `4` concurrent tasks and can be configured from `1` to `8`.
- The device concurrency value entered on a test plan or batch page limits that run.
- New tasks are limited by the smallest remaining global, business, and batch capacity, and by the devices currently available to that business.

4. Start the service with `make dev`.
5. Open `http://127.0.0.1:8000`, create the first admin account, and configure
   the runner from the Settings page.

`APP_SECRET_KEY` is required for decrypting saved runner settings. Back it up
with the data directory and keep it unchanged across upgrades.

### Real-device configuration

Small deployments can configure Mobile Use directly from the Settings page:

1. Open `Settings`.
2. Set Runner mode to `mobile_use`.
3. Fill in Access Key ID, Secret Access Key, Product ID, TOS Bucket, and TOS
   Region.
4. Save settings and run diagnostics.
5. Open the Pod pool page and confirm devices are discovered.
6. Create a case or test plan and run it with the Mobile Use Runner.

For scripted deployment, the same defaults can be provided with
`MOBILE_USE_*` environment variables in `.env`. Values saved from the UI take
precedence over environment defaults.

### Daily operation

```bash
make dev
```

The command builds the frontend and starts FastAPI on `127.0.0.1:8000`. For a
long-running package deployment, run the same command under your process
manager of choice and preserve `APP_DATA_DIR` between restarts.

Use these endpoints for external health checks:

```text
GET /health/live
GET /health/ready
```

### Upgrade and backup

Before replacing the package:

- Stop the running process.
- Back up `APP_DATA_DIR`, including `app.db` and `secret.key` if generated.
- Keep the same `APP_SECRET_KEY`.
- Install dependencies again with `uv sync` and `npm ci`.
- Start the service and check `/health/ready`.

## Deployment Notes

This repository includes a sample `Dockerfile` for building a single-instance image. When running with Docker, mount `APP_DATA_DIR` as a persistent volume and run only one backend instance.

### Docker example

1. Prepare `.env` with at least `APP_ENV`, `APP_SECRET_KEY`, `APP_BASE_URL`, and `TASK_WORKER_CONCURRENCY`. For Docker, explicitly override `APP_DATA_DIR=/app/data` at runtime.
2. Build the image:

```bash
docker build -t mua-platform:latest .
```

3. Create a local data directory:

```bash
mkdir -p data
```

4. Start the container:

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

5. Open `http://127.0.0.1:8000` and check readiness:

```bash
curl http://127.0.0.1:8000/health/ready
```

Docker notes:

- `./data` stores SQLite data and secret files. Keep it across restarts and upgrades.
- `APP_SECRET_KEY` must stay unchanged, or saved runner secrets may become undecryptable.
- Do not run multiple containers writing to the same SQLite data directory.
- On Linux, if the app cannot write data, make sure the host `./data` directory is writable by the container user.

### Non-Docker deployment

Recommended production deployment is single-machine, single-instance:

1. Install Python 3.12, uv, Node.js 22, and npm on the server.
2. Pull or extract the code package.
3. Install dependencies and build the frontend:

```bash
uv sync
npm ci
npm run build
```

4. Prepare `.env` with at least `APP_ENV`, `APP_DATA_DIR`, `APP_SECRET_KEY`, `APP_BASE_URL`, and `TASK_WORKER_CONCURRENCY`.
5. Start the backend:

```bash
uv run uvicorn mua_platform.main:app --host 0.0.0.0 --port 8000
```

6. Run that command under systemd, supervisor, pm2, or another process manager.
7. For domains and HTTPS, put Nginx, Caddy, or a gateway in front and proxy to `127.0.0.1:8000`.
8. After deployment, check `/health/ready` to verify database, data directory, and Worker readiness.

Important constraints:

- The current architecture is single-tenant, single FastAPI instance, and single SQLite database.
- Do not run multiple containers or processes writing to the same SQLite database.
- `APP_DATA_DIR` must be persistent, not a disposable container layer or temporary directory.
- `APP_SECRET_KEY` must stay stable across upgrades, migrations, and restarts.
- During restart, readiness returns `503` while the Worker is draining or recovering. Tasks with a saved `remote_run_id` resume polling after startup instead of starting another remote run.
- `make dev` uses `--reload` and is meant for local development. For production, run `uvicorn` directly under a process manager.

### Devbox `systemd --user` deployment

For the internal devbox HTTP deployment path that uses `systemd --user`,
user lingering, and the repo-local helper script
[`scripts/mua-platform-systemd.sh`](scripts/mua-platform-systemd.sh),
see [docs/devbox-systemd-deployment.md](docs/devbox-systemd-deployment.md).

## Runner Mode

### Mobile Use Runner

Mobile Use Runner executes against real mobile devices. It requires:

- Access Key ID
- Secret Access Key
- Product ID
- TOS Bucket
- TOS Region, such as `cn-beijing`

The platform discovers Pods with `ListPod`, checks availability with
`DetailPod`, snapshots execution configuration when a task is created, and then
uses the `RunAgentTaskOneStep -> ListAgentRunCurrentStep -> GetAgentResult`
flow for remote execution.

Sensitive values are write-only in the UI. Access keys and API keys must never
be written to fixtures, screenshots, logs, shell history, issues, or commits.

Related OpenAPI references:

- Run task `RunAgentTaskOneStep`: https://docs.volcengine.com/docs/6394/2105943?lang=zh
- Cancel task: https://docs.volcengine.com/docs/6394/1953044?lang=zh
- Query current step `ListAgentRunCurrentStep`: https://docs.volcengine.com/docs/6394/1953039?lang=zh
- Get task result `GetAgentResult`: https://docs.volcengine.com/docs/6394/1953054?lang=zh
- Query instance detail `DetailPod`: https://docs.volcengine.com/docs/6394/2189048?lang=zh

## Development Commands

```bash
make test          # backend pytest + frontend Vitest
make test-backend  # pytest tests/backend
make test-frontend # npm test
npm run build      # TypeScript check + Vite production build
make e2e           # Playwright E2E with a temporary app server
```

`make dev` runs `npm run build` first and then serves the built frontend from
FastAPI with `uvicorn --reload`.

## Project Layout

```text
Dockerfile            Docker image build example
.dockerignore         Docker build context ignore rules
ARCHITECTURE.md       System architecture, runtime flow, data model, boundaries
src/mua_platform/      FastAPI app, domain services, runners, settings, tasks
web/                   React application, API client, pages, components, styles
tests/backend/         pytest backend and domain tests
tests/frontend/        Vitest + Testing Library tests
tests/e2e/             Playwright browser flows and controlled test servers
```

Key backend modules:

- `main.py`: application factory, routers, worker startup, SPA serving, health checks.
- `config.py`: environment settings and secret-key resolution.
- `tasks/`: task state machine, repository, scheduler, worker, execution config.
- `runners/`: Mobile Use Runner, Universal API gateway, result parser.
- `settings/`: encrypted runner settings, validation, audit events.
- `pods/`: Pod discovery, allocation, leases, and task sync.
- `test_plans/`: test-plan models, execution orchestration, reports.

## Health Checks

- `GET /health/live`: process liveness.
- `GET /health/ready`: database, data directory, and worker readiness.

Readiness failures return HTTP 503 with failed check names. They do not
necessarily mean the process has exited.

## Delivery Checklist

Before handing off a package or making a public copy:

- Remove local runtime artifacts such as `data/`, `dist/`, `app.db`,
  temporary screenshots, and ad-hoc verification scripts.
- Confirm `.env` and other secret-bearing files are not tracked.
- Rotate any credentials that may have appeared in local logs or screenshots.
- Run `make test`, `npm run build`, and `make e2e` on a clean checkout.

## Agent Notes

Automation agents should read `AGENTS.md` before making changes. It contains the
project-specific architecture notes, safety rules, and verification commands
that are intentionally kept out of the user-facing README.
