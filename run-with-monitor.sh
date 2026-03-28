#!/usr/bin/env bash

set -euo pipefail

INTERVAL_SECONDS=2

usage() {
  cat <<'EOF'
用法:
  ./run-with-monitor.sh [--interval 秒] -- <command> [args...]

示例:
  ./run-with-monitor.sh --interval 1 -- glmocr parse ./demo.pdf --output ./results
EOF
}

parse_gpu_util() {
  # Apple Silicon/macOS: 通过 IOAccelerator 的 PerformanceStatistics 读取设备利用率。
  local util
  util="$(
    ioreg -r -d 1 -w 0 -c IOAccelerator 2>/dev/null \
      | /usr/bin/perl -ne 'if (/"Device Utilization %"\s*=\s*([0-9.]+)/) { print $1; exit }'
  )"
  if [[ -n "${util}" ]]; then
    printf "%s%%" "${util}"
  else
    printf "N/A"
  fi
}

parse_system_snapshot() {
  local top_snapshot cpu_line mem_line
  top_snapshot="$(top -l 1 -n 0)"
  cpu_line="$(printf "%s\n" "${top_snapshot}" | /usr/bin/awk '/^CPU usage:/{print; exit}')"
  mem_line="$(printf "%s\n" "${top_snapshot}" | /usr/bin/awk '/^PhysMem:/{print; exit}')"
  printf "%s|%s" "${cpu_line:-CPU usage: N/A}" "${mem_line:-PhysMem: N/A}"
}

parse_process_snapshot() {
  local pid="$1"
  local raw cpu_pct mem_pct rss_kb rss_mb

  raw="$(ps -p "${pid}" -o %cpu=,%mem=,rss= 2>/dev/null | /usr/bin/awk 'NR==1{print $1,$2,$3}')"
  if [[ -z "${raw}" ]]; then
    printf "proc CPU=N/A MEM=N/A RSS=N/A"
    return
  fi

  cpu_pct="$(printf "%s" "${raw}" | /usr/bin/awk '{print $1}')"
  mem_pct="$(printf "%s" "${raw}" | /usr/bin/awk '{print $2}')"
  rss_kb="$(printf "%s" "${raw}" | /usr/bin/awk '{print $3}')"
  rss_mb="$(/usr/bin/awk -v kb="${rss_kb}" 'BEGIN { printf "%.1f", kb/1024 }')"

  printf "proc CPU=%s%% MEM=%s%% RSS=%sMB" "${cpu_pct}" "${mem_pct}" "${rss_mb}"
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval)
      if [[ $# -lt 2 ]]; then
        echo "缺少 --interval 的参数值"
        exit 1
      fi
      INTERVAL_SECONDS="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "未知参数: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ $# -eq 0 ]]; then
  echo "缺少待执行命令"
  usage
  exit 1
fi

START_TS="$(date +%s)"

echo "=== 监控开始 ==="
echo "命令: $*"
echo "采样间隔: ${INTERVAL_SECONDS}s"
echo

"$@" &
TARGET_PID=$!

cleanup() {
  if kill -0 "${TARGET_PID}" >/dev/null 2>&1; then
    kill "${TARGET_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup INT TERM

while kill -0 "${TARGET_PID}" >/dev/null 2>&1; do
  now="$(date '+%H:%M:%S')"
  sys_snapshot="$(parse_system_snapshot)"
  cpu_line="${sys_snapshot%%|*}"
  mem_line="${sys_snapshot#*|}"
  gpu_line="GPU: $(parse_gpu_util)"
  proc_line="$(parse_process_snapshot "${TARGET_PID}")"

  echo "[${now}] ${cpu_line}"
  echo "[${now}] ${mem_line}"
  echo "[${now}] ${gpu_line}"
  echo "[${now}] ${proc_line}"
  echo "----------------------------------------"

  sleep "${INTERVAL_SECONDS}"
done

set +e
wait "${TARGET_PID}"
COMMAND_EXIT_CODE=$?
set -e

END_TS="$(date +%s)"
ELAPSED_SECONDS=$((END_TS - START_TS))
ELAPSED_H=$((ELAPSED_SECONDS / 3600))
ELAPSED_M=$(((ELAPSED_SECONDS % 3600) / 60))
ELAPSED_S=$((ELAPSED_SECONDS % 60))

echo
echo "=== 任务结束 ==="
echo "退出码: ${COMMAND_EXIT_CODE}"
printf "总耗时: %02d:%02d:%02d (%ss)\n" "${ELAPSED_H}" "${ELAPSED_M}" "${ELAPSED_S}" "${ELAPSED_SECONDS}"

exit "${COMMAND_EXIT_CODE}"
