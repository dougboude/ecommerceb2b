#!/usr/bin/env bash
# qa/full_reset.sh
#
# Complete test environment reset: start the ecosystem, seed the database,
# and rebuild the vector index. Use this for a fully clean test session.
#
# Usage:
#   bash qa/full_reset.sh
#
# What it does:
#   1. Starts all three services via start.sh (embedding sidecar, SSE relay, Django)
#   2. Waits for the embedding sidecar to finish loading its model (~60-90s cold start)
#   3. Applies migrations and seeds the database
#   4. Rebuilds the ChromaDB vector index from the seed listings
#   5. Leaves start.sh running in the foreground (Ctrl-C to stop everything)
#
# If the ecosystem is already running, stop it first with Ctrl-C in the
# start.sh terminal, then run this script.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REPO_ROOT/.venv/bin/python"

# Load .env so all variables come from one place.
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

EMBEDDING_SOCKET="$EMBEDDING_SOCKET_PATH"
DJANGO_ADDR="$DJANGO_ADDR"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Full Reset — Niche Supply / Professional Demand"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$REPO_ROOT"

# ── Step 0: Verify Docker is available ────────────────────────────────────

if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running. Start Docker and try again."
    exit 1
fi

# ── Step 1: Start the ecosystem in the background ─────────────────────────

echo "Step 1 — Starting ecosystem (start.sh)..."
bash start.sh &
START_SH_PID=$!

# Forward Ctrl-C to start.sh so everything shuts down cleanly
trap 'kill $START_SH_PID 2>/dev/null; exit 0' INT TERM

# ── Step 2: Wait for the embedding sidecar to be healthy ──────────────────
# The SentenceTransformer model takes 60-90 seconds on first load.
# start.sh already waits internally, but we need to wait for it too
# before we can run rebuild_vector_index.

echo ""
echo "Step 2 — Waiting for all services to be healthy..."
echo "  (The embedding sidecar may take up to 2 minutes on first start)"
echo ""

MAX_WAIT=180
INTERVAL=3
ELAPSED=0

wait_for_url() {
    local label="$1" url="$2"
    shift 2
    local extra=("$@")
    printf "  Waiting for %-25s " "$label..."
    while ! curl -sf "${extra[@]}" "$url" > /dev/null 2>&1; do
        sleep $INTERVAL
        ELAPSED=$(( ELAPSED + INTERVAL ))
        if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
            echo "TIMEOUT"
            echo ""
            echo "ERROR: $label did not become healthy after ${MAX_WAIT}s."
            echo "Check logs/ for details."
            kill $START_SH_PID 2>/dev/null
            exit 1
        fi
        printf "."
    done
    echo " OK"
}

wait_for_url "embedding sidecar" "http://localhost/health" \
    --unix-socket "$EMBEDDING_SOCKET"
wait_for_url "Django"            "http://${DJANGO_ADDR}/"

echo ""

# ── Step 3: Seed the database ─────────────────────────────────────────────

echo "Step 3 — Checking Postgres is ready..."
if ! docker exec ecommerceb2b-postgres pg_isready -U postgres -q 2>/dev/null; then
    echo "ERROR: Postgres container is not responding. Check Docker logs."
    kill $START_SH_PID 2>/dev/null
    exit 1
fi
echo "  Postgres ready."
echo ""
echo "  Applying migrations and seeding database..."
"$PYTHON" manage.py migrate --run-syncdb
"$PYTHON" manage.py seed_test_data
echo ""

# ── Step 4: Rebuild the vector index ──────────────────────────────────────

echo "Step 4 — Rebuilding ChromaDB vector index..."
"$PYTHON" manage.py rebuild_vector_index
echo ""

# ── Done ──────────────────────────────────────────────────────────────────

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Environment ready.  http://${DJANGO_ADDR}"
echo "  Password for all seed accounts: Seedpass1!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Press Ctrl-C to stop the ecosystem when you are done."
echo ""

# Keep this script alive so Ctrl-C reaches the trap above
wait $START_SH_PID
