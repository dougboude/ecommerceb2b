#!/usr/bin/env bash
# qa/reset_and_seed.sh
#
# Wipe all application data, apply migrations, and install the seed dataset.
#
# NOTE: This script resets the Django database only. It does NOT rebuild the
# ChromaDB vector index used for semantic search on the Discover page.
# For a complete reset (database + vector index), use qa/full_reset.sh instead.
#
# Use this script when:
#   - The ecosystem is already running and you want to re-seed without restarting
#   - You want a fast DB-only reset during development
#
# Requires: Postgres container must be running (start.sh manages this).
#
# Usage:
#   bash qa/reset_and_seed.sh
#   .venv/bin/python manage.py rebuild_vector_index   # if semantic search is needed

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REPO_ROOT/.venv/bin/python"

# Load .env so all variables come from one place.
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.env"
    set +a
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Reset and Seed — Niche Supply / Professional Demand"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$REPO_ROOT"

echo "Checking Postgres..."
if ! docker exec ecommerceb2b-postgres pg_isready -U postgres -q 2>/dev/null; then
    echo "ERROR: Postgres is not running. Run 'bash start.sh' first."
    exit 1
fi
echo "Postgres ready."
echo ""

echo "Step 1/3 — Applying migrations..."
"$PYTHON" manage.py migrate --run-syncdb
echo ""

echo "Step 2/3 — Installing seed data..."
"$PYTHON" manage.py seed_test_data
echo ""

echo "Step 3/3 — Done."
echo ""
echo "Database seeded. Next steps:"
echo "  Full reset with vector index:  bash qa/full_reset.sh"
echo "  Start ecosystem only:          bash start.sh"
echo "  Rebuild vector index only:     .venv/bin/python manage.py rebuild_vector_index"
echo ""
