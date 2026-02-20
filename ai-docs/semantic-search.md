# Semantic Search — End-to-End Behavior

**Scope:** This document describes how semantic search works in this project today, from indexing through query results. It is descriptive only; any changes to result qualification or cutoff logic require a human-in-the-loop decision.

## High-Level Flow
1. Listings are indexed into ChromaDB by the embedding sidecar service.
2. Discover search in Django calls the sidecar over a Unix Domain Socket.
3. The sidecar returns a list of PKs and cosine distances.
4. Django loads full ORM objects by PK and returns them to the view.

## Components

### 1) Django (caller)
Files:
- `marketplace/views.py`
- `marketplace/vector_search.py`
- `marketplace/management/commands/rebuild_vector_index.py`
- `config/settings.py`

Entry point:
- `discover_view()` in `marketplace/views.py` calls `_run_discover_search()`.
- `_run_discover_search()` chooses:
  - keyword search (`_keyword_search`) if user selects "keyword"
  - semantic search via `vector_search.search_listings()` otherwise

Filters used for semantic search:
- `listing_type` (supply_lot vs demand_post)
- `status == "active"`
- `created_by_id != user.pk`
- optional `category`
- optional `location_country`

Note: semantic search does not apply distance/radius or expiration checks in Django; it relies on metadata filters only.

Index sync calls:
- `marketplace/views.py` calls:
  - `_sync_listing_to_vector_index()` after create/edit/toggle (if active)
  - `_remove_listing_from_vector_index()` on delete
- Both helpers silently ignore errors (logging in the client, but exceptions are swallowed).

Index rebuild:
- `manage.py rebuild_vector_index` calls `marketplace.vector_search.rebuild_index()`.

### 2) Vector Search Client (Django side)
File:
- `marketplace/vector_search.py`

Responsibilities:
- Builds listing metadata used for filtering in ChromaDB.
- Sends requests to the embedding service over UDS with `httpx`.

Metadata fields:
- `pk`
- `listing_type` ("supply_lot" or "demand_post")
- `status`
- `category` (empty string if blank)
- `location_country`
- `created_by_id`
- optional `location_lat`, `location_lng`

Response handling:
- Receives `[{pk, distance}, ...]` from sidecar.
- Loads ORM objects by PK and preserves the relevance order.
- Adds `search_distance` attribute to each object.

### 3) Embedding Sidecar (FastAPI + ChromaDB)
Files:
- `services/embedding/app.py`
- `services/embedding/README.md`

Model:
- `paraphrase-multilingual-MiniLM-L12-v2`

**Important:** This model is intentionally locked. Changing it will
materially shift cosine distance distributions and can invalidate
the current cutoff logic. Any change requires a human-reviewed
re-evaluation of search quality and cutoff thresholds.

Endpoints:
- `POST /index` — index or update one listing
- `POST /search` — query embeddings, filter by metadata, return PKs + distances
- `POST /remove` — remove one listing
- `POST /rebuild` — rebuild the entire index
- `GET /health` — readiness check (unauthenticated)

Auth:
- All endpoints except `/health` require `X-Service-Token`.

ChromaDB:
- Persistent client at `CHROMA_PERSIST_DIR` (default `data/chroma`).
- Collection: `listings`, cosine distance.

Search behavior:
- Uses ChromaDB `where` filter passed from Django.
- Returns cosine distances for matched results.
- Applies an adaptive cutoff to drop low-quality results before returning.
- Optional debugging flags:
  - `?debug=1` — include raw distances and keep_count
  - `?bypass_cutoff=1` — return all raw results without cutoff

## Distance Cutoff Algorithm (Authoritative)
File: `services/embedding/app.py`

Constants:
- `QUALITY_FLOOR = 0.50`
- `GAP_MULTIPLIER = 2.5`
- `MAX_DISTANCE = 0.75`
- `AVG_FLOOR = 0.01`

Inputs:
- A list of distances sorted ascending (best match first) as returned by ChromaDB.

Algorithm (exact behavior):
1. If no distances → return 0 results.
2. If the best distance is > `QUALITY_FLOOR` (0.50) → return 0 results.
3. Drop any distances > `MAX_DISTANCE` (0.75). If none remain → return 0 results.
4. If only 1 distance remains → keep 1.
5. Compute gaps between adjacent distances: `gap[i] = d[i+1] - d[i]`.
6. If only one gap:
   - If `gap[0] > d[0]`, keep 1.
   - Else keep all.
7. If multiple gaps, scan for a “large” gap using `GAP_MULTIPLIER`:
   - For i == 0:
     - baseline = max(average of gaps[1:], `AVG_FLOOR`)
     - if gap[0] / baseline >= `GAP_MULTIPLIER`, keep 1.
   - For i > 0:
     - baseline = max(average of gaps[:i], `AVG_FLOOR`)
     - if gap[i] / baseline >= `GAP_MULTIPLIER`, keep i+1.
8. If no large gap is found → keep all remaining distances.

Output:
- `keep_count` = number of results returned.
- Results are truncated to the first `keep_count` matches.

Notes:
- All cutoff logic is executed in the sidecar, not Django.
- Django trusts the returned PK list as “qualified.”

## Where “Qualified Results” Are Determined
The **only** automatic result-quality logic is the adaptive cutoff in the sidecar:
- `services/embedding/app.py` → `_find_adaptive_cutoff()`

All other filtering is metadata-based and comes from Django.

## Known Behavior Notes (Descriptive)
- Keyword mode is pure ORM `icontains` AND matching across all words.
- Semantic mode uses embedding distance only, not item_text token overlap.
- Semantic results do not currently enforce:
  - demand radius in miles/km
  - supply `available_until > now()`
  - demand `expires_at > now()`

These are current behaviors, not recommendations.

## Files to Inspect for Any Future Changes
- `services/embedding/app.py` (distance cutoff and model)
- `marketplace/vector_search.py` (filters, metadata)
- `marketplace/views.py` (discover flow, keyword search)
- `marketplace/matching.py` (suggestions engine, not semantic search)
