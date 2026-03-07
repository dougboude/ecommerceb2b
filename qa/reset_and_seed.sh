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
# Usage:
#   bash qa/reset_and_seed.sh
#   .venv/bin/python manage.py rebuild_vector_index   # if semantic search is needed
#
# The application does NOT need to be stopped. Django management commands are
# safe to run against a live SQLite dev database.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REPO_ROOT/.venv/bin/python"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Reset and Seed — Niche Supply / Professional Demand"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$REPO_ROOT"

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
