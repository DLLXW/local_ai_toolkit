#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${ROOT_DIR}/app/.venv"
APP_DIR="${ROOT_DIR}/app/backend"

if [[ ! -x "${VENV_DIR}/bin/uvicorn" ]]; then
  echo "Missing backend environment at ${VENV_DIR}. Create it with uv first." >&2
  exit 1
fi

cd "${APP_DIR}"
"${VENV_DIR}/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000
