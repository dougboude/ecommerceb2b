#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_BIN="$REPO_ROOT/.venv/bin"

SERVICE_URL="${EMBEDDING_SERVICE_URL:-http://127.0.0.1:8002}"
HOST="${SERVICE_URL##*://}"; HOST="${HOST%%:*}"
PORT="${SERVICE_URL##*:}"
exec "$VENV_BIN/uvicorn" app:app --host "$HOST" --port "$PORT"
