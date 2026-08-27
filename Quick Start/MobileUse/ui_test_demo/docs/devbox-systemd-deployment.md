# Devbox `systemd --user` Deployment

This guide documents the current long-running deployment path for the MUA
Automation Platform on a Linux devbox where:

- the service is accessed over plain HTTP inside the internal network,
- `systemd --user` is available,
- the user has `linger=yes`, so the service can survive logout,
- Python dependencies are installed in a repo-local virtual environment.

This is the path currently used on devbox `10.37.28.65`.

## Scope

Use this guide when you want a persistent devbox-hosted instance that:

- serves the built frontend from `dist/`,
- runs the backend with `uvicorn`,
- persists SQLite data under the repo directory,
- is managed through `systemctl --user`,
- stays available after you disconnect from the devbox shell.

This guide is not the public production deployment guide. For public-facing or
shared deployment behind HTTPS, prefer the standard non-Docker deployment in
the README and put a reverse proxy in front.

## Files and Paths

Repo-local service management script:

```text
scripts/mua-platform-systemd.sh
```

Devbox user service unit:

```text
~/.config/systemd/user/mua-platform-devbox.service
```

Runtime paths used by the service:

```text
repo root:        ~/eval-mua
data directory:   ~/eval-mua/data
stdout log:       ~/eval-mua/data/runtime/mua-platform-devbox.stdout.log
stderr log:       ~/eval-mua/data/runtime/mua-platform-devbox.stderr.log
```

## Current Runtime Mode

The current devbox service runs in HTTP-compatible mode:

```text
APP_ENV=development
APP_BASE_URL=http://<devbox-ip>:8000
APP_DATA_DIR=/data00/home/<user>/eval-mua/data
```

Why `development` instead of `production`?

- In this codebase, auth cookies are marked `Secure` only when `APP_ENV` is
  `production`.
- On a plain `http://` devbox URL, a `Secure` session cookie is not sent back
  by normal clients, which causes authenticated API calls to return `401`.
- For this reason, the devbox HTTP deployment intentionally uses
  `APP_ENV=development`.

Trade-off:

- This is appropriate for an internal devbox reached over HTTP.
- It is not appropriate for a public or Internet-facing deployment.

## Preconditions

Before using the `systemd --user` script, make sure these are true on the
devbox:

1. The repo exists locally, for example at `~/eval-mua`.
2. The frontend has already been built and `dist/` exists.
3. The backend virtual environment already exists and contains `uvicorn` and
   all runtime dependencies.
4. `.env` exists in the repo root and contains the desired runtime values.
5. `systemd --user` works on the machine.
6. `linger` is enabled for the current user.

Quick checks:

```bash
cd ~/eval-mua
test -f .env
test -x .venv/bin/uvicorn
test -f dist/index.html
systemctl --user --version
loginctl show-user "$USER" -p Linger
```

Expected linger output:

```text
Linger=yes
```

## First-Time Setup

### 1. Make sure `.env` is correct

At minimum, verify:

```dotenv
APP_ENV=development
APP_BASE_URL=http://10.37.28.65:8000
APP_DATA_DIR=/data00/home/yanghailan/eval-mua/data
APP_SECRET_KEY=<stable key>
TASK_WORKER_CONCURRENCY=16
TASK_WORKER_DRAIN_TIMEOUT_SECONDS=30
```

For HTTP devbox deployment, keep `APP_ENV=development` unless you are also
moving the service behind HTTPS.

### 2. Enable linger

Run once per user:

```bash
cd ~/eval-mua
./scripts/mua-platform-systemd.sh enable-linger
```

Verify:

```bash
loginctl show-user "$USER" -p Linger
```

### 3. Install the user service

```bash
cd ~/eval-mua
./scripts/mua-platform-systemd.sh install
```

This writes the rendered unit to:

```text
~/.config/systemd/user/mua-platform-devbox.service
```

### 4. Start the service

```bash
cd ~/eval-mua
./scripts/mua-platform-systemd.sh start
```

### 5. Verify service state

```bash
cd ~/eval-mua
./scripts/mua-platform-systemd.sh status
curl http://127.0.0.1:8000/health/ready
```

From another machine on the same internal network:

```bash
curl http://10.37.28.65:8000/health/ready
```

## Day-2 Operations

### Status

```bash
cd ~/eval-mua
./scripts/mua-platform-systemd.sh status
```

### Restart

```bash
cd ~/eval-mua
./scripts/mua-platform-systemd.sh restart
```

### Stop

```bash
cd ~/eval-mua
./scripts/mua-platform-systemd.sh stop
```

### Logs

Show the last 80 lines by default:

```bash
cd ~/eval-mua
./scripts/mua-platform-systemd.sh logs
```

Show more lines:

```bash
cd ~/eval-mua
./scripts/mua-platform-systemd.sh logs 200
```

## Update Workflow

When code or built assets change:

1. Sync or update the repo on the devbox.
2. Refresh `.venv` and `dist/` if needed.
3. Restart the service with `./scripts/mua-platform-systemd.sh restart`.
4. Re-run health checks.

Typical flow:

```bash
cd ~/eval-mua
./scripts/mua-platform-systemd.sh restart
curl http://127.0.0.1:8000/health/ready
```

The rendered unit sends `SIGTERM` and uses `TimeoutStopSec=45`. On `SIGTERM`,
the backend enters draining, readiness returns `503`, new tasks are not
scheduled, and active local Worker tasks get up to
`TASK_WORKER_DRAIN_TIMEOUT_SECONDS` seconds to finish. If the process exits
while a remote task is still running, the next process resumes polling by the
saved `remote_run_id`.

Do not start a second MUA backend process against the same SQLite data
directory. The graceful restart path is single-instance recovery, not
multi-instance rolling deployment.

If Python dependencies changed, rebuild `.venv` first. If frontend code
changed, rebuild `dist/` first.

## Service Script Reference

The repo-local helper supports:

```bash
./scripts/mua-platform-systemd.sh enable-linger
./scripts/mua-platform-systemd.sh disable-linger
./scripts/mua-platform-systemd.sh install
./scripts/mua-platform-systemd.sh uninstall
./scripts/mua-platform-systemd.sh start
./scripts/mua-platform-systemd.sh stop
./scripts/mua-platform-systemd.sh restart
./scripts/mua-platform-systemd.sh status
./scripts/mua-platform-systemd.sh logs
./scripts/mua-platform-systemd.sh logs 200
./scripts/mua-platform-systemd.sh print-unit
```

## Troubleshooting

### Login works but authenticated API requests return `401`

Symptom:

- Login succeeds
- Later requests to `/api/v1/tasks` or other authenticated endpoints return
  `401 authentication_required`

Likely cause:

- The service is running with `APP_ENV=production` while the site is accessed
  over `http://`
- Auth cookies are marked `Secure` and are not sent back over plain HTTP

Fix:

1. Set `APP_ENV=development` in `.env`
2. Restart the service
3. Log in again

### Service starts then exits with `/app/data` permission errors

Likely cause:

- `.env` still contains `APP_DATA_DIR=/app/data` from a Docker-oriented setup

Fix:

Set a repo-local or home-local persistent path instead, for example:

```dotenv
APP_DATA_DIR=/data00/home/yanghailan/eval-mua/data
```

Then restart the service.

### `systemctl --user` exists but service does not survive logout

Likely cause:

- `linger` is still disabled

Fix:

```bash
./scripts/mua-platform-systemd.sh enable-linger
loginctl show-user "$USER" -p Linger
```

Expected:

```text
Linger=yes
```

### The service unit is installed but `status` shows failed

Check:

```bash
./scripts/mua-platform-systemd.sh status
./scripts/mua-platform-systemd.sh logs 200
```

Focus on:

- missing `.venv/bin/uvicorn`
- bad `APP_DATA_DIR`
- stale `.env`
- missing built frontend `dist/`

## Notes

- The current app is still a single-process, single-instance SQLite service.
- Do not start multiple instances pointing at the same `APP_DATA_DIR`.
- Keep `APP_SECRET_KEY` stable across restarts and updates.
- If you later move to HTTPS, you can switch back to `APP_ENV=production` and
  restart the service.
