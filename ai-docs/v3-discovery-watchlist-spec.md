# V3 Discovery & Watchlist Spec

**Project:** Niche Supply ↔ Professional Demand Platform
**Feature:** Manual Discovery, Watchlist, Messaging Evolution
**Status:** Approved — implementation in progress
**Audience:** AI coding agents (primary), human reviewer (secondary)
**Authority:** This document is authorized by explicit human direction in session. It intentionally evolves several V1 invariants (documented in §4).

---

## 1. Overview

V1 and V2 provided a passive matching system: users post listings and wait for algorithmic matches. V3 adds **active discovery** — the ability to search for counterpart listings manually — and a **watchlist** that becomes the unified hub for all user interest, whether sourced from suggestions or manual search.

The existing auto-matching algorithm is preserved but repositioned as a **suggestion engine**. Suggestions are computed on the fly (not stored) and shown to users who can accept or dismiss them. The Match model is deprecated in favor of WatchlistItem as the core relationship record.

Messaging is decoupled from algorithmic matching. Users can message any counterpart lister directly from search results or suggestions, which automatically adds the item to their watchlist.

---

## 2. Motivation

- **Keyword matching is brittle.** "Organic heirloom tomatoes" won't match "heritage tomato varieties." Users need the ability to search with their own terms.
- **Users want agency.** Passive matching is useful but insufficient. Real procurement involves active searching.
- **No listing required for discovery.** A buyer should be able to search supply lots and contact a supplier without having posted a demand. This simplifies onboarding and mirrors how marketplaces like eBay work.
- **Unified interest tracking.** Whether a match was suggested or manually discovered, the user needs one place to track items they're pursuing.

---

## 3. Core Concepts

| Concept | Definition |
|---------|-----------|
| **Discover** | Authenticated search for counterpart listings. Buyers search supply lots; suppliers search demand posts. |
| **Suggestion** | An algorithmically computed potential match, shown on the fly. Ephemeral until the user acts on it. |
| **Watchlist** | A user's personal list of counterpart listings they are interested in. The central hub for all activity. |
| **WatchlistItem** | A record linking a user to a counterpart listing, with a status (starred/watching/archived). |
| **Starred** | Watchlist status: actively pursuing, top priority. |
| **Watching** | Watchlist status: on my radar, default state when added. |
| **Archived** | Watchlist status: no longer interested, or listing was withdrawn. Conversations preserved, read-only history. |
| **Dismissed** | A suggestion the user explicitly doesn't want. Tracked to avoid re-showing. |

---

## 4. V1 Rules Being Evolved

The following V1 access invariants (from `v1-agent-build-spec.md` §4) are **deliberately changed** with explicit human authorization:

| V1 Rule | V3 Evolution | Rationale |
|---------|-------------|-----------|
| "Buyers may only see SupplyLots after a Match" | Buyers can discover supply lots via search | Enables active procurement |
| "Suppliers may only see DemandPosts after a Match" | Suppliers can discover demand posts via search | Enables proactive selling |
| "Users may not message without a Match" | Users can message from search results or suggestions | Removes friction, mirrors eBay model |
| "No public visibility of posts" | **Unchanged** — authentication still required for all discovery | Privacy preserved |

The **Core Loop** (§2 of build spec) evolves from:

```
Post → System matches → Notify → Connect
```

To:

```
Post → Discover (search + suggestions) → Save/Message → Connect
         ↑                                    ↑
    Manual search                    Auto-suggestions feed in too
```

The original loop remains as one pathway (suggestions), but discovery adds a second, user-driven pathway.

---

## 5. Data Model

### 5.1 New Models

#### WatchlistItem
```
WatchlistItem
  id                    (auto PK)
  user                  (FK to User — the person watching)
  supply_lot            (FK to SupplyLot, nullable — for buyers watching supply)
  demand_post           (FK to DemandPost, nullable — for suppliers watching demand)
  status                (CharField: starred | watching | archived, default: watching)
  source                (CharField: suggestion | search | direct)
  created_at            (DateTimeField, auto)
  updated_at            (DateTimeField, auto)

Constraints:
  - CheckConstraint: exactly one of supply_lot / demand_post must be non-null
  - UniqueConstraint: (user, supply_lot) where supply_lot is not null
  - UniqueConstraint: (user, demand_post) where demand_post is not null
```

#### WatchlistStatus (TextChoices enum)
```
STARRED   = "starred",  "Starred"
WATCHING  = "watching",  "Watching"
ARCHIVED  = "archived",  "Archived"
```

#### WatchlistSource (TextChoices enum)
```
SUGGESTION = "suggestion", "Suggestion"
SEARCH     = "search",     "Search"
DIRECT     = "direct",     "Direct"
```

#### DismissedSuggestion
```
DismissedSuggestion
  id                    (auto PK)
  user                  (FK to User)
  supply_lot            (FK to SupplyLot, nullable)
  demand_post           (FK to DemandPost, nullable)
  created_at            (DateTimeField, auto)

Constraints:
  - CheckConstraint: exactly one of supply_lot / demand_post must be non-null
  - UniqueConstraint: (user, supply_lot) where supply_lot is not null
  - UniqueConstraint: (user, demand_post) where demand_post is not null
```

### 5.2 Modified Models

#### MessageThread
```
Before:
  match       (OneToOneField to Match)
  buyer       (FK to User)
  supplier    (FK to User)

After:
  watchlist_item  (OneToOneField to WatchlistItem)
  buyer           (FK to User)
  supplier        (FK to User)
```

#### Match (Deprecated)
The Match model is **deprecated**. Existing Match records and the `MatchStatus` field added in the match lifecycle work are removed as part of the data reset. The matching algorithm functions (`normalize`, `overlaps`, `location_compatible`) are preserved in `matching.py` and reused by both the suggestion engine and search.

### 5.3 Unchanged Models

User, Organization, DemandPost, SupplyLot, Message — no schema changes.

---

## 6. User Experience

### 6.1 Discover Page (`/discover/`)

The primary manual search interface. Role-aware: buyers see supply lots, suppliers see demand posts.

**Search form:**
- **Search term** (text input, required) — semantic search via ChromaDB with keyword fallback
- **Category** (dropdown, optional) — "All categories" default, same enum as listings
- **Location** (composite):
  - Country: defaults to user's profile `country`
  - Postal code / locality: defaults to user's profile location values
  - Radius: preset selector — 25 / 50 / 100 / Any distance (in user's preferred unit: mi or km)
- Search values persist: use user's profile values as initial defaults. Once the user enters custom values, remember them in the session for subsequent searches within the same login.

**Results:**
- Cards below the search form, max 20 per page, "Load more" button
- Each card shows: item_text, category badge, location (country + locality), key metadata
  - Supply lot cards: quantity, asking price, shipping scope, available_until
  - Demand post cards: quantity, frequency, shipping preference
- Each card has two actions:
  - **"Save"** — adds to watchlist (watching status, source: search)
  - **"Message"** — creates WatchlistItem (watching, source: direct) + MessageThread + redirects to thread
- Results sorted by semantic similarity (ChromaDB distance score)
- Cards for listings already on the user's watchlist show "Saved" badge instead of Save button

**Empty state:** "No results found. Try broadening your search."

### 6.2 Watchlist Page (`/watchlist/`)

The user's personal interest hub. Three sections with tab-like navigation or collapsible sections:

**Starred section (top):**
- Items the user has starred as high priority
- Each item: listing details, "Unstar" action, "Archive" action, "Message" button (or "View conversation" if thread exists)
- Empty: "No starred items."

**Watching section:**
- Default landing section
- Items the user is tracking but hasn't starred
- Each item: listing details, "Star" action, "Archive" action, "Message" button
- Empty: "No items being watched."

**Archived section (bottom, collapsed by default):**
- Historical items: user lost interest, or listing was withdrawn/expired
- Each item: listing details (muted appearance), "Unarchive" action, "View conversation" if thread exists
- Messaging still possible even for archived items (conversations are always accessible)
- Empty: "No archived items."

**Automatic archival:** When a listing is withdrawn/paused/expired, all associated WatchlistItems are automatically moved to `archived` status. When a listing is reactivated, associated WatchlistItems are restored to their previous status (`watching` or `starred`).

### 6.3 Dashboard Changes

**"Suggested for you" section:**
- Computed on the fly using the existing matching algorithm
- For buyers: suggestions across all their active demand posts — "Based on [demand post item_text]:"
- For suppliers: suggestions across all their active supply lots — "Based on [supply lot item_text]:"
- Max 5 suggestion cards on dashboard (keep it concise)
- Each card: counterpart listing details + "Save to watchlist" button + "Dismiss" button
- Excluded: items already on user's watchlist (any status), dismissed suggestions
- If user has no active listings: "Post a listing to see suggestions, or use Discover to search manually."

**Existing sections remain:**
- Recent listings (demand posts for buyers, supply lots for suppliers)
- Quick-access links

**Match count badge evolution:**
- Currently shows auto-match count per listing
- Evolves to show watchlist item count (or just remove it — the watchlist page is the hub now)

### 6.4 Listing Detail Page Changes

**"Suggested matches" section:**
- Computed on the fly for this specific listing
- Same matching logic, same exclusions (already on watchlist, dismissed)
- Shows up to 5 suggestions with "Save" and "Dismiss" buttons
- Appears below the listing details, above the actions bar

**Label:**
- Buyer viewing demand post: "Suggested suppliers"
- Supplier viewing supply lot: "Interested buyers"

### 6.5 Messaging Changes

**Thread creation** no longer requires an algorithmic match. Threads can be created from:
1. Clicking "Message" on a search result
2. Clicking "Message" on a watchlist item
3. Clicking "Message" on a suggestion card

All three create a WatchlistItem (if one doesn't exist) and a MessageThread (if one doesn't exist for that WatchlistItem).

**Thread detail page** stays structurally the same. The context card at the top shows the counterpart listing details. The `thread.watchlist_item` replaces `thread.match` for accessing the listing context.

**Thread access control:** Both participants (buyer and supplier from the WatchlistItem's listing context) can view and post to the thread. This rule is unchanged from V1.

---

## 7. Suggestion Engine

Suggestions reuse the existing matching algorithm but are **computed on the fly** rather than stored as Match records.

### Computation

```python
def get_suggestions_for_post(demand_post, user, limit=5):
    """Return suggested supply lots for a demand post."""
    # 1. Get active supply lots
    # 2. Filter by text overlap + location compatibility (existing logic)
    # 3. Exclude supply lots already on user's watchlist
    # 4. Exclude supply lots in user's dismissed suggestions
    # 5. Return top `limit` results

def get_suggestions_for_lot(supply_lot, user, limit=5):
    """Return suggested demand posts for a supply lot."""
    # Symmetric to above

def get_dashboard_suggestions(user, limit=5):
    """Aggregate suggestions across all user's active listings."""
    # For each active listing, get suggestions
    # Deduplicate (same counterpart listing suggested for multiple of my listings)
    # Return top `limit`
```

### Performance

On-the-fly computation runs the matching algorithm per page load. For V1 scale (small user base, limited listings), this is acceptable. Future optimization options:
- Short-TTL cache (e.g., 5 minutes)
- Background computation triggered on listing create/edit
- These are not needed for Pass 1 or Pass 2

---

## 8. Search Architecture

### 8.1 Embedding Service (Sidecar Architecture)

The SentenceTransformer model and ChromaDB run in a **standalone FastAPI sidecar process**, not inside Django. This avoids blocking Django with the 1-2 minute model cold-start on every restart. Django communicates with the service over a **Unix Domain Socket** using `httpx`.

```
Django  ──(Unix socket)──>  Embedding Service (FastAPI/uvicorn)
                              ├── SentenceTransformer model (loaded at startup)
                              └── ChromaDB (persistent, data/chroma/)
```

**Socket path:** `/tmp/ecommerceb2b-embedding.sock` (configurable via `EMBEDDING_SOCKET_PATH` env var)
**Auth:** Shared secret token in `X-Service-Token` header (from `EMBEDDING_SERVICE_TOKEN` env var)
**Protocol:** HTTP/JSON over Unix Domain Socket — no TCP port, no network exposure

**Service files:**
| File | Purpose |
|------|---------|
| `services/embedding/app.py` | FastAPI app with all endpoints |
| `services/embedding/requirements.txt` | Service deps (fastapi, uvicorn, chromadb, sentence-transformers) |
| `services/embedding/run.sh` | Startup script |

**Service endpoints:**
| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| POST | `/index` | Index/update a listing | `{id, text, metadata}` | `{ok: true}` |
| POST | `/search` | Semantic search | `{query, filters, limit}` | `{results: [{pk, distance}]}` |
| POST | `/remove` | Remove from index | `{id}` | `{ok: true}` |
| POST | `/rebuild` | Batch rebuild index | `{listings: [{id, text, metadata}]}` | `{ok, count}` |
| GET | `/health` | Readiness check | — | `{status, model_loaded, collection_count}` |

Search returns only PKs + distances. Django fetches full ORM objects. The adaptive cutoff algorithm lives in the service.

**Django client:** `marketplace/vector_search.py` is a thin HTTP client with the same public API (`index_listing`, `remove_listing`, `search_listings`, `rebuild_index`). No callers needed modification.

### 8.2 Vector Database — ChromaDB

**Choice:** ChromaDB as a standalone, file-based vector database. Fully decoupled from the relational database (works with both SQLite dev and PostgreSQL prod).

**Storage:** Persistent file-based storage at `data/chroma/` (added to `.gitignore`). Managed by the embedding sidecar service.

**Document structure per listing:**
```
id:        "supply_lot_123" or "demand_post_456"
embedding: [0.023, -0.117, ...]  (from item_text)
document:  "organic heirloom tomatoes"  (the item_text, for ChromaDB's internal use)
metadata:  {
  pk:               123,
  listing_type:     "supply_lot",
  status:           "active",
  category:         "food_fresh",
  location_country: "US",
  location_lat:     37.77,
  location_lng:     -122.41,
  created_by_id:    456
}
```

**Sync lifecycle:**
- Listing create → Django calls `index_listing()` → HTTP POST to sidecar → embed + upsert
- Listing edit → re-index if `item_text` changed, always update metadata
- Status change (withdraw/pause/expire/reactivate) → update via `index_listing()`
- ChromaDB is the secondary store; the Django ORM remains the source of truth

### 8.3 Embedding Model — Multilingual Sentence-Transformers

**Model:** `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers library)
- 384 dimensions
- Supports 50+ languages
- ~118MB model size, fast CPU inference (~5ms per short text)
- Loaded **eagerly at sidecar startup** (via FastAPI lifespan event), not lazily per-request

**i18n rationale:** A multilingual model is chosen deliberately to future-proof the architecture. Cross-language semantic matching works automatically: a French buyer searching "tomates biologiques" will find an English supplier's "organic tomatoes" because the model maps semantically equivalent text across languages to nearby vectors. This costs nothing extra versus an English-only model but makes the entire search architecture i18n-ready from day one.

**No external API dependencies.** Everything runs locally — no OpenAI, no network calls for embeddings.

### 8.4 Search Flow

1. User enters search term on `/discover/`
2. Django builds filter clause and POSTs to sidecar `/search` endpoint
3. Sidecar embeds search term, queries ChromaDB: top N results by cosine similarity, filtered by metadata:
   - `listing_type`: counterpart type based on user role
   - `status`: "active"
   - `created_by_id`: exclude own listings (`$ne` filter)
   - `category`: if specified by user
   - `location_country`: if specified by user
4. Sidecar applies adaptive cutoff algorithm, returns PKs + distances
5. Django fetches full listing records from ORM using returned PKs
6. Django applies post-retrieval filters in Python:
   - Radius filtering using lat/lng (Haversine — ChromaDB can't do geospatial)
   - Time-based expiration checks (`available_until`, `expires_at`)
7. Return results ranked by semantic similarity (lowest distance = best match)

### 8.5 Keyword Fallback

If ChromaDB is unavailable (empty collection, corrupted, first run before any listings indexed):
- Fall back to Django ORM `icontains` on `item_text`
- Apply same category, location, status filters
- Order by `-created_at`

This ensures the discover page always works, even before the vector index is populated.

### 8.6 Management Command — Rebuild Index

A `rebuild_vector_index` management command will be provided to re-index all active listings. Useful for:
- Initial setup after data import
- Recovery from corrupted ChromaDB data
- Reindexing after model upgrade

---

## 9. URL Structure

```
/discover/                    → Discover page (search)
/watchlist/                   → Watchlist page (starred/watching/archived)
/watchlist/<int:pk>/star/     → Toggle star on watchlist item (POST)
/watchlist/<int:pk>/archive/  → Archive watchlist item (POST)
/watchlist/<int:pk>/unarchive/ → Unarchive watchlist item (POST)
/watchlist/<int:pk>/delete/   → Remove from watchlist entirely (POST)
```

Existing URLs preserved:
```
/threads/<int:pk>/            → Thread detail (unchanged)
/demands/...                  → Demand post CRUD (unchanged)
/supply/...                   → Supply lot CRUD (unchanged)
```

Removed:
```
/matches/                     → Replaced by /watchlist/
/matches/history/             → Replaced by archived section of /watchlist/
```

New API-style endpoints (for "Save" and "Message" actions from search results — can be standard Django POST views, not necessarily JSON):
```
/discover/save/               → Save a listing to watchlist (POST, params: listing type + pk)
/discover/message/            → Save + create thread + redirect to thread (POST)
/suggestions/dismiss/         → Dismiss a suggestion (POST)
```

---

## 10. Implementation Scope

Single-pass implementation (semantic search included from the start).

**Scope:**
1. ~~Install dependencies: `chromadb`, `sentence-transformers`~~ → Extracted to sidecar service (`services/embedding/`). Django depends on `httpx` only.
2. New models: `WatchlistItem`, `WatchlistStatus`, `WatchlistSource`, `DismissedSuggestion`
3. Evolve `MessageThread`: replace `match` FK with `watchlist_item` FK
4. Remove `Match` model and `MatchStatus` enum (clean break after data reset)
5. Create `marketplace/vector_search.py`: HTTP client to embedding sidecar (same public API: index, search, remove, rebuild)
6. Create `rebuild_vector_index` management command
7. Discover page with semantic search + category + location/radius filters + keyword fallback
8. Watchlist page with starred/watching/archived sections
9. Dashboard "Suggested for you" section (on-the-fly computation)
10. Listing detail page "Suggested matches" section
11. Save/Message/Dismiss actions
12. Automatic watchlist archival when listings are withdrawn/paused/expired
13. Automatic watchlist restoration when listings are reactivated
14. Search value persistence via session
15. URL routing for all new pages and actions
16. Templates and CSS for all new views
17. Admin registration for new models
18. Update navbar with Discover and Watchlist links
19. Vector index sync on listing create/edit/toggle
20. DiscoverForm for search inputs

**Django dependency added:** `httpx` (for Unix socket communication with embedding sidecar)
**Sidecar dependencies:** `fastapi`, `uvicorn`, `chromadb`, `sentence-transformers` (+ `torch` transitive) — isolated in `services/embedding/requirements.txt`
**Models removed:** `Match`, `MatchStatus`
**New files:** `services/embedding/app.py`, `services/embedding/requirements.txt`, `services/embedding/run.sh`, `marketplace/vector_search.py`, `marketplace/management/commands/rebuild_vector_index.py`
**Files heavily modified:** `models.py`, `matching.py`, `views.py`, `urls.py`, `admin.py`, `forms.py`
**New templates:** `discover.html`, `watchlist.html`
**Modified templates:** `dashboard.html`, `supply_lot_detail.html`, `demand_post_detail.html`, `thread_detail.html`, `_navbar.html`

---

## 11. Migration Plan

**Data reset:** Per human direction, existing test data (including Match records, MessageThreads, Messages) will be cleared. This enables a clean schema transition without complex data migration.

**Steps:**
1. Flush database or drop/recreate tables
2. Remove `Match` model and `MatchStatus` from `models.py`
3. Remove `match_lifecycle` migration (0006) — squash or reset migrations if cleaner
4. Add new models (`WatchlistItem`, `DismissedSuggestion`)
5. Modify `MessageThread` to reference `WatchlistItem` instead of `Match`
6. Generate fresh migrations
7. Apply migrations to clean database
8. Remove reconciliation functions from `matching.py` (replaced by on-the-fly suggestions)
9. Preserve core matching utilities: `normalize`, `overlaps`, `location_compatible`, `_haversine_km`, `_within_radius`

**Code cleanup:**
- Remove from `views.py`: `_active_matches()`, `match_list`, `match_history`, match count annotations that reference Match
- Remove from `matching.py`: `evaluate_supply_lot`, `evaluate_demand_post`, `_create_match`, all reconciliation functions
- Remove `match_list.html`, `match_history.html` templates
- Remove `/matches/` and `/matches/history/` URL routes

---

## 12. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector database | ChromaDB (file-based, in sidecar) | Decoupled from RDBMS, works with SQLite dev and PostgreSQL prod. Runs in embedding sidecar, not in Django process. Listing PK stored as metadata acts as FK to RDBMS. |
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` (local, in sidecar) | 384 dims, 50+ languages, fast CPU inference, no external API. i18n-ready from day one — cross-language semantic matching works automatically. Loaded once at sidecar startup. |
| Embedding provider | Local sentence-transformers (no OpenAI) | No external dependencies, no API costs, no network calls. Sufficient quality for item text matching. |
| Embedding deployment | FastAPI sidecar over Unix Domain Socket | Model loads once at service start (1-2 min), not per Django restart. No TCP port exposure. Shared-secret auth via `X-Service-Token` header. Django uses `httpx` as HTTP client. |
| Suggestions storage | On the fly, not stored | User direction: "retrieved on the fly, fresh." Avoids staleness, no reconciliation needed. |
| Dismiss tracking | `DismissedSuggestion` model | Lightweight, prevents re-showing dismissed items. Separate from watchlist (dismissed ≠ archived). |
| MessageThread linkage | Via WatchlistItem | Clean: one thread per watchlist item. Messaging auto-creates watchlist item. |
| Search persistence | Django session | Simple, no model needed. Profile values used as initial defaults. |
| Search method | Semantic (ChromaDB) with keyword fallback | Semantic is primary. Keyword `icontains` fallback when ChromaDB unavailable. |
| Match model | Remove entirely | Clean break. Suggestion engine replaces it. Data reset makes this safe. |
| Watchlist auto-archival | On listing withdraw/pause/expire | Keeps watchlist in sync with listing lifecycle. Restore on reactivate. |
| Result limit | Default 20, "Load more" | Per human direction: simple, no selector needed. |

---

## 13. Non-Goals (V3)

These remain out of scope:
- Public (unauthenticated) browsing
- Payments, escrow, invoicing
- Auctions or bidding
- Ratings, reviews, reputation
- Mobile apps
- Real-time push notifications
- Advanced abuse detection

---

**END OF V3 SPEC**
