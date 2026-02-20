# V3 Discovery & Watchlist — Session Status

**Last updated:** 2026-02-19
**Feature:** Manual Discovery, Watchlist, Messaging Evolution
**Current phase:** Implementation in progress — embedding sidecar extracted

---

## Session History

### Session 1 (2026-02-16)

**Work completed:**

1. **Match lifecycle management (pre-V3):** Implemented `MatchStatus` enum, `status` field on Match, reconciliation logic (`reconcile_matches_for_lot/post`, `deactivate_matches_for_lot/post`), updated views to use reconciliation on edit/toggle, added `match_history` view and template, updated admin. Migration 0006 applied. All verification checks passed.

2. **V3 feature discussion:** Extensive brainstorming session with human on discovery + watchlist feature. Key decisions reached:
   - Auto-matches become ephemeral suggestions (computed on the fly, not stored)
   - Manual search (keyword → semantic in two passes) from a `/discover/` page
   - Watchlist with starred/watching/archived states replaces match list
   - Messaging decoupled from algorithmic matching — can message from search results
   - No listing required to search and contact counterparts
   - Match model to be removed (clean data reset approved)
   - Two-pass implementation: Pass 1 keyword search, Pass 2 semantic/vector search

3. **V3 spec written:** `ai-docs/v3-discovery-watchlist-spec.md` — comprehensive spec covering data model, UX, URL structure, implementation passes, migration plan.

**Key decisions confirmed by human:**
- Suggestions are on-the-fly, not stored
- Stale test data will be blown away for clean architecture start
- Auto-matches are suggestions until explicitly saved to watchlist
- Messaging auto-adds to watchlist
- Watchlist states: starred (active pursuit), watching (default), archived (historical)
- Search defaults to profile values, remembers custom values within session
- Result limit: default 20, "Load more" button
- Two-pass approach (keyword first, semantic second)

### Session 2 (2026-02-19)

**Work completed:**

1. **Embedding service extraction:** Extracted the SentenceTransformer model + ChromaDB out of the Django process into a standalone FastAPI sidecar that communicates over a Unix Domain Socket.

   **Problem solved:** The SentenceTransformer model takes 1-2 minutes to load on first use, blocking the user mid-request. Every Django restart forced a cold start because the model was lazy-loaded inside the Django process.

   **Architecture:**
   ```
   Django  ──(Unix socket)──>  Embedding Service (FastAPI/uvicorn)
                                 ├── SentenceTransformer model (loaded at startup)
                                 └── ChromaDB (persistent, data/chroma/)
   ```

   **Files created:**
   | File | Purpose |
   |------|---------|
   | `services/embedding/app.py` | FastAPI app with `/index`, `/search`, `/remove`, `/rebuild`, `/health` endpoints. Includes adaptive cutoff algorithm, token auth middleware, ChromaDB + embedding logic. |
   | `services/embedding/requirements.txt` | fastapi, uvicorn, chromadb, sentence-transformers |
   | `services/embedding/run.sh` | Startup script (cleans stale socket, runs uvicorn with `--uds`) |

   **Files modified:**
   | File | Change |
   |------|--------|
   | `marketplace/vector_search.py` | Rewritten as thin HTTP client using `httpx` over Unix socket. Same public API (`index_listing`, `remove_listing`, `search_listings`, `rebuild_index`). |
   | `config/settings.py` | Added `EMBEDDING_SOCKET_PATH` and `EMBEDDING_SERVICE_TOKEN` settings |
   | `requirements.txt` | Added `httpx[http2]>=0.27,<1` |

   **What did NOT change:** Views, templates, models, URLs, management command (`rebuild_vector_index` calls the same `rebuild_index()` function).

2. **Documentation updates:** Updated `CLAUDE.md` (embedding service section), `v3-discovery-watchlist-spec.md` (§8 search architecture, §10, §12), and this status file.

**Key decisions:**
- Unix Domain Socket (not TCP) — no network exposure, filesystem-permission secured
- Shared secret via `X-Service-Token` header (from `EMBEDDING_SERVICE_TOKEN` env var)
- `/health` endpoint is unauthenticated (for monitoring)
- Service fails silently from Django's perspective — all calls wrapped in try/except, return empty results on error

---

## Current Codebase State

### Files modified in this session (pre-V3, match lifecycle):
| File | Change |
|------|--------|
| `marketplace/models.py` | Added `MatchStatus` enum, `status` field on Match |
| `marketplace/migrations/0006_match_status.py` | Schema migration |
| `marketplace/matching.py` | Added reconciliation functions |
| `marketplace/views.py` | Updated edit/toggle views, match count annotations, added `match_history` view |
| `marketplace/urls.py` | Added `/matches/history/` route |
| `marketplace/admin.py` | Match status in list_display + list_filter |
| `templates/marketplace/match_history.html` | New template |
| `templates/marketplace/match_list.html` | Added history link |
| `static/css/style.css` | Added `.match-card-inactive` style |

**Note:** The match lifecycle changes will be **removed/replaced** during V3 Pass 1 implementation (Match model deprecated, reconciliation logic replaced by on-the-fly suggestions).

### Spec files:
| File | Status |
|------|--------|
| `ai-docs/v3-discovery-watchlist-spec.md` | Written, awaiting review |
| `ai-docs/v3-session-status.md` | This file |

---

## What's Next

### Completed:
- ✅ Human reviewed and approved `v3-discovery-watchlist-spec.md`
- ✅ Embedding sidecar extracted (Session 2)

### Remaining implementation order:
1. Data reset (flush DB)
2. Model changes: remove Match/MatchStatus, add WatchlistItem/DismissedSuggestion, modify MessageThread
3. Migration generation
4. Update `matching.py`: remove reconciliation/evaluate functions, add suggestion engine functions, add search functions
5. Update `views.py`: remove match views, add discover/watchlist/suggestion views
6. Update `urls.py`: new routes, remove old match routes
7. Templates: `discover.html`, `watchlist.html`, update dashboard/detail pages
8. CSS: new styles for discover results, watchlist sections
9. Admin: register new models, remove Match admin
10. Navbar: add Discover and Watchlist links
11. Verification: `manage.py check`, smoke test, confirm embedding service integration

---

## Known Considerations

- **V1 spec access invariants are changing** — documented in V3 spec §4. Human has authorized this evolution.
- **Match lifecycle code (just built) will be replaced** — the concepts carry forward (validity checking, location compatibility) but the Match model and reconciliation functions are superseded by the watchlist architecture.
- **No automated tests exist** — V3 implementation should include at least basic tests for the search and watchlist logic.
- **SQLite dev compatibility** — Keyword search works fine on SQLite. ChromaDB runs in the sidecar (decoupled from RDBMS choice).
- **Embedding sidecar must be running** for vector search to work. If it's down, search calls fail silently (return empty). Start with `cd services/embedding && bash run.sh`.

---

**END OF STATUS**
