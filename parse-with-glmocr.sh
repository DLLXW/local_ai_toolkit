#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_FILE="${1:-}"
OUTPUT_DIR="${2:-./results}"
MONITOR_INTERVAL="${MONITOR_INTERVAL:-2}"

if [[ -z "${INPUT_FILE}" ]]; then
  echo "Usage: ./parse-with-glmocr.sh <input-file> [output-dir]" >&2
  exit 1
fi

if [[ ! -f "${INPUT_FILE}" ]]; then
  echo "Input file not found: ${INPUT_FILE}" >&2
  exit 1
fi

cd "${ROOT_DIR}/glm-ocr"
source .venv/bin/activate

"${ROOT_DIR}/run-with-monitor.sh" --interval "${MONITOR_INTERVAL}" -- \
  glmocr parse "${INPUT_FILE}" --output "${OUTPUT_DIR}"
