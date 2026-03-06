#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_BIN="$REPO_ROOT/.venv/bin"

HOST="${SSE_HOST:-127.0.0.1}"
PORT="${SSE_PORT:-8001}"

cd "$SCRIPT_DIR"
exec "$VENV_BIN/uvicorn" app:app --host "$HOST" --port "$PORT"
