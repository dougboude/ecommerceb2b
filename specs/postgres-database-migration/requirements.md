# Requirements Document — PostgreSQL Database Migration

## Introduction

This spec replaces SQLite with PostgreSQL as the database engine for all
environments — local development and production. The goal is complete
dev/prod database parity so that testing in a lower environment provides
genuine confidence before deploying to production.

SQLite is permissive in ways Postgres is not (type coercion, constraint
enforcement, case sensitivity in queries). Running SQLite in dev while
targeting Postgres in prod is a known source of bugs that only surface at
deploy time. This spec eliminates that class of risk.

The change is additive to application code — no models, views, or business
logic are altered. Only the database driver, connection configuration, and
local development setup are affected.

This spec does not cover Dockerization, Railway deployment, or media file
storage migration. Those are separate specs.

---

## State Assumptions

| Assumption | Required State | Fail Condition |
|---|---|---|
| All foundation specs complete | Features 1–10 `EXEC` | Block if any of specs 1–10 are not `EXEC` |
| Docker available locally | `docker --version` succeeds | Warn; operator may use a native Postgres install instead |
| No pending migrations | `manage.py migrate --check` passes | Block if unapplied migrations exist before switching engines |

---

## Dependencies

- **New Python packages:** `psycopg2-binary`, `dj-database-url`
- **New dev tooling:** Docker (for local Postgres container) — or a native
  Postgres 16 install as an alternative
- **No model changes** — all existing migrations are database-agnostic and
  apply to Postgres unchanged
- **No application code changes** — views, forms, models, and tests are
  unaffected

---

## Glossary

- **DATABASE_URL:** A connection string in the format
  `postgres://user:password@host:port/dbname`, read by `dj-database-url`
  to configure Django's `DATABASES` setting.
- **dj-database-url:** A small utility library that parses a `DATABASE_URL`
  environment variable into a Django `DATABASES` dict.
- **psycopg2-binary:** The PostgreSQL adapter for Python. The `-binary`
  variant bundles its C dependencies and requires no system-level Postgres
  installation on the developer machine.
- **Dev/prod parity:** The principle that local development and production
  use the same database engine, version, and configuration so test results
  are trustworthy.

---

## Requirements

### Requirement 1: Python Dependencies

**User Story:** As a developer, I want the correct database driver and
configuration library installed so Django can connect to PostgreSQL.

#### Acceptance Criteria

1. `psycopg2-binary>=2.9` SHALL be added to `requirements.txt`.
2. `dj-database-url>=2.0` SHALL be added to `requirements.txt`.
3. `python-dotenv>=1.0` SHALL also be added to `requirements.txt`.
4. All three packages SHALL be installable via `.venv/bin/pip install -r requirements.txt`
   without errors on the development platform.

---

### Requirement 2: Django Database Configuration

**User Story:** As a developer, I want Django to read the database
connection from an environment variable so the same codebase works in
dev, CI, and production without code changes.

#### Acceptance Criteria

1. `settings.py` SHALL use `dj-database-url` to parse a `DATABASE_URL`
   environment variable into `DATABASES["default"]`.
2. If `DATABASE_URL` is not set, `settings.py` SHALL raise
   `django.core.exceptions.ImproperlyConfigured` immediately at startup
   with a clear message directing the developer to copy `.env.example`
   to `.env`. There is no SQLite fallback.
3. The `DATABASE_URL` variable SHALL be loaded via `python-dotenv`'s
   `load_dotenv()` call at the top of `settings.py`, before any
   `os.environ` reads.
4. `CONN_MAX_AGE` SHALL be set to `600` (seconds) to enable persistent
   connections. `conn_health_checks=True` SHALL also be set to recycle
   stale connections automatically.

---

### Requirement 3: Local Development Setup — Postgres via Docker

**User Story:** As a developer, I want a documented, repeatable way to
run a local Postgres instance that matches the production engine so I can
develop and test against the same database.

#### Acceptance Criteria

1. A `.env.example` file SHALL exist at the project root documenting all
   supported environment variables, including `DATABASE_URL` with the
   canonical local dev value:
   ```
   DATABASE_URL=postgres://postgres:postgres@localhost:5432/ecommerceb2b
   ```
2. `README.md` or `CLAUDE.md` SHALL include a "Local Postgres Setup"
   section with the exact Docker command to start a local Postgres 16
   container:
   ```bash
   docker run -d \
     --name ecommerceb2b-postgres \
     -e POSTGRES_DB=ecommerceb2b \
     -e POSTGRES_USER=postgres \
     -e POSTGRES_PASSWORD=postgres \
     -p 5432:5432 \
     postgres:16
   ```
3. The documentation SHALL include the steps to initialise the database
   after starting the container:
   ```bash
   cp .env.example .env          # then set DATABASE_URL
   .venv/bin/python manage.py migrate
   .venv/bin/python manage.py seed_test_data
   ```
4. `.env` SHALL be listed in `.gitignore` (it already is — verify only).
5. `.env.example` SHALL be committed to the repository and SHALL NOT
   contain real secrets.

---

### Requirement 4: Migration Integrity on PostgreSQL

**User Story:** As a developer, I want all existing Django migrations to
apply cleanly to a fresh Postgres database so the schema is correct and
complete.

#### Acceptance Criteria

1. Running `.venv/bin/python manage.py migrate` against a fresh Postgres
   database SHALL complete with zero errors.
2. Running `.venv/bin/python manage.py migrate --check` after the above
   SHALL report no pending migrations.
3. No new migrations SHALL be created as part of this spec. The existing
   migration history is database-agnostic and requires no modification.
4. The `seed_test_data` management command SHALL execute successfully
   against Postgres and produce the correct seed dataset.

---

### Requirement 5: Test Suite Compatibility

**User Story:** As a developer, I want the existing test suite to pass
against PostgreSQL so I can trust that the switch has not broken any
existing behaviour.

#### Acceptance Criteria

1. All existing tests SHALL pass against Postgres. With `python-dotenv`
   loading `.env`, the test command is simply:
   ```bash
   .venv/bin/python manage.py test
   ```
2. Tests that use `@override_settings` for storage SHALL continue to work
   unchanged — no test code modifications are expected.
3. If any test fails against Postgres, the failure SHALL be treated as a
   bug to fix before this spec is marked `EXEC`. There is no acceptable
   state where a test passes against one engine but not the other.
4. The CI test run (if configured) SHALL be updated to run against Postgres.

---

### Requirement 6: Developer Documentation Updates

**User Story:** As an agent or developer onboarding to this project, I
want the setup documentation to reflect the Postgres requirement clearly
so I don't accidentally run against SQLite without realising it.

#### Acceptance Criteria

1. `CLAUDE.md` SHALL be updated to document Postgres as the required
   database engine for development, including the Docker command and
   `.env` setup.
2. `ai-docs/AGENT_NOTES.md` SHALL be updated to note that `DATABASE_URL`
   must be set via `.env` and that a missing value raises
   `ImproperlyConfigured` at startup.
3. `qa/README.md` SHALL be updated: `bash start.sh` handles Postgres
   automatically — no separate Docker step needed. A "Wiping the Database"
   note SHALL be added explaining `rm -rf data/pgdata/`.

---

### Requirement 7: Ecosystem Lifecycle — start.sh and stop.sh

**User Story:** As a developer, I want `start.sh` to bring up the entire
ecosystem including the database, and `stop.sh` to shut everything down
completely, so there is no ambiguity about what is running.

#### Acceptance Criteria

1. `start.sh` SHALL manage the Postgres container lifecycle:
   - If the container does not exist, create it with the bind mount to
     `data/pgdata/` and wait for it to be ready before proceeding.
   - If the container exists but is stopped, start it and wait for ready.
   - If the container is already running, proceed without action.
2. `start.sh` SHALL poll until Postgres accepts connections before starting
   Django. If Postgres does not become ready within a reasonable timeout,
   `start.sh` SHALL exit with a clear error message.
3. `stop.sh` SHALL stop the Postgres container (`docker stop
   ecommerceb2b-postgres`) as part of its shutdown sequence. When
   `stop.sh` exits, no part of the ecosystem SHALL remain running.
4. The Postgres container SHALL use a bind mount to `data/pgdata/` (a
   developer-owned directory inside the project) for data persistence.
   Docker-managed named volumes SHALL NOT be used.
5. `--restart unless-stopped` SHALL NOT be set on the container. `start.sh`
   owns the lifecycle — Postgres starts and stops only when explicitly told to.

---

### Requirement 8: Seed Script Preflight Checks

**User Story:** As a developer running QA reset scripts, I want a clear
error if Postgres is not running rather than a cryptic Django crash.

#### Acceptance Criteria

1. `qa/full_reset.sh` SHALL verify the Postgres container is running and
   accepting connections before executing any Django management commands.
   If Postgres is not ready, the script SHALL exit with a clear message.
2. `qa/reset_and_seed.sh` SHALL perform the same preflight check.
3. The preflight check SHALL use `docker exec ecommerceb2b-postgres
   pg_isready` or equivalent — not a raw TCP check.

---

### Requirement 9: Scope Boundaries

The following are explicitly **out of scope** for this spec:

1. Dockerization of Django, the embedding sidecar, or the SSE relay —
   separate spec.
2. Railway deployment configuration — separate spec.
3. Media file migration to object storage (S3/R2) — separate spec.
4. Embedding sidecar UDS → TCP migration — separate spec.
5. Database connection pooling beyond `CONN_MAX_AGE` (e.g. PgBouncer) —
   post-launch infrastructure concern.
6. Read replicas, backups, or any production database operations policy —
   out of scope for this spec; addressed at deployment time.
