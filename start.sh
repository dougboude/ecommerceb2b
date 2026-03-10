#!/usr/bin/env bash
# start.sh — Start the full ecommerceb2b application ecosystem.
#
# Manages the complete lifecycle:
#   0. PostgreSQL container  (Docker / localhost:5432)
#   1. Embedding sidecar     (FastAPI / Unix socket)
#   2. SSE relay sidecar     (FastAPI / TCP :8001)
#   3. Django dev server     (manage.py runserver)
#
# Each process writes to its own log file under logs/.
# Press Ctrl-C once to stop everything (including Postgres).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$REPO_ROOT/logs"
VENV_BIN="$REPO_ROOT/.venv/bin"

# Load .env so all variables (including PGDATA_DIR) come from one place.
# set +u temporarily: SECRET_KEY and other values may contain $ characters
# that bash would try to expand as variables under -u (nounset).
if [ -f "$REPO_ROOT/.env" ]; then
    set +u
    set -a
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.env"
    set +a
    set -u
fi

mkdir -p "$LOG_DIR"

# ── Helpers ──────────────────────────────────────────────────────────────────

log() { echo "[start.sh] $*"; }

# Wait for a service health endpoint to respond OK.
# Usage: wait_for_health <label> <max_seconds> <url> [extra curl args...]
wait_for_health() {
    local label="$1" max="$2" url="$3"
    shift 3
    local extra_args=("$@")   # optional: e.g. --unix-socket <path>
    local attempts=0

    printf '[start.sh] Waiting for %s (up to %ds) ' "$label" "$max"
    while ! curl -sf "${extra_args[@]}" "$url" > /dev/null 2>&1; do
        attempts=$(( attempts + 1 ))
        if [ "$attempts" -ge "$max" ]; then
            echo " TIMEOUT"
            log "ERROR: $label did not become healthy after ${max}s — check logs."
            return 1
        fi
        printf '.'
        sleep 1
    done
    echo " OK"
}

kill_children() {
    # Clear traps first so re-entrant signals don't loop.
    trap '' EXIT INT TERM
    log "Shutting down..."
    rm -f "$PID_FILE"
    # Kill tail first so its buffered output doesn't pollute the shutdown display.
    kill ${TAIL_PID:-} 2>/dev/null || true
    sleep 0.2
    # SIGTERM each service individually (not the process group, so this script
    # stays alive long enough to wait and confirm they're gone).
    for entry in "embedding:${EMBEDDING_PID:-}" "SSE relay:${SSE_PID:-}" "Django:${DJANGO_PID:-}"; do
        local label="${entry%%:*}" pid="${entry##*:}"
        [ -n "$pid" ] && kill "$pid" 2>/dev/null && log "  Stopping $label (PID $pid)" || true
    done
    # Wait up to 8s for graceful exit.
    local deadline=$(( $(date +%s) + 8 ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        local any_alive=0
        for pid in ${EMBEDDING_PID:-} ${SSE_PID:-} ${DJANGO_PID:-}; do
            kill -0 "$pid" 2>/dev/null && { any_alive=1; break; }
        done
        [ "$any_alive" -eq 0 ] && break
        sleep 0.5
    done
    # SIGKILL anything still standing.
    for entry in "embedding:${EMBEDDING_PID:-}" "SSE relay:${SSE_PID:-}" "Django:${DJANGO_PID:-}"; do
        local label="${entry%%:*}" pid="${entry##*:}"
        [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null && log "  Force-killed $label (PID $pid)" || true
    done
    # Stop the Postgres container.
    if [ "$(docker ps -q -f name=^ecommerceb2b-postgres$)" ]; then
        log "  Stopping Postgres container..."
        docker stop ecommerceb2b-postgres > /dev/null
        log "  Postgres stopped."
    fi
    log "All processes stopped."
}
trap kill_children INT TERM
trap kill_children EXIT

# ── Config ────────────────────────────────────────────────────────────────────

EMBEDDING_SOCKET="$EMBEDDING_SOCKET_PATH"
SSE_HOST="$SSE_HOST"
SSE_PORT="$SSE_PORT"
DJANGO_ADDR="$DJANGO_ADDR"
PGDATA_DIR="$PGDATA_DIR"

PID_FILE="$LOG_DIR/start.pids"

# ── Tear down any leftover processes from a previous run ─────────────────────

# kill_pid: send SIGTERM to a PID and log it. No-ops if PID is not running.
kill_pid() {
    local pid="$1" label="$2"
    if kill -0 "$pid" 2>/dev/null; then
        log "  Stopping $label (PID $pid)"
        kill "$pid" 2>/dev/null || true
    fi
}

# kill_socket_owner: kill whatever process is holding a Unix socket file.
kill_socket_owner() {
    local socket="$1" label="$2"
    if [ -S "$socket" ]; then
        local pid
        pid=$(lsof -t "$socket" 2>/dev/null || true)
        if [ -n "$pid" ]; then
            kill_pid "$pid" "$label"
        fi
    fi
}

# kill_port_owner: kill whatever process is listening on a TCP port.
kill_port_owner() {
    local port="$1" label="$2"
    local pid
    pid=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill_pid "$pid" "$label"
    fi
}

DJANGO_PORT="${DJANGO_ADDR##*:}"
NEEDS_SLEEP=0

# Pass 1 — precise: use PID file if we started the ecosystem ourselves.
if [ -f "$PID_FILE" ]; then
    log "Found PID file — stopping previously managed processes..."
    while IFS=: read -r label pid; do
        kill_pid "$pid" "$label"
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    NEEDS_SLEEP=1
fi

# Pass 2 — fallback: check socket/ports regardless, catches manual starts.
kill_socket_owner "$EMBEDDING_SOCKET" "embedding sidecar"  && NEEDS_SLEEP=1 || true
kill_port_owner   "$SSE_PORT"         "SSE relay"           && NEEDS_SLEEP=1 || true
kill_port_owner   "$DJANGO_PORT"      "Django"              && NEEDS_SLEEP=1 || true

# Give processes a moment to release their resources before we rebind.
[ "$NEEDS_SLEEP" -eq 1 ] && sleep 1

# Clean up stale socket file.
rm -f "$EMBEDDING_SOCKET"

# ── 0. PostgreSQL container ───────────────────────────────────────────────────

start_postgres() {
    if ! docker info > /dev/null 2>&1; then
        log "ERROR: Docker is not running. Start Docker and try again."
        exit 1
    fi

    if [ ! "$(docker ps -aq -f name=^ecommerceb2b-postgres$)" ]; then
        log "Creating Postgres container (first time)..."
        docker run -d \
            --name ecommerceb2b-postgres \
            -e POSTGRES_DB=ecommerceb2b \
            -e POSTGRES_USER=postgres \
            -e POSTGRES_PASSWORD=postgres \
            -p 5432:5432 \
            -v "$PGDATA_DIR:/var/lib/postgresql/data" \
            postgres:16 > /dev/null
    elif [ ! "$(docker ps -q -f name=^ecommerceb2b-postgres$)" ]; then
        log "Starting existing Postgres container..."
        docker start ecommerceb2b-postgres > /dev/null
    else
        log "Postgres already running."
    fi

    printf '[start.sh] Waiting for Postgres (up to 30s) '
    local attempts=0
    until docker exec ecommerceb2b-postgres pg_isready -U postgres -q 2>/dev/null; do
        attempts=$(( attempts + 1 ))
        if [ "$attempts" -ge 30 ]; then
            echo " TIMEOUT"
            log "ERROR: Postgres did not become ready — check Docker logs."
            exit 1
        fi
        printf '.'
        sleep 1
    done
    echo " OK"
}

start_postgres

# ── 1. Embedding sidecar ─────────────────────────────────────────────────────

EMBEDDING_DIR="$REPO_ROOT/services/embedding"

log "Starting embedding sidecar  →  $LOG_DIR/embedding.log"
(
    cd "$EMBEDDING_DIR"
    "$VENV_BIN/uvicorn" app:app --uds "$EMBEDDING_SOCKET"
) >> "$LOG_DIR/embedding.log" 2>&1 &
EMBEDDING_PID=$!
wait_for_health "embedding sidecar" 150 "http://localhost/health" --unix-socket "$EMBEDDING_SOCKET"

# ── 2. SSE relay sidecar ─────────────────────────────────────────────────────

SSE_DIR="$REPO_ROOT/services/sse"

log "Starting SSE relay sidecar  →  $LOG_DIR/sse.log"
(
    cd "$SSE_DIR"
    "$VENV_BIN/uvicorn" app:app --host "$SSE_HOST" --port "$SSE_PORT"
) >> "$LOG_DIR/sse.log" 2>&1 &
SSE_PID=$!
wait_for_health "SSE relay" 20 "http://${SSE_HOST}:${SSE_PORT}/health"

# ── 3. Django dev server ──────────────────────────────────────────────────────

log "Starting Django dev server  →  $LOG_DIR/django.log  ($DJANGO_ADDR)"
(
    cd "$REPO_ROOT"
    "$VENV_BIN/python" manage.py runserver "$DJANGO_ADDR"
) >> "$LOG_DIR/django.log" 2>&1 &
DJANGO_PID=$!
wait_for_health "Django" 30 "http://${DJANGO_ADDR}/"

# ── Record PIDs for clean restart ────────────────────────────────────────────

printf '%s\n' "embedding:$EMBEDDING_PID" "SSE relay:$SSE_PID" "Django:$DJANGO_PID" > "$PID_FILE"

# ── Status ────────────────────────────────────────────────────────────────────

log ""
log "All three processes are running.  PIDs:"
log "  embedding : $EMBEDDING_PID  (log: logs/embedding.log)"
log "  sse       : $SSE_PID        (log: logs/sse.log)"
log "  django    : $DJANGO_PID     (log: logs/django.log)"
log ""
log "Django UI  →  http://$DJANGO_ADDR"
log ""
log "Press Ctrl-C to stop everything."
log "── live logs ────────────────────────────────────────────────────────────"

# ── Stream logs live ──────────────────────────────────────────────────────────

# Tail all three log files into this terminal so you can see what's happening.
tail -f "$LOG_DIR/embedding.log" "$LOG_DIR/sse.log" "$LOG_DIR/django.log" &
TAIL_PID=$!

# Block until a child exits (crash) or the user hits Ctrl-C.
wait -n 2>/dev/null || wait
