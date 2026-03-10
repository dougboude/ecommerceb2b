# Design Document — PostgreSQL Database Migration

## Overview

This design translates the requirements into a concrete implementation
plan. The change surface is narrow: three new packages, a settings update,
a `.env.example` file, updates to `start.sh` and `stop.sh`, seed script
preflight checks, and documentation updates. No models, views, or
migrations are modified.

---

## 1. Package Changes

Add to `requirements.txt`:

```
psycopg2-binary>=2.9,<3
dj-database-url>=2.0,<3
python-dotenv>=1.0,<2
```

All three packages are mature, stable, and have no sub-dependencies that
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
# settings.py — top of file, before any os.environ reads
from dotenv import load_dotenv
load_dotenv()  # loads .env from project root if present; no-op if absent

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

_DATABASE_URL = os.environ.get("DATABASE_URL")

if not _DATABASE_URL:
    raise ImproperlyConfigured(
        "DATABASE_URL environment variable is not set. "
        "Copy .env.example to .env and configure your Postgres connection."
    )

DATABASES = {
    "default": dj_database_url.parse(
        _DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}
```

Key decisions:
- `python-dotenv` loads `.env` automatically — no manual shell exports needed.
- Missing `DATABASE_URL` raises `ImproperlyConfigured` immediately at startup —
  no silent fallback, no SQLite, no ambiguity about which database is in use.
- `conn_max_age=600` enables persistent connections — avoids a new TCP
  handshake on every request.
- `conn_health_checks=True` ensures stale connections are detected and
  recycled automatically (Django 4.1+).

---

## 3. Environment File

**`.env.example`** (new file, committed to repo):

```bash
# Copy this file to .env and fill in values for your environment.
# .env is gitignored and must never be committed.

# Database
# Local dev default — matches the Docker container started by start.sh
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

## 4. Data Persistence — Bind Mount

The Postgres container stores its data in `data/pgdata/` — a real directory
inside the project folder, owned and managed by the developer. Docker mounts
this directory into the container at `/var/lib/postgresql/data`.

This is a **bind mount** (not a Docker-managed named volume). The difference:
- A named volume is managed by Docker — you can't see or back it up without
  Docker commands.
- A bind mount is a plain directory on your filesystem — you can see it,
  back it up, or delete it like any other folder.

`data/pgdata/` sits alongside the existing `data/chroma/` directory. Both
are gitignored.

Add to `.gitignore`:
```
data/pgdata/
```

To wipe the database completely and start fresh, delete the directory:
```bash
rm -rf data/pgdata/
```
The next `start.sh` run will re-initialise it from scratch.

---

## 5. start.sh Changes

`start.sh` must manage the full ecosystem including Postgres. The updated
logic for the Postgres container:

```
if container "ecommerceb2b-postgres" does not exist:
    docker run (first-time setup — creates container + data directory)
elif container exists but is stopped:
    docker start ecommerceb2b-postgres
else:
    container is already running — do nothing
```

After starting the container, `start.sh` polls until Postgres accepts
connections (via `pg_isready` or a simple `psql` ping) before proceeding
to start Django. This prevents Django from crashing on startup if Postgres
hasn't finished initialising.

Full Docker run command used by `start.sh`:

```bash
docker run -d \
  --name ecommerceb2b-postgres \
  -e POSTGRES_DB=ecommerceb2b \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  -v "$(pwd)/data/pgdata:/var/lib/postgresql/data" \
  postgres:16
```

Note: `--restart unless-stopped` is intentionally omitted. `start.sh`
owns the lifecycle — Postgres starts when you say start, stops when you
say stop. No background auto-restart behaviour.

---

## 6. stop.sh Changes

`stop.sh` must stop the Postgres container as part of its shutdown
sequence. When `stop.sh` completes, nothing in the ecosystem is running.

```bash
docker stop ecommerceb2b-postgres
```

The container is stopped, not removed — data in `data/pgdata/` is
untouched. The next `start.sh` will start it again cleanly.

---

## 7. Seed Script Preflight Checks

Both `qa/full_reset.sh` and `qa/reset_and_seed.sh` run Django management
commands that require a live database connection. Both scripts must verify
Postgres is reachable before proceeding, with a clear error message if not.

Preflight check pattern (shared by both scripts):

```bash
echo "Checking Postgres..."
until docker exec ecommerceb2b-postgres pg_isready -U postgres -q; do
  echo "  Waiting for Postgres..."
  sleep 1
done
echo "Postgres ready."
```

If the container is not running at all, `docker exec` fails immediately
with a clear message — no silent hang.

---

## 8. Test Suite

No test code changes are expected. Django's test runner creates and
destroys a test database automatically, identically for Postgres and SQLite.

With `python-dotenv` loading `.env`, running the test suite is simply:

```bash
.venv/bin/python manage.py test
```

The test runner uses the `DATABASE_URL` from `.env` to connect to Postgres,
creates a `test_ecommerceb2b` database, runs all tests, and drops it.

---

## 9. First-Time Setup Workflow

For a developer setting up the project for the first time after this spec:

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Install new packages
.venv/bin/pip install -r requirements.txt

# 3. Start the full ecosystem (start.sh creates the Postgres container
#    on first run, runs migrate, then starts all services)
bash start.sh
```

`start.sh` handles container creation, health check, and migration on
first run. The developer does not need to run `docker run` manually.

Daily workflow after initial setup is unchanged: `bash start.sh` /
`bash stop.sh` / `bash qa/full_reset.sh`.

---

## 10. Documentation Updates

### `CLAUDE.md`
- Add a "Local Database Setup" section: bind mount path, first-time setup,
  how to wipe data, note that `start.sh` manages the container lifecycle.
- Update the QA scripts table to note the Postgres prerequisite.

### `ai-docs/AGENT_NOTES.md`
- Note that `DATABASE_URL` must be set; SQLite fallback warns at startup.
- Note that `python-dotenv` loads `.env` automatically.
- Note that `data/pgdata/` is the Postgres data directory — do not delete
  it unintentionally.

### `qa/README.md`
- Update Quick Start: `bash start.sh` already handles Postgres — no
  separate Docker step needed.
- Add a "Wiping the Database" note: `rm -rf data/pgdata/` then
  `bash qa/full_reset.sh`.

---

## 11. File Change Summary

| File | Change |
|------|--------|
| `requirements.txt` | Add `psycopg2-binary`, `dj-database-url`, `python-dotenv` |
| `config/settings.py` | `load_dotenv()` + `dj-database-url` parse + SQLite fallback |
| `.env.example` | New file — all env vars with local dev defaults |
| `.gitignore` | Add `data/pgdata/` |
| `start.sh` | Add Postgres container lifecycle management + health check |
| `stop.sh` | Add `docker stop ecommerceb2b-postgres` |
| `qa/full_reset.sh` | Add Postgres preflight check |
| `qa/reset_and_seed.sh` | Add Postgres preflight check |
| `CLAUDE.md` | Add Local Database Setup section |
| `ai-docs/AGENT_NOTES.md` | Add DATABASE_URL, dotenv, and pgdata notes |
| `qa/README.md` | Update Quick Start and add wipe instructions |

Total: 11 files. No model, view, migration, template, or test changes.

---

## 12. Rollback Plan

If Postgres causes an unexpected issue, revert is a single settings change:
restore the original hardcoded SQLite `DATABASES` dict and remove the
`dj-database-url` block. The SQLite `db.sqlite3` file is untouched by this
spec. `start.sh` and `stop.sh` changes can be reverted independently — the
Postgres container can be stopped manually with `docker stop ecommerceb2b-postgres`.
