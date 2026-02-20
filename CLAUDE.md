# CLAUDE.md — Standing Instructions for AI Agents

## First Step (Every Session)

Before doing any work in this repository, read and internalize:

1. `ai-docs/ai-constitution.md` — governance rules, scope control, stop conditions
2. `ai-docs/v1-agent-build-spec.md` — authoritative product spec and data schemas
3. `ai-docs/v1-implementation-decisions.md` — locked engineering decisions
4. `ai-docs/v3-discovery-watchlist-spec.md` — V3 discovery/watchlist/messaging evolution

## Authority Order

1. `ai-docs/v1-agent-build-spec.md` (highest, except as overridden below)
2. `ai-docs/v3-discovery-watchlist-spec.md` (overrides V1 only for discovery/watchlist/messaging evolution)
3. `ai-docs/ai-constitution.md`
4. `ai-docs/v1-implementation-decisions.md`
5. Explicit human instructions in the current session (lowest)

If any planned work conflicts with a higher-authority document, **stop and ask the human** before proceeding. Do not silently override spec docs based on session instructions.

## Key Rules

- Do not add features not in the spec
- Do not alter the core loop, role boundaries, or data access rules without explicit approval
- Do not guess when requirements are ambiguous — ask
- Validate all planned changes against the build spec schemas before writing code
- When in doubt, do less, not more

## Tech Stack

- Python 3.12 / Django / PostgreSQL (SQLite for local dev)
- Server-rendered templates, no SPA
- Django ORM, Django built-in auth
- Virtual environment: `.venv/bin/python`
- Run Django commands with: `.venv/bin/python manage.py <command>`
- Embedding sidecar service (FastAPI/uvicorn) for vector search — see below

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
# Terminal 1: Start the embedding service
cd services/embedding
bash run.sh
# Or directly:
EMBEDDING_SOCKET_PATH=/tmp/ecommerceb2b-embedding.sock uvicorn app:app --uds /tmp/ecommerceb2b-embedding.sock

# Terminal 2: Django as usual
.venv/bin/python manage.py runserver
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

**Read `ai-docs/v2.1-status.md` for detailed status of the V2.1 UX & Form Enhancements.**
This file tracks what's done, what still needs testing, and any known issues.

# Skinnable Theme System

## How It Works
- Each skin = one standalone CSS file in `static/css/skin-<name>.css`.
- All skins implement the same CSS class names (the "skin contract").
- The active skin is stored on `User.skin` (default: `warm-editorial`).
- `marketplace/context_processors.py` provides `{{ skin_css }}` to templates.
- `base.html` uses `<link rel="stylesheet" href="{% static skin_css %}">`.
- Unauthenticated users see the default skin (`warm-editorial`).

## Available Skins
| Slug | File | Description |
|------|------|-------------|
| `warm-editorial` | `skin-warm-editorial.css` | Cream/coral/serif editorial theme (default) |
| `simple-blue` | `skin-simple-blue.css` | Clean blue/gray utilitarian theme |

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
- **Forms:** `form p`, `label`, input types, `select`, `textarea`, `.helptext`, `.errorlist`, `.search-mode-row`
- **Auth:** `.auth-form`, `.auth-link`
- **Messages (Django):** `.messages`, `.message`, `.success`, `.error`, `.warning`, `.info`
- **Messaging (thread):** `.messages-list`, `.message.sent`, `.message.received`
- **Status badges:** `.status`, `.status-active`, `.status-paused`, `.status-expired`, `.status-fulfilled`, `.status-withdrawn`, `.status-deleted`
- **Definition lists:** `dl`, `dt`, `dd`
- **Match UI:** `.match-group`, `.match-group-header`, `.match-card`, `.match-card--watchlist`, `.match-card-inactive`, `.match-card-details`, `.match-card-actions`, `.match-card-actions-left`, `.match-card-actions-right`, `.match-badge`, `.matches-scroll`, `details.match-group`
- **Misc:** `.actions`, `.empty-state`, `.item-list`, `.pagination`
- **Responsive:** `@media (max-width: 600px)`

## Styling Ground Rules
- Never hardcode a value that exists as a CSS variable in `:root`. Always use `var(--...)`.
- Prefer applying existing classes over adding new CSS.
- Do not change business logic; styling changes should be class additions + CSS edits only.
- When adding a new component class, add it to **both** skin files.
