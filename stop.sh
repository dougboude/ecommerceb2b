#!/usr/bin/env bash
# stop.sh — Stop the ecommerceb2b application ecosystem.
#
# Stops all components: Django, SSE relay, embedding sidecar, and the
# Postgres Docker container. When this script exits, nothing is running.
#
# Works regardless of how the ecosystem was started:
#   - If started via start.sh: uses the PID file for precise targeting.
#   - Fallback: finds and kills anything holding the known socket/ports.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$REPO_ROOT/logs"

log() { echo "[stop.sh] $*"; }

kill_pid() {
    local pid="$1" label="$2"
    if ! kill -0 "$pid" 2>/dev/null; then
        return 1  # not running
    fi
    log "  Stopping $label (PID $pid)"
    kill "$pid" 2>/dev/null || true
    # Wait up to 8s for graceful exit, then SIGKILL.
    local deadline=$(( $(date +%s) + 8 ))
    printf '  [stop.sh] Waiting for %s ' "$label"
    while kill -0 "$pid" 2>/dev/null && [ "$(date +%s)" -lt "$deadline" ]; do
        printf '.'
        sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo " (force killing)"
        kill -9 "$pid" 2>/dev/null || true
    else
        echo " done"
    fi
    return 0
}

kill_socket_owner() {
    local socket="$1" label="$2"
    if [ -S "$socket" ]; then
        local pid
        pid=$(lsof -t "$socket" 2>/dev/null || true)
        if [ -n "$pid" ]; then
            kill_pid "$pid" "$label"
            return 0
        fi
    fi
    return 1
}

kill_port_owner() {
    local port="$1" label="$2"
    local pid
    pid=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill_pid "$pid" "$label"
        return 0
    fi
    return 1
}

# ── Config (must match start.sh defaults) ────────────────────────────────────

EMBEDDING_SOCKET="${EMBEDDING_SOCKET_PATH:-/tmp/ecommerceb2b-embedding.sock}"
SSE_PORT="${SSE_PORT:-8001}"
DJANGO_ADDR="${DJANGO_ADDR:-127.0.0.1:8000}"
DJANGO_PORT="${DJANGO_ADDR##*:}"

PID_FILE="$LOG_DIR/start.pids"

# ── Pass 1: PID file ──────────────────────────────────────────────────────────

KILLED=0

if [ -f "$PID_FILE" ]; then
    log "Found PID file — stopping managed processes..."
    while read -r pid; do
        kill_pid "$pid" "managed process" && KILLED=$(( KILLED + 1 )) || true
    done < "$PID_FILE"
    rm -f "$PID_FILE"
fi

# ── Pass 2: socket/port fallback ─────────────────────────────────────────────

kill_socket_owner "$EMBEDDING_SOCKET" "embedding sidecar" && KILLED=$(( KILLED + 1 )) || true
kill_port_owner   "$SSE_PORT"         "SSE relay"          && KILLED=$(( KILLED + 1 )) || true
kill_port_owner   "$DJANGO_PORT"      "Django"             && KILLED=$(( KILLED + 1 )) || true

# ── Clean up ─────────────────────────────────────────────────────────────────

rm -f "$EMBEDDING_SOCKET"

# ── Postgres container ────────────────────────────────────────────────────────

if [ "$(docker ps -q -f name=^ecommerceb2b-postgres$)" ]; then
    log "Stopping Postgres container..."
    docker stop ecommerceb2b-postgres > /dev/null
    KILLED=$(( KILLED + 1 ))
else
    log "Postgres container is not running."
fi

# ── Summary ──────────────────────────────────────────────────────────────────

if [ "$KILLED" -eq 0 ]; then
    log "Nothing was running."
else
    log "Done — stopped $KILLED process(es)."
fi
