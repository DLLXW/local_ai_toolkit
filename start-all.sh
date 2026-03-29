#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="${ROOT_DIR}/.runtime"
PID_DIR="${RUNTIME_DIR}/pids"
LOG_DIR="${RUNTIME_DIR}/logs"

FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:5173}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
HEALTH_URL="${HEALTH_URL:-${BACKEND_URL}/api/health}"

mkdir -p "${PID_DIR}" "${LOG_DIR}"

usage() {
  cat <<'EOF'
用法:
  ./start-all.sh              一键启动全部服务
  ./start-all.sh start        一键启动全部服务
  ./start-all.sh stop         停止全部服务
  ./start-all.sh restart      重启全部服务
  ./start-all.sh status       查看服务状态
  ./start-all.sh logs         查看日志目录

说明:
  - 默认会启动 OCR 服务、翻译服务、后端、前端
  - 服务以后台方式运行，日志写入 ./.runtime/logs/
  - 首次启动若缺少 app/backend/.env，会自动从 .env.example 复制
EOF
}

service_pid_file() {
  printf "%s/%s.pid" "${PID_DIR}" "$1"
}

service_log_file() {
  printf "%s/%s.log" "${LOG_DIR}" "$1"
}

service_pattern() {
  case "$1" in
    ocr)
      printf "%s" "mlx_vlm.server --trust-remote-code"
      ;;
    translate)
      printf "%s" "llama-server -m ${MODEL_PATH:-${ROOT_DIR}/hy-mt/HY-MT1.5-1.8B-Q4_K_M.gguf}"
      ;;
    backend)
      printf "%s" "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
      ;;
    frontend)
      printf "%s" "vite --host 0.0.0.0 --port 5173"
      ;;
    *)
      return 1
      ;;
  esac
}

is_pid_running() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1
}

get_service_pid() {
  local name="$1"
  local pid_file
  pid_file="$(service_pid_file "${name}")"

  if [[ -f "${pid_file}" ]]; then
    tr -d '[:space:]' < "${pid_file}"
  fi
}

discover_service_pid() {
  local name="$1"
  local pattern
  pattern="$(service_pattern "${name}")" || return 0
  pgrep -f "${pattern}" | head -n 1 || true
}

ensure_backend_env() {
  local env_file="${ROOT_DIR}/app/backend/.env"
  local example_file="${ROOT_DIR}/app/backend/.env.example"

  if [[ ! -f "${env_file}" ]]; then
    cp "${example_file}" "${env_file}"
    echo "已自动创建后端配置: ${env_file}"
  fi
}

ensure_prerequisites() {
  local missing=0

  if [[ ! -x "${ROOT_DIR}/app/.venv/bin/uvicorn" ]]; then
    echo "缺少后端环境: ${ROOT_DIR}/app/.venv"
    echo "可执行: uv venv app/.venv && app/.venv/bin/pip install -e app/backend"
    missing=1
  fi

  if [[ ! -d "${ROOT_DIR}/app/frontend/node_modules" ]]; then
    echo "缺少前端依赖: ${ROOT_DIR}/app/frontend/node_modules"
    echo "可执行: (cd app/frontend && npm install)"
    missing=1
  fi

  if [[ ! -d "${ROOT_DIR}/glm-ocr-mlx-server" ]]; then
    echo "缺少 OCR 服务目录: ${ROOT_DIR}/glm-ocr-mlx-server"
    missing=1
  elif [[ ! -f "${ROOT_DIR}/glm-ocr-mlx-server/.venv/bin/activate" ]]; then
    echo "OCR 虚拟环境不存在: ${ROOT_DIR}/glm-ocr-mlx-server/.venv"
    missing=1
  fi

  if [[ ! -x "${LLAMA_SERVER_BIN:-$HOME/llama-b8470/llama-server}" ]]; then
    echo "llama-server 不存在: ${LLAMA_SERVER_BIN:-$HOME/llama-b8470/llama-server}"
    missing=1
  fi

  if [[ ! -f "${MODEL_PATH:-${ROOT_DIR}/hy-mt/HY-MT1.5-1.8B-Q4_K_M.gguf}" ]]; then
    echo "翻译模型不存在: ${MODEL_PATH:-${ROOT_DIR}/hy-mt/HY-MT1.5-1.8B-Q4_K_M.gguf}"
    missing=1
  fi

  if [[ "${missing}" -ne 0 ]]; then
    exit 1
  fi
}

start_service() {
  local name="$1"
  shift

  local pid_file log_file old_pid
  pid_file="$(service_pid_file "${name}")"
  log_file="$(service_log_file "${name}")"
  old_pid="$(get_service_pid "${name}")"

  if is_pid_running "${old_pid:-}"; then
    echo "${name}: 已在运行中 (PID ${old_pid})"
    return 0
  fi

  : > "${log_file}"
  nohup bash -lc "
    cd \"${ROOT_DIR}\"
    exec \"\$@\"
  " bash "$@" >>"${log_file}" 2>&1 < /dev/null &
  local pid=$!
  echo "${pid}" > "${pid_file}"
  echo "${name}: 已启动 (PID ${pid})"
}

stop_service() {
  local name="$1"
  local pid pattern
  pid="$(get_service_pid "${name}")"
  pattern="$(service_pattern "${name}")" || pattern=""

  if ! is_pid_running "${pid:-}"; then
    pid="$(discover_service_pid "${name}")"
  fi

  if [[ -z "${pid:-}" ]]; then
    rm -f "$(service_pid_file "${name}")"
    echo "${name}: 未运行"
    return 0
  fi

  if [[ -n "${pattern}" ]]; then
    pkill -TERM -f "${pattern}" >/dev/null 2>&1 || true
  fi
  kill "${pid}" >/dev/null 2>&1 || true

  for _ in {1..20}; do
    if ! is_pid_running "${pid}" && [[ -z "$(discover_service_pid "${name}")" ]]; then
      break
    fi
    sleep 0.5
  done

  if [[ -n "${pattern}" ]]; then
    pkill -KILL -f "${pattern}" >/dev/null 2>&1 || true
  fi

  if is_pid_running "${pid}"; then
    kill -9 "${pid}" >/dev/null 2>&1 || true
  fi

  rm -f "$(service_pid_file "${name}")"
  echo "${name}: 已停止"
}

print_service_status() {
  local name="$1"
  local pid
  pid="$(get_service_pid "${name}")"

  if ! is_pid_running "${pid:-}"; then
    pid="$(discover_service_pid "${name}")"
  fi

  if is_pid_running "${pid:-}"; then
    echo "${name}: 运行中 (PID ${pid})"
  else
    echo "${name}: 未运行"
  fi
}

open_frontend_if_possible() {
  if command -v open >/dev/null 2>&1; then
    open "${FRONTEND_URL}" >/dev/null 2>&1 || true
  fi
}

wait_for_backend_health() {
  local attempts=30

  for _ in $(seq 1 "${attempts}"); do
    if command -v curl >/dev/null 2>&1 && curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
      echo "后端健康检查通过: ${HEALTH_URL}"
      return 0
    fi
    sleep 1
  done

  echo "后端暂未通过健康检查，你可以稍后手动访问: ${HEALTH_URL}"
  return 1
}

start_all() {
  ensure_prerequisites
  ensure_backend_env

  start_service "ocr" ./start_ocr_server.sh
  start_service "translate" ./start-hy-mt.sh
  start_service "backend" ./app/scripts/dev_backend.sh
  start_service "frontend" ./app/scripts/dev_frontend.sh

  wait_for_backend_health || true
  open_frontend_if_possible

  cat <<EOF

全部启动命令已执行完成。
前端地址: ${FRONTEND_URL}
后端地址: ${BACKEND_URL}
健康检查: ${HEALTH_URL}
日志目录: ${LOG_DIR}

常用命令:
  ./start-all.sh status
  ./start-all.sh stop
  ./start-all.sh logs
EOF
}

show_logs() {
  echo "日志目录: ${LOG_DIR}"
  ls -1 "${LOG_DIR}" 2>/dev/null || true
}

COMMAND="${1:-start}"

case "${COMMAND}" in
  start)
    start_all
    ;;
  stop)
    stop_service "frontend"
    stop_service "backend"
    stop_service "translate"
    stop_service "ocr"
    ;;
  restart)
    "${BASH_SOURCE[0]}" stop
    "${BASH_SOURCE[0]}" start
    ;;
  status)
    print_service_status "ocr"
    print_service_status "translate"
    print_service_status "backend"
    print_service_status "frontend"
    ;;
  logs)
    show_logs
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "未知命令: ${COMMAND}"
    usage
    exit 1
    ;;
esac
