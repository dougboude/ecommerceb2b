# Design Document — PostgreSQL Database Migration

## Overview

This design translates the requirements into a concrete implementation
plan. The change surface is narrow: two new packages, a settings update,
a `.env.example` file, and documentation updates. No models, views, or
migrations are modified.

---

## 1. Package Changes

Add to `requirements.txt`:

```
psycopg2-binary>=2.9,<3
dj-database-url>=2.0,<3
```

Both packages are mature, stable, and have no sub-dependencies that
conflict with the existing stack.

---

## 2. Settings Change

Current `settings.py` has a hardcoded SQLite config:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

Replace with:

```python
import dj_database_url

_DATABASE_URL = os.environ.get("DATABASE_URL")

if _DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            _DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    import warnings
    warnings.warn(
        "DATABASE_URL is not set — falling back to SQLite. "
        "Set DATABASE_URL in your .env file to use PostgreSQL.",
        stacklevel=2,
    )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
```

Key decisions:
- `conn_max_age=600` enables persistent connections for Postgres — avoids
  a new TCP handshake on every request.
- `conn_health_checks=True` ensures stale connections are detected and
  recycled automatically (Django 4.1+).
- The `warnings.warn` call surfaces in the console at startup without
  being an error — dev can still run, but is clearly informed.

---

## 3. Environment File

**`.env.example`** (new file, committed to repo):

```bash
# Copy this file to .env and fill in values for your environment.
# .env is gitignored and must never be committed.

# Database
# Local dev default (Docker container — see CLAUDE.md for setup command)
DATABASE_URL=postgres://postgres:postgres@localhost:5432/ecommerceb2b

# Embedding sidecar
EMBEDDING_SOCKET_PATH=/tmp/ecommerceb2b-embedding.sock
EMBEDDING_SERVICE_TOKEN=dev-token-change-me

# SSE relay
SSE_SERVICE_URL=http://127.0.0.1:8001
SSE_SERVICE_TOKEN=dev-token-change-me
SSE_STREAM_SECRET=dev-stream-secret
```

This documents all environment variables in one place for the first time.
Values shown are the local dev defaults already used by the app — no
secrets are introduced.

---

## 4. Loading the .env File

Django does not load `.env` files automatically. Two options:

**Option A — Manual export (current approach, no change needed):**
Developers export variables in their shell before running Django. Works
today for the existing env vars.

**Option B — `python-dotenv` auto-load:**
Add `python-dotenv` to requirements and call `load_dotenv()` at the top
of `settings.py`. Removes the need for manual shell exports.

**Decision: Option B.** The project now has enough environment variables
that manual export is error-prone. `python-dotenv` is a single lightweight
dependency with no conflicts. Implementation:

```python
# settings.py — top of file, before any os.environ reads
from dotenv import load_dotenv
load_dotenv()  # loads .env from project root if present; no-op if absent
```

Add to `requirements.txt`:
```
python-dotenv>=1.0,<2
```

---

## 5. Local Development Setup

The developer workflow after this spec:

```bash
# 1. Start Postgres container (once — survives reboots with --restart unless-stopped)
docker run -d \
  --name ecommerceb2b-postgres \
  --restart unless-stopped \
  -e POSTGRES_DB=ecommerceb2b \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:16

# 2. Configure environment
cp .env.example .env
# DATABASE_URL is already set correctly in .env.example for this container

# 3. Install new packages
.venv/bin/pip install -r requirements.txt

# 4. Apply migrations to fresh Postgres DB
.venv/bin/python manage.py migrate

# 5. Seed test data
.venv/bin/python manage.py seed_test_data

# 6. Start the ecosystem as normal
bash start.sh
```

After initial setup, daily workflow is unchanged: `bash start.sh` or
`bash qa/full_reset.sh`.

---

## 6. Test Suite

No test code changes are expected. The test runner creates and destroys a
test database automatically — Django handles this identically for Postgres
and SQLite.

To verify the full suite against Postgres:

```bash
DATABASE_URL=postgres://postgres:postgres@localhost:5432/ecommerceb2b \
.venv/bin/python manage.py test
```

If `DATABASE_URL` is already set in `.env` and `python-dotenv` is loading
it, this simplifies to:

```bash
.venv/bin/python manage.py test
```

---

## 7. Documentation Updates

### `CLAUDE.md`
Add a "Local Database Setup" section under the Tech Stack heading:
- Postgres 16 required (Docker command)
- `.env` setup via `.env.example`
- Note that SQLite fallback produces a console warning

### `ai-docs/AGENT_NOTES.md`
Add a note:
- `DATABASE_URL` must be set; SQLite fallback is intentional but warns
- `python-dotenv` loads `.env` automatically — no manual export needed

### `qa/README.md`
Prepend a "Prerequisites" step to Quick Start:
- Postgres container must be running before `bash qa/full_reset.sh`

---

## 8. File Change Summary

| File | Change |
|------|--------|
| `requirements.txt` | Add `psycopg2-binary`, `dj-database-url`, `python-dotenv` |
| `config/settings.py` | Replace hardcoded SQLite with `dj-database-url` parse + SQLite fallback |
| `.env.example` | New file — all env vars with local dev defaults |
| `CLAUDE.md` | Add Local Database Setup section |
| `ai-docs/AGENT_NOTES.md` | Add DATABASE_URL and dotenv notes |
| `qa/README.md` | Add Postgres prerequisite to Quick Start |

Total: 6 files. No model, view, migration, template, or test changes.

---

## 9. Rollback Plan

If Postgres causes an unexpected issue, revert is a single settings change:
remove the `dj-database-url` block and restore the original SQLite
`DATABASES` dict. The SQLite `db.sqlite3` file is untouched by this spec.
