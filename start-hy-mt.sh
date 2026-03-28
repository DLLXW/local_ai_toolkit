#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLAMA_SERVER_BIN="${LLAMA_SERVER_BIN:-$HOME/llama-b8470/llama-server}"
MODEL_PATH="${MODEL_PATH:-${ROOT_DIR}/hy-mt/HY-MT1.5-1.8B-Q4_K_M.gguf}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8090}"
CTX_SIZE="${CTX_SIZE:-4096}"
GPU_LAYERS="${GPU_LAYERS:-999}"

if [[ ! -x "${LLAMA_SERVER_BIN}" ]]; then
  echo "llama-server not found: ${LLAMA_SERVER_BIN}" >&2
  echo "Set LLAMA_SERVER_BIN to your local llama-server binary." >&2
  exit 1
fi

if [[ ! -f "${MODEL_PATH}" ]]; then
  echo "Translation model not found: ${MODEL_PATH}" >&2
  echo "Set MODEL_PATH to your local HY-MT model file." >&2
  exit 1
fi

"${LLAMA_SERVER_BIN}" \
  -m "${MODEL_PATH}" \
  -ngl "${GPU_LAYERS}" \
  -c "${CTX_SIZE}" \
  --host "${HOST}" \
  --port "${PORT}"
