#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="${SERVER_DIR:-${ROOT_DIR}/glm-ocr-mlx-server}"

if [[ ! -d "${SERVER_DIR}" ]]; then
  echo "OCR server directory not found: ${SERVER_DIR}" >&2
  echo "Set SERVER_DIR to your local glm-ocr-mlx-server path." >&2
  exit 1
fi

cd "${SERVER_DIR}"
source .venv/bin/activate
mlx_vlm.server --trust-remote-code
