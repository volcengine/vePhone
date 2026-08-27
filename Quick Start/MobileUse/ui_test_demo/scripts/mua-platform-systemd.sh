#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-mua-platform-devbox}"
UNIT_NAME="${SERVICE_NAME}.service"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_PATH="${SYSTEMD_USER_DIR}/${UNIT_NAME}"
LOG_DIR="${REPO_ROOT}/data/runtime"
STDOUT_LOG="${LOG_DIR}/${SERVICE_NAME}.stdout.log"
STDERR_LOG="${LOG_DIR}/${SERVICE_NAME}.stderr.log"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command>

Commands:
  enable-linger   Enable user lingering for the current user
  disable-linger  Disable user lingering for the current user
  install         Install/update the user service unit and enable it
  uninstall       Stop, disable, and remove the user service unit
  start           Start the user service
  stop            Stop the user service
  restart         Restart the user service
  status          Show current service status
  logs [N]        Show the last N log lines from stdout/stderr files (default: 80)
  print-unit      Print the rendered systemd unit to stdout
EOF
}

require_repo_files() {
  if [[ ! -x "${REPO_ROOT}/.venv/bin/uvicorn" ]]; then
    echo "Missing ${REPO_ROOT}/.venv/bin/uvicorn. Set up the virtual environment first." >&2
    exit 1
  fi
  if [[ ! -f "${REPO_ROOT}/.env" ]]; then
    echo "Missing ${REPO_ROOT}/.env. Create the runtime environment file first." >&2
    exit 1
  fi
}

render_unit() {
  cat <<EOF
[Unit]
Description=MUA Automation Platform (devbox HTTP)
After=network.target

[Service]
Type=simple
WorkingDirectory=${REPO_ROOT}
Environment=PYTHONPATH=${REPO_ROOT}/src
Environment=PATH=${REPO_ROOT}/.venv/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=${REPO_ROOT}/.env
ExecStart=${REPO_ROOT}/.venv/bin/uvicorn mua_platform.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=45
StandardOutput=append:${STDOUT_LOG}
StandardError=append:${STDERR_LOG}

[Install]
WantedBy=default.target
EOF
}

ensure_unit_installed() {
  if [[ ! -f "${UNIT_PATH}" ]]; then
    echo "Service unit not installed at ${UNIT_PATH}. Run '$(basename "$0") install' first." >&2
    exit 1
  fi
}

cmd="${1:-}"

case "${cmd}" in
  enable-linger)
    loginctl enable-linger "${USER}"
    loginctl show-user "${USER}" -p Linger
    ;;
  disable-linger)
    loginctl disable-linger "${USER}"
    loginctl show-user "${USER}" -p Linger
    ;;
  install)
    require_repo_files
    mkdir -p "${SYSTEMD_USER_DIR}" "${LOG_DIR}"
    render_unit > "${UNIT_PATH}"
    systemctl --user daemon-reload
    systemctl --user enable "${UNIT_NAME}"
    ;;
  uninstall)
    systemctl --user stop "${UNIT_NAME}" 2>/dev/null || true
    systemctl --user disable "${UNIT_NAME}" 2>/dev/null || true
    rm -f "${UNIT_PATH}"
    systemctl --user daemon-reload
    ;;
  start)
    ensure_unit_installed
    systemctl --user start "${UNIT_NAME}"
    ;;
  stop)
    ensure_unit_installed
    systemctl --user stop "${UNIT_NAME}"
    ;;
  restart)
    ensure_unit_installed
    systemctl --user restart "${UNIT_NAME}"
    ;;
  status)
    ensure_unit_installed
    systemctl --user status "${UNIT_NAME}" --no-pager
    ;;
  logs)
    lines="${2:-80}"
    mkdir -p "${LOG_DIR}"
    if [[ -f "${STDOUT_LOG}" ]]; then
      echo "== ${STDOUT_LOG} =="
      tail -n "${lines}" "${STDOUT_LOG}"
    else
      echo "No stdout log yet: ${STDOUT_LOG}"
    fi
    if [[ -f "${STDERR_LOG}" ]]; then
      echo
      echo "== ${STDERR_LOG} =="
      tail -n "${lines}" "${STDERR_LOG}"
    else
      echo
      echo "No stderr log yet: ${STDERR_LOG}"
    fi
    ;;
  print-unit)
    render_unit
    ;;
  *)
    usage
    exit 1
    ;;
esac
