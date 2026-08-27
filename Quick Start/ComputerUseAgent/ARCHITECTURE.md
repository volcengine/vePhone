# Computer Use Test Demo Architecture

This document describes the boundaries, modules, runtime flow, and operational
constraints of Computer Use Test Demo. It is intended for engineers who need to
develop, deploy, troubleshoot, or customize the project.

## Design Goals

- Local-first deployment: one host can run the web app, backend worker, and
  SQLite database.
- CUA-first execution: real tasks run through Volcengine Computer Use Agent
  OpenAPI.
- Traceable results: task status, runner configuration snapshots, runtime
  details, screenshots, files, traces, and reports are persisted locally.
- Minimal credential exposure: secrets are encrypted at rest and never echoed
  back through the UI.
- Browser-friendly live view: noVNC sessions are proxied through the backend so
  the frontend can embed the desktop view from the same origin.

## System Overview

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
  +-- noVNC proxy store

RunnerAdapter
  |
  +-- CUA runner logic -> UniversalGateway -> Volcengine CUA OpenAPI
```

The deployment boundary is intentionally simple: one backend process, one
SQLite database, and one data directory. Node leases provide mutual exclusion
inside a single backend instance. They are not distributed locks.

## Frontend Layers

The frontend lives in `web/` and uses React 19, React Router, TanStack Query,
TypeScript, and Vite.

- `web/app.tsx`: routes, authentication gate, and page loading.
- `web/api/client.ts`: API wrapper, CSRF handling, and unauthorized handling.
- `web/api/types.ts`: frontend API contract types.
- `web/pages/`: page containers for cases, test plans, tasks, node pool,
  settings, users, and reports.
- `web/components/`: shared UI such as execution config form, pagination,
  status badges, runtime config snapshot, and live desktop panel.
- `web/utils/`: pure helpers for time formatting, status mapping, runtime trace
  processing, and tags.

The frontend does not store real credentials. Secret inputs are write-only.

## Backend Layers

The backend lives in `src/cua_platform/`. The public product behavior is
Computer Use Agent based.

- `main.py`: app factory, lifespan, routers, worker startup, health checks, and
  SPA serving.
- `api/`: FastAPI routers and response schemas.
- `auth/`: initial admin setup, users, sessions, roles, CSRF, and rate limiting.
- `business/`: business spaces and per-space execution limits.
- `cases/`: test case models, import, statistics, and default agent options.
- `test_plans/`: plans, case ordering, plan execution, and reports.
- `tasks/`: task models, state machine, repository, batches, scheduler, worker,
  and execution config snapshots.
- `runners/`: runner protocol, task prompt rendering, CUA result parsing, and
  Universal API gateway.
- `pods/`: CUA node discovery, cached node pool, allocation, cooldown, and local
  leases.
- `settings/`: encrypted runner settings, validation, and audit records.
- `traces/`: safe task trace spans and query APIs.
- `novnc_proxy.py` and `api/novnc.py`: same-origin noVNC HTTP/WebSocket proxy.

Routers should stay thin. Business rules belong in services, repositories, or
runner code.

## Data Storage

`APP_DATA_DIR` points to the runtime data directory. The SQLite database is
`APP_DATA_DIR/app.db`. If `APP_SECRET_KEY` is not configured, the app generates
`APP_DATA_DIR/secret.key`.

Main tables:

- Authentication: `users`, `auth_sessions`.
- Business spaces: `business_spaces`.
- Settings: `settings`.
- Cases: `test_cases`.
- Plans: `test_plans`, `test_plan_cases`, `plan_executions`.
- Tasks: `tasks`, `task_batches`, `task_runner_configs`, `task_events`,
  `task_steps`.
- CUA nodes: `discovered_pods`, `pod_pool_refreshes`, `pod_leases`.
- Traces: `task_trace_spans`.
- Reusable scripts: `reusable_scripts` related tables.

Each task stores an execution configuration snapshot at creation time. Later
changes to global or business settings do not change historical tasks.

## Task Lifecycle

Task state transitions are enforced by `tasks/state_machine.py`.

```text
script_pending -> queued
queued -> running
queued -> result_ready
queued -> cancelled
running -> result_ready
running -> cancelled
```

Terminal states:

- `result_ready`: must include a `pass` or `fail` verdict.
- `cancelled`: no verdict.

Execution flow:

1. User starts a case or a test plan.
2. Backend writes task records, batch records, snapshots, and idempotency keys.
3. `BatchScheduler` selects eligible queued tasks.
4. `TaskWorker` creates a runner based on the task's runner type.
5. Runner starts a CUA task and stores the returned `RunId`.
6. Runner polls current step and final result using `RunId`.
7. `TaskService` converts runner events into local task state, result assets,
   evidence, trace spans, and reports.
8. Frontend reads task details and trace data from local APIs.

During single-instance shutdown, the Worker enters draining state and stops
accepting new work. Active tasks may finish for up to
`TASK_WORKER_DRAIN_TIMEOUT_SECONDS`; after a restart, the new process recovers
unfinished remote tasks and continues polling them with their stored `RunId`.

## CUA Runner Flow

The CUA execution flow uses Volcengine Universal API requests:

```text
ListCuaNode / GetCuaNode
  -> RunAgentTaskOneStep
  -> ListAgentRunCurrentStep
  -> GetAgentResult
  -> CancelTask when requested
  -> CreateCuaNodeNoVNCSession for live desktop view
```

Important payload fields for `RunAgentTaskOneStep`:

| Field | Meaning |
| --- | --- |
| `AgentType` | Always `cua`. |
| `Ecsid` | Selected CUA node ID. |
| `RunName` | Local task-based run name. |
| `ThreadId` | Configured thread ID or generated stable ID. |
| `UserPrompt` | Rendered test case prompt. |
| `SystemPrompt` | Configured or built-in system prompt. |
| `MaxStep` | Max agent steps. |
| `Timeout` | Remote timeout in seconds. |
| `RetryLimit` | AI retry limit. |
| `TosBucket` / `TosEndpoint` / `TosRegion` | Optional artifact storage target. |
| `CallbackInfo` / `OutputSchema` / `McpJson` / `MaxOutputTokens` | Optional advanced parameters. |

Result handling:

- `GetAgentResult` is called with `IsDetail=true`.
- `ScreenShots`, `Usage`, `Files`, `Content`, `StructOutput`, `TotalSteps`, and
  duration fields are merged into task runtime assets when present.
- Screenshot records are filtered by `remote_run_id` before being exposed to
  the frontend.
- The UI maps remote execution outcomes into three high-level final states:
  success, failed, and stopped.

## CUA Node Allocation

The node pool turns CUA node availability into task scheduling decisions.

1. `PodGateway` calls `ListCuaNode` and `GetCuaNode`.
2. `pods/service.py` caches nodes in `discovered_pods`.
3. Only CUA status `2` is allocatable.
4. Status `3` is online but occupied.
5. Creating a task records the requested allocation strategy.
6. Before running, the backend creates a local `pod_leases` row for the selected
   `Ecsid`.
7. Terminal task states, cancellation, failure, or startup cleanup normally
   release the lease. An unknown remote start outcome keeps the lease until the
   possible remote execution timeout plus the 30-second safety interval elapses.

This mechanism does not start, stop, rebuild, or fence cloud resources. It only
coordinates task assignment inside one backend instance.

## noVNC Live View

`CreateCuaNodeNoVNCSession` returns viewer and WebSocket URLs. Directly embedding
the remote viewer can fail because browser iframe requests may not carry the
remote session cookie.

The backend therefore provides:

```text
/novnc/view?sid=<local-session-id>
/novnc/{path}
/novnc/ws
```

The proxy stores the remote noVNC session server-side and exposes same-origin
HTTP/WebSocket routes to the frontend. This keeps the embedded viewer stable in
local development and common reverse-proxy deployments.

## Test Plan Execution

Test plans snapshot their execution context:

1. `test_plans` stores plan metadata.
2. `test_plan_cases` stores ordered case membership.
3. Starting a plan creates one `task_batches` row and multiple `tasks`.
4. `plan_executions` stores plan name, tags, selected cases, node strategy,
   concurrency, runner type, and configuration snapshot.
5. Reports read the execution snapshot and associated tasks, not the latest
   edited plan state.

## Security Boundaries

- `APP_SECRET_KEY` derives the encryption key for settings. Back it up and keep
  it stable.
- Secret settings are encrypted in SQLite and are not returned in full by APIs.
- Empty secret inputs mean "keep existing value".
- API errors should not expose credentials, raw upstream payloads, or stack
  traces.
- Trace spans store safe metadata such as action, method, duration, request ID,
  and error code. They intentionally do not store request bodies.
- `.env`, `APP_DATA_DIR`, databases, logs, screenshots, and generated secrets
  must not be published.

## Runtime Constraints

The current architecture intentionally favors a small deployment footprint:

- Single backend instance.
- Single SQLite database.
- Backend in-process worker and scheduler.
- No external queue.
- No distributed lock.
- No multi-instance task fencing.

Readiness returns HTTP 503 while the Worker is draining and until startup
recovery completes. Restart this single instance in place; never overlap old
and new processes against the same SQLite file.

If horizontal scaling is required, redesign task claiming, CUA node leases,
database storage, and scheduler ownership first. Do not simply run multiple
backend processes against the same SQLite file.

## Verification Commands

```bash
make test
npm run build
make e2e
```

For scoped changes, run the smallest relevant backend or frontend test first,
then broaden verification before release.
