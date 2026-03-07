#!/usr/bin/env bash
# qa/reset_and_seed.sh
#
# Wipe all application data, apply migrations, and install the seed dataset.
# Run this before any manual test session to get a clean, known-good state.
#
# Usage:
#   bash qa/reset_and_seed.sh
#
# The application does NOT need to be stopped before running this. Django's
# management commands are safe to run against a live SQLite dev database.

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
echo "The app is ready for manual testing."
echo "Start the full ecosystem with:  bash start.sh"
echo ""
