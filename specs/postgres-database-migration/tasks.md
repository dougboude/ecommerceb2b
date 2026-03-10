# Implementation Plan — PostgreSQL Database Migration

## Pre-Execution Gate Checklist

Before any task begins, confirm all prior specs are `EXEC`:

```bash
# Confirm Features 1–10 are complete
grep -E "Status:" specs/SPEC_ORDER.md | head -12
```

All entries through spec 10 must show `EXEC`. If any do not, stop.

---

## Phase 1: Packages and Configuration

### Group 1 — Python Dependencies

- [ ] 1.1 Add new packages to `requirements.txt`
  - Add `psycopg2-binary>=2.9,<3`
  - Add `dj-database-url>=2.0,<3`
  - Add `python-dotenv>=1.0,<2`
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 1.2 Install new packages into the virtual environment
  - Run `.venv/bin/pip install -r requirements.txt`
  - Confirm `import psycopg2`, `import dj_database_url`, `import dotenv` all succeed
  - _Requirements: 1.4_

---

### Group 2 — Environment File

- [ ] 2.1 Create `.env.example` at project root
  - Include all environment variables with local dev defaults:
    ```bash
    # Copy this file to .env and fill in values for your environment.
    # .env is gitignored and must never be committed.

    # Database
    DATABASE_URL=postgres://postgres:postgres@localhost:5432/ecommerceb2b

    # Embedding sidecar
    EMBEDDING_SOCKET_PATH=/tmp/ecommerceb2b-embedding.sock
    EMBEDDING_SERVICE_TOKEN=dev-token-change-me

    # SSE relay
    SSE_SERVICE_URL=http://127.0.0.1:8001
    SSE_SERVICE_TOKEN=dev-token-change-me
    SSE_STREAM_SECRET=dev-stream-secret
    ```
  - Confirm `.env` is already in `.gitignore` (it is — verify only)
  - _Requirements: 3.1, 3.5_

- [ ] 2.2 Add `data/pgdata/` to `.gitignore`
  - Add entry under the existing `data/chroma/` line
  - _Requirements: 3.4 (implied by design §4)_

---

### Group 3 — Django Settings

- [ ] 3.1 Update `config/settings.py` — load `.env` and configure database
  - Add at the very top of the file, before any `os.environ` reads:
    ```python
    from dotenv import load_dotenv
    load_dotenv()
    ```
  - Replace the existing hardcoded `DATABASES` dict with:
    ```python
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
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 3.2 Verify settings load correctly
  - Copy `.env.example` to `.env` if not already done
  - Run `.venv/bin/python manage.py check`
  - Expected: system check passes with no errors
  - _Requirements: 2.1_

---

## Phase 2: Postgres Container and Data Directory

### Group 4 — First-Time Container Setup

- [ ] 4.1 Create `data/pgdata/` directory
  - Run `mkdir -p data/pgdata`
  - Confirm it exists alongside `data/chroma/`
  - _Requirements: 7.4_

- [ ] 4.2 Run Postgres container for the first time
  - From the project root:
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
  - Wait for the container to be ready:
    ```bash
    until docker exec ecommerceb2b-postgres pg_isready -U postgres -q; do
      echo "Waiting for Postgres..."; sleep 1
    done
    echo "Postgres ready."
    ```
  - _Requirements: 7.1, 7.4_

---

### Group 5 — Schema and Seed

- [ ] 5.1 Apply all migrations to the fresh Postgres database
  - Run `.venv/bin/python manage.py migrate`
  - Expected: all migrations apply cleanly, zero errors
  - _Requirements: 4.1, 4.2, 4.3_

- [ ] 5.2 Verify no pending migrations
  - Run `.venv/bin/python manage.py migrate --check`
  - Expected: exits 0 — no pending migrations
  - _Requirements: 4.2_

- [ ] 5.3 Seed the database
  - Run `.venv/bin/python manage.py seed_test_data`
  - Expected: completes successfully, all 5 personas created
  - _Requirements: 4.4_

---

## Phase 3: Ecosystem Script Updates

### Group 6 — start.sh

- [ ] 6.1 Add Postgres container lifecycle management to `start.sh`
  - Add a function that handles all three container states:
    ```bash
    start_postgres() {
      if ! docker info > /dev/null 2>&1; then
        echo "ERROR: Docker is not running. Start Docker and try again."
        exit 1
      fi

      if [ ! "$(docker ps -aq -f name=ecommerceb2b-postgres)" ]; then
        echo "Creating Postgres container..."
        docker run -d \
          --name ecommerceb2b-postgres \
          -e POSTGRES_DB=ecommerceb2b \
          -e POSTGRES_USER=postgres \
          -e POSTGRES_PASSWORD=postgres \
          -p 5432:5432 \
          -v "$(pwd)/data/pgdata:/var/lib/postgresql/data" \
          postgres:16
      elif [ ! "$(docker ps -q -f name=ecommerceb2b-postgres)" ]; then
        echo "Starting existing Postgres container..."
        docker start ecommerceb2b-postgres
      else
        echo "Postgres already running."
      fi
    }
    ```
  - Call `start_postgres` before starting any other service
  - _Requirements: 7.1_

- [ ] 6.2 Add Postgres health check to `start.sh`
  - After `start_postgres`, poll until ready (timeout 30 seconds):
    ```bash
    echo "Waiting for Postgres to be ready..."
    RETRIES=30
    until docker exec ecommerceb2b-postgres pg_isready -U postgres -q || [ $RETRIES -eq 0 ]; do
      RETRIES=$((RETRIES - 1))
      sleep 1
    done
    if [ $RETRIES -eq 0 ]; then
      echo "ERROR: Postgres did not become ready in time. Check Docker logs."
      exit 1
    fi
    echo "Postgres ready."
    ```
  - _Requirements: 7.2_

---

### Group 7 — stop.sh

- [ ] 7.1 Add Postgres container shutdown to `stop.sh`
  - Add `docker stop ecommerceb2b-postgres` to the shutdown sequence
  - Place it after Django/embedding/SSE are stopped so the app shuts down
    cleanly before the database goes away
  - Add a guard so it does not error if the container is not running:
    ```bash
    if [ "$(docker ps -q -f name=ecommerceb2b-postgres)" ]; then
      echo "Stopping Postgres..."
      docker stop ecommerceb2b-postgres
    fi
    ```
  - _Requirements: 7.3_

---

### Group 8 — Seed Scripts

- [ ] 8.1 Add Postgres preflight check to `qa/full_reset.sh`
  - Add before any Django commands:
    ```bash
    echo "Checking Postgres..."
    if ! docker exec ecommerceb2b-postgres pg_isready -U postgres -q 2>/dev/null; then
      echo "ERROR: Postgres is not running. Run 'bash start.sh' first."
      exit 1
    fi
    echo "Postgres ready."
    ```
  - _Requirements: 8.1, 8.3_

- [ ] 8.2 Add Postgres preflight check to `qa/reset_and_seed.sh`
  - Same preflight block as 8.1
  - _Requirements: 8.2, 8.3_

---

## Phase 4: Test Suite Verification

### Group 9 — Run Existing Tests Against Postgres

- [ ] 9.1 Run the full test suite against Postgres
  - Run `.venv/bin/python manage.py test`
  - Expected: all tests pass, zero failures, zero errors
  - If any test fails only on Postgres: treat as a bug, fix before
    proceeding — it is not acceptable to leave engine-specific failures
  - _Requirements: 5.1, 5.2, 5.3_

---

## Phase 5: Documentation Updates

### Group 10 — Documentation

- [ ] 10.1 Update `CLAUDE.md`
  - Add a "Local Database Setup" section under Tech Stack:
    - Postgres 16 required via Docker
    - `start.sh` manages the container lifecycle automatically
    - First-time setup: `cp .env.example .env` then `bash start.sh`
    - To wipe all data: `bash stop.sh`, `rm -rf data/pgdata/`,
      `bash qa/full_reset.sh`
  - _Requirements: 6.1_

- [ ] 10.2 Update `ai-docs/AGENT_NOTES.md`
  - Add note: `DATABASE_URL` must be present in `.env`; missing value
    raises `ImproperlyConfigured` at startup — not a silent fallback
  - Add note: `python-dotenv` loads `.env` automatically; no manual
    shell exports needed
  - Add note: `data/pgdata/` is the Postgres data directory — do not
    delete it unintentionally; wipe only via the documented procedure
  - _Requirements: 6.2_

- [ ] 10.3 Update `qa/README.md`
  - Update Quick Start: `bash start.sh` handles Postgres automatically —
    no separate Docker command needed
  - Add "Wiping the Database" section:
    ```bash
    bash stop.sh
    rm -rf data/pgdata/
    bash qa/full_reset.sh
    ```
  - _Requirements: 6.3_

---

### Group 11 — Final Verification and Close-Out

- [ ] 11.1 Full ecosystem smoke test
  - Run `bash start.sh`
  - Confirm all three services start cleanly and Postgres is up
  - Log in as `alice@seed.test` (password: `Seedpass1!`)
  - Confirm basic flows work: listing detail, messaging, discover
  - Run `bash stop.sh`
  - Confirm nothing is left running
  - _Requirements: all_

- [ ] 11.2 Verify data persists across stop/start cycle
  - Run `bash start.sh`
  - Confirm seed data is present (alice's listings, etc.)
  - Run `bash stop.sh`
  - Run `bash start.sh` again
  - Confirm data is still present — bind mount persisted correctly
  - _Requirements: 7.4_

- [ ] 11.3 Confirm scope boundaries
  - No Dockerization of Django, embedding, or SSE services
  - No Railway configuration added
  - No media file storage changes
  - No data migrated from SQLite — fresh Postgres DB only
  - _Requirements: 9.1–9.6_

- [ ] 11.4 Update `specs/SPEC_ORDER.md` status to `REQ, DES, TASK, EXEC`

- [ ] 11.5 Update `ai-docs/SESSION_STATUS.md` with implementation summary
