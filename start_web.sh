#!/usr/bin/env bash
set -euo pipefail

action="${1:-start}"
case "$action" in
  start|stop|restart|status) ;;
  *)
    echo "Usage: $0 [start|stop|restart|status]"
    exit 2
    ;;
esac

backend_port=8000
frontend_port=5173
backend_url="http://127.0.0.1:${backend_port}"
frontend_url="http://127.0.0.1:${frontend_port}"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
web_root="${repo_root}/web"
state_dir="${repo_root}/.web"
backend_pid_file="${state_dir}/backend.pid"
frontend_pid_file="${state_dir}/frontend.pid"
backend_log="${state_dir}/backend.log"
frontend_log="${state_dir}/frontend.log"

python_bin="${PYTHON_BIN:-C:/ProgramData/anaconda3/python.exe}"
if [[ ! -x "$python_bin" ]]; then
  python_bin="${PYTHON_BIN:-python}"
fi

port_pids() {
  local port="$1"
  netstat -ano -p tcp 2>/dev/null |
    awk -v needle=":${port}" '
      $0 ~ needle && ($0 ~ /LISTENING/ || $0 ~ /Listen/) {
        print $NF
      }
    ' |
    sort -u
}

is_port_listening() {
  [[ -n "$(port_pids "$1")" ]]
}

write_port_status() {
  local name="$1"
  local port="$2"
  local url="$3"
  local pids
  pids="$(port_pids "$port" | paste -sd, -)"
  if [[ -z "$pids" ]]; then
    echo "${name} stopped  ${url}"
    return
  fi
  echo "${name} running  ${url}  PID=${pids}"
}

wait_port_state() {
  local port="$1"
  local should_listen="$2"
  local timeout_seconds="${3:-12}"
  local deadline=$((SECONDS + timeout_seconds))
  while (( SECONDS < deadline )); do
    if is_port_listening "$port"; then
      [[ "$should_listen" == "true" ]] && return 0
    else
      [[ "$should_listen" == "false" ]] && return 0
    fi
    sleep 0.5
  done
  return 1
}

save_pid() {
  local pid_file="$1"
  local pid="$2"
  mkdir -p "$state_dir"
  printf '%s\n' "$pid" > "$pid_file"
}

managed_pid() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 0
  awk 'NR == 1 && $1 ~ /^[0-9]+$/ { print $1 }' "$pid_file"
}

remove_pid() {
  local pid_file="$1"
  rm -f "$pid_file"
}

kill_pid_tree() {
  local pid="$1"
  [[ -n "$pid" ]] || return 0
  taskkill //PID "$pid" //T //F >/dev/null 2>&1 || kill -TERM "$pid" >/dev/null 2>&1 || true
}

start_backend() {
  local pids
  pids="$(port_pids "$backend_port" | paste -sd, -)"
  if [[ -n "$pids" ]]; then
    echo "Backend  already running  ${backend_url}  PID=${pids}"
    return
  fi

  mkdir -p "$state_dir"
  (
    cd "$repo_root"
    PYTHONPATH=src "$python_bin" -m uvicorn icewine_web:app --host 127.0.0.1 --port "$backend_port" \
      > "$backend_log" 2>&1 &
    save_pid "$backend_pid_file" "$!"
  )
  echo "Backend  starting  ${backend_url}  launcher PID=$(managed_pid "$backend_pid_file")"
  if ! wait_port_state "$backend_port" true; then
    echo "Backend  start requested, but port ${backend_port} is not listening yet"
    echo "Backend  log: ${backend_log}"
  fi
}

start_frontend() {
  local pids
  pids="$(port_pids "$frontend_port" | paste -sd, -)"
  if [[ -n "$pids" ]]; then
    echo "Frontend already running  ${frontend_url}  PID=${pids}"
    return
  fi

  mkdir -p "$state_dir"
  (
    cd "$web_root"
    if [[ ! -d node_modules ]]; then
      npm install
    fi
    VITE_API_BASE_URL="" npm run dev -- --host 127.0.0.1 --port "$frontend_port" \
      > "$frontend_log" 2>&1 &
    save_pid "$frontend_pid_file" "$!"
  )
  echo "Frontend starting  ${frontend_url}  launcher PID=$(managed_pid "$frontend_pid_file")"
  if ! wait_port_state "$frontend_port" true; then
    echo "Frontend start requested, but port ${frontend_port} is not listening yet"
    echo "Frontend log: ${frontend_log}"
  fi
}

stop_service() {
  local name="$1"
  local port="$2"
  local pid_file="$3"
  local seeds
  seeds="$(
    {
      managed_pid "$pid_file"
      port_pids "$port"
    } | awk 'NF && !seen[$1]++'
  )"

  if [[ -z "$seeds" ]]; then
    echo "${name} already stopped"
    remove_pid "$pid_file"
    return
  fi

  while IFS= read -r pid; do
    [[ -n "$pid" ]] || continue
    echo "${name} stopping  PID=${pid}"
    kill_pid_tree "$pid"
  done <<< "$seeds"

  remove_pid "$pid_file"
  if ! wait_port_state "$port" false; then
    echo "${name} stop requested, but port ${port} is still listening"
  fi
}

start_web() {
  start_backend
  start_frontend
  echo
  show_status
}

stop_web() {
  stop_service "Frontend" "$frontend_port" "$frontend_pid_file"
  stop_service "Backend " "$backend_port" "$backend_pid_file"
}

show_status() {
  write_port_status "Backend " "$backend_port" "$backend_url"
  write_port_status "Frontend" "$frontend_port" "$frontend_url"
}

case "$action" in
  start)
    start_web
    ;;
  stop)
    stop_web
    show_status
    ;;
  restart)
    stop_web
    sleep 1
    start_web
    ;;
  status)
    show_status
    ;;
esac
