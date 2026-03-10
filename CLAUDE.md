# CLAUDE.md — Standing Instructions for AI Agents

## First Step (Every Session)

**Orientation (read once when new to the project):**
1. `README.md` — what this product is and who it's for
2. `ai-docs/PRODUCT_ROADMAP.md` — what's been built and where it's going

**Every session:**
3. `ai-docs/SESSION_STATUS.md` — current state, what's done, what's next (update at end of session)
4. `ai-docs/ai-constitution.md` — governance rules, scope control, stop conditions
5. `ai-docs/AGENT_NOTES.md` — gotchas, non-obvious patterns, hard-won lessons

**QA work only:**
6. `qa/README.md` — test scripts, seed accounts, reset tooling

## Authority Order

1. `ai-docs/ai-constitution.md`
2. `ai-docs/PRODUCT_ROADMAP.md`
3. `specs/` documents for the feature being worked on
4. Explicit human instructions in the current session (lowest)

If any planned work conflicts with a higher-authority document, **stop and ask the human** before proceeding. Do not silently override spec docs based on session instructions.

## Key Rules

- Do not add features not in the spec
- Do not alter the core loop, role boundaries, or data access rules without explicit approval
- Do not guess when requirements are ambiguous — ask
- Validate all planned changes against the build spec schemas before writing code
- When in doubt, do less, not more

## Tech Stack

- Python 3.12 / Django / PostgreSQL
- Server-rendered templates, no SPA
- Django ORM, Django built-in auth
- Virtual environment: `.venv/bin/python`
- Run Django commands with: `.venv/bin/python manage.py <command>`
- Embedding sidecar service (FastAPI/uvicorn) for vector search — see below

## Local Database Setup

PostgreSQL 16 is required. `start.sh` manages the Docker container automatically —
you do not need to run `docker run` manually.

**First-time setup:**
```bash
cp .env.example .env   # DATABASE_URL is pre-configured for local dev
.venv/bin/pip install -r requirements.txt
bash start.sh          # creates container, migrates, starts all services
```

**Daily workflow:** `bash start.sh` / `bash stop.sh` — unchanged.

**Wiping all data (full clean slate):**
```bash
bash stop.sh
rm -rf ~/.local/share/ecommerceb2b/pgdata
bash qa/full_reset.sh
```

**Data persistence:** Postgres data lives in `~/.local/share/ecommerceb2b/pgdata`
on the WSL2 native Linux filesystem (not inside the project directory). This path
is required — the Windows filesystem (`/mnt/c/`) does not support the permissions
Postgres needs. Override with the `PGDATA_DIR` environment variable if needed.
Data survives stop/start cycles. Deleting that directory is the only way to lose data.

**`DATABASE_URL` is required.** A missing value raises `ImproperlyConfigured` at
Django startup — there is no SQLite fallback. Configure it via `.env`.

# Embedding Service (Sidecar)

## Architecture
The SentenceTransformer model and ChromaDB run in a standalone FastAPI sidecar process, **not** inside Django. Django communicates with it over a Unix Domain Socket using `httpx`.

```
Django  ──(Unix socket)──>  Embedding Service (FastAPI/uvicorn)
                              ├── SentenceTransformer model (loaded at startup)
                              └── ChromaDB (persistent, data/chroma/)
```

## Key Files
| File | Purpose |
|------|---------|
| `services/embedding/app.py` | FastAPI app — all embedding + ChromaDB logic |
| `services/embedding/requirements.txt` | Service-specific deps (fastapi, uvicorn, chromadb, sentence-transformers) |
| `services/embedding/run.sh` | Startup script (cleans stale socket, runs uvicorn) |
| `marketplace/vector_search.py` | Django-side HTTP client — same public API, talks to sidecar via socket |

## How to Run
```bash
# Recommended — start all three services at once:
bash start.sh

# Or start the embedding sidecar individually (e.g. for debugging):
cd services/embedding
bash run.sh
```

## Configuration (env vars / settings.py)
| Variable | Default | Used by |
|----------|---------|---------|
| `EMBEDDING_SOCKET_PATH` | `/tmp/ecommerceb2b-embedding.sock` | Django + service |
| `EMBEDDING_SERVICE_TOKEN` | `dev-token-change-me` | Django + service (shared secret) |
| `CHROMA_PERSIST_DIR` | `../../data/chroma` (relative to service dir) | Service only |

## API Endpoints (service)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/index` | Index/update a listing |
| POST | `/search` | Semantic search (returns PKs + distances) |
| POST | `/remove` | Remove from index |
| POST | `/rebuild` | Batch rebuild entire index |
| GET | `/health` | Readiness check |

## Important Notes
- The model loads **once** at service startup (1-2 min cold start) — Django never waits for model loading.
- If the service is down, all vector search calls fail silently (logged, return empty results).
- Auth: `X-Service-Token` header with shared secret. `/health` is unauthenticated.
- Django's `marketplace/vector_search.py` public API is unchanged: `index_listing()`, `remove_listing()`, `search_listings()`, `rebuild_index()`. No callers needed modification.

## Current Work-in-Progress

**Use `ai-docs/SESSION_STATUS.md` as the single source of truth for current status.**
This file tracks what's done, what still needs testing, and any known issues.

# SSE Service (Sidecar — Real-time Messaging)

## Architecture
The SSE relay runs as a standalone FastAPI sidecar over **TCP** (not UDS), because
browsers connect directly via `EventSource`. Django publishes events over HTTP;
the sidecar fans them out to connected browsers.

```
Browser  ──(EventSource, TCP :8001)──>  SSE Service (FastAPI/uvicorn)
Django   ──(HTTP POST /publish)──────>  SSE Service
```

## Key Files
| File | Purpose |
|------|---------|
| `services/sse/app.py` | FastAPI app — SSE relay + publish endpoint |
| `services/sse/run.sh` | Startup script |
| `services/sse/requirements.txt` | Service-specific deps (fastapi, uvicorn) |
| `marketplace/sse_client.py` | Django-side HTTP client — publish events + generate stream tokens |
| `static/js/sse-client.js` | Browser EventSource client — updates thread, inbox, navbar |

## How to Run
```bash
# Recommended — start all three services at once:
bash start.sh

# Or start the SSE relay individually (e.g. for debugging):
cd services/sse
bash run.sh
```

## Configuration (env vars / settings.py)
| Variable | Default | Used by |
|----------|---------|---------|
| `SSE_SERVICE_URL` | `http://127.0.0.1:8001` | Django + browser |
| `SSE_SERVICE_TOKEN` | `dev-token-change-me` | Django + service (shared secret) |
| `SSE_STREAM_SECRET` | `dev-stream-secret` | Django + service (HMAC signing) |
| `SSE_CORS_ORIGINS` | `http://127.0.0.1:8000,http://localhost:8000` | Service only |
| `SSE_HOST` | `127.0.0.1` | Service only (run.sh) |
| `SSE_PORT` | `8001` | Service only (run.sh) |

## API Endpoints (service)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/publish` | Django publishes events (auth: `X-Service-Token`) |
| GET | `/stream/{user_id}?token=...` | Browser EventSource connection (auth: HMAC token) |
| GET | `/health` | Readiness check (unauthenticated) |

## Important Notes
- No model loading — service starts instantly (unlike embedding sidecar).
- If the service is down, SSE publish calls fail silently (logged). Email notifications still work.
- Browser auth uses HMAC-signed query tokens (EventSource can't set headers).
- Auto-reconnect with exponential backoff in the browser client (max 10 retries).
- Django's `marketplace/sse_client.py` public API: `generate_stream_token()`, `publish_event()`, `publish_new_message()`.

# Skinnable Theme System

## How It Works
- Each skin = one standalone CSS file in `static/css/skin-<name>.css`.
- All skins implement the same CSS class names (the "skin contract").
- The active skin is stored on `User.skin` (application default: `simple-blue`, no DB default).
- `marketplace/context_processors.py` provides `{{ skin_css }}` to templates.
- `base.html` uses `<link rel="stylesheet" href="{% static skin_css %}">`.
- Unauthenticated users see the default skin (`simple-blue`).

## Available Skins
| Slug | File | Description |
|------|------|-------------|
| `warm-editorial` | `skin-warm-editorial.css` | Cream/coral/serif editorial theme |
| `simple-blue` | `skin-simple-blue.css` | Clean blue/gray utilitarian theme (default) |

## Adding a New Skin
1. Add a choice to `Skin` enum in `marketplace/models.py`.
2. Create `static/css/skin-<slug>.css` implementing all contract classes.
3. Run `makemigrations` + `migrate` (the default stays unchanged).

## Skin Contract (classes every skin must implement)
- **Layout:** `main`, `.container`
- **Navbar:** `nav`, `nav a`, `nav button`, `nav form`
- **Buttons:** `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-small`, `button[type="submit"]`
- **Cards:** `section`, `.card`
- **Tiles:** `.card-grid`, `.tile`, `.tile-title`, `.tile-meta`
- **Listing filter:** `.listing-filter-bar`, `.listing-filter-input-wrap`, `.listing-filter-clear`, `.listing-filter-count`, `.listing-status-checks`, `.listing-status-check`, `.tile-filtered`
- **Forms:** `form p`, `label`, input types, `select`, `textarea`, `.helptext`, `.errorlist`, `.search-mode-row`
- **Auth:** `.auth-form`, `.auth-link`
- **Messages (Django):** `.messages`, `.message`, `.success`, `.error`, `.warning`, `.info`
- **Messaging (thread):** `.messages-list`, `.message.sent`, `.message.received`
- **Status badges:** `.status`, `.status-active`, `.status-paused`, `.status-expired`, `.status-fulfilled`, `.status-withdrawn`, `.status-deleted`
- **Definition lists:** `dl`, `dt`, `dd`
- **Match UI:** `.match-group`, `.match-group-header`, `.match-card`, `.match-card--watchlist`, `.match-card-inactive`, `.match-card-details`, `.match-card-actions`, `.match-card-actions-left`, `.match-card-actions-right`, `.match-badge`, `.match-badge-unsaved`, `.match-badge-saved`, `.tile-match-counts`, `.matches-scroll`, `details.match-group`
- **Inbox/Messages:** `.nav-badge`, `.thread-unread`, `.thread-preview`
- **Avatars:** `.avatar`, `.avatar-xs`, `.avatar-sm`, `.avatar-lg`, `.avatar-clickable`, `.listing-owner`
- **Accessibility:** `.visually-hidden`
- **Avatar lightbox:** `#avatar-lightbox`, `#avatar-lightbox::backdrop`, `#avatar-lightbox-close`
- **Misc:** `.actions`, `.empty-state`, `.item-list`, `.pagination`
- **Responsive:** `@media (max-width: 600px)`

## Styling Ground Rules
- Never hardcode a value that exists as a CSS variable in `:root`. Always use `var(--...)`.
- Prefer applying existing classes over adding new CSS.
- Do not change business logic; styling changes should be class additions + CSS edits only.
- When adding a new component class, add it to **both** skin files.

# QA Infrastructure

## Overview
The `qa/` directory contains the manual test script and reset tooling for human testers.
The seed command lives in `marketplace/management/commands/seed_test_data.py`.

## Scripts

| Script | Purpose |
|--------|---------|
| `bash start.sh` | Start full ecosystem (embedding + SSE + Django) |
| `bash qa/full_reset.sh` | **Recommended test prep**: start ecosystem + seed DB + rebuild vector index |
| `bash qa/reset_and_seed.sh` | DB-only reset when ecosystem is already running |
| `.venv/bin/python manage.py seed_test_data` | Seed command (called by reset scripts) |
| `.venv/bin/python manage.py rebuild_vector_index` | Rebuild ChromaDB after a DB reset |

## Seed Personas

All accounts use password `Seedpass1!`.

| Email | Name | State | Key data |
|-------|------|-------|----------|
| alice@seed.test | Alice Thornton | verified, has avatar | 3 active supply, 1 paused, 1 expired |
| bob@seed.test | Bob Mercado | verified, has avatar | 2 active demand, 1 paused, 1 expired; unread message |
| carol@seed.test | Carol Vance | verified, **no avatar** | 1 supply + 1 demand |
| dave@seed.test | Dave Okonkwo | verified, has avatar | 1 active, 1 fulfilled, 1 withdrawn supply; unread message |
| eve@seed.test | Eve Nakamura | **UNVERIFIED** | Tests login-blocking + resend-verification |

## Maintenance Contract — What to Update When a Feature Ships

Every spec execution cycle **must** include updates to:

1. **`marketplace/management/commands/seed_test_data.py`**
   - Add at least one representative row for every new model, status, or feature
   - Add a new persona or extend an existing one if the feature introduces a new user state
   - If the feature changes a model field, update existing seed rows accordingly

2. **`qa/MANUAL_TEST_SCRIPT.md`**
   - Add a new section (or subsection) covering the new feature's happy path and key edge cases
   - Mark high-value automation candidates with `[AUTO]`
   - Add new items to the "Future Automation Targets" list
   - Update "Known Limitations" if anything previously out-of-scope is now in-scope

3. **`CLAUDE.md` (this file)**
   - Add any new CSS contract classes to the Skin Contract section
   - Add any new services, scripts, or management commands to the relevant tables
   - Update the Seed Personas table if new accounts are added

4. **`specs/SPEC_ORDER.md`**
   - Update the feature's status to `EXEC`

5. **`ai-docs/SESSION_STATUS.md`**
   - Record what was built and the new test suite count

The test script and seed command are **living documents**, not one-time artifacts.
A feature is not fully shipped until all five of the above are updated.
