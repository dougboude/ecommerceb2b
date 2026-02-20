#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_BIN="$REPO_ROOT/.venv/bin"

SOCKET="${EMBEDDING_SOCKET_PATH:-/tmp/ecommerceb2b-embedding.sock}"
[ -S "$SOCKET" ] && rm "$SOCKET"
exec "$VENV_BIN/uvicorn" app:app --uds "$SOCKET"
