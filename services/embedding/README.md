# Embedding Service

Standalone sidecar that hosts the SentenceTransformer model and ChromaDB vector database. Django talks to it over a Unix Domain Socket — no TCP port, no network exposure.

```
Django  ──(Unix socket)──>  This service
                              ├── SentenceTransformer model (loaded once at startup)
                              └── ChromaDB (persistent storage)
```

## Why a sidecar?

The `paraphrase-multilingual-MiniLM-L12-v2` model takes 1-2 minutes to load into memory. When it lived inside Django, every Django restart forced users to wait through a cold start on their first search. Running it as a separate process means the model stays loaded across Django restarts.

## Model (Locked)

Current model: `paraphrase-multilingual-MiniLM-L12-v2`

**Important:** This model is intentionally locked. Changing it will
materially shift cosine distance distributions and can invalidate
the current cutoff logic. Any change requires a human-reviewed
re-evaluation of search quality and cutoff thresholds.

## Prerequisites

- Python 3.12+
- pip (a reasonably recent version; the system pip on Ubuntu may be too old)

## Installation

Use the **project venv** from the repo root (recommended for local dev):

```bash
# From the repo root
.venv/bin/pip install -r services/embedding/requirements.txt
```

Or create a dedicated venv for the service:

```bash
cd services/embedding
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### First run note

The SentenceTransformer model (~118 MB) is downloaded automatically on first startup and cached in `~/.cache/torch/sentence_transformers/`. Subsequent starts skip the download.

## Running

### Quick start

```bash
cd services/embedding
bash run.sh
```

### Manual start

```bash
cd services/embedding
uvicorn app:app --uds /tmp/ecommerceb2b-embedding.sock
```

### With a project-root venv

```bash
cd services/embedding
../../.venv/bin/uvicorn app:app --uds /tmp/ecommerceb2b-embedding.sock
```

The service logs will show:

```
INFO:     Loading SentenceTransformer model 'paraphrase-multilingual-MiniLM-L12-v2' ...
INFO:     Model loaded.
INFO:     ChromaDB ready at ../../data/chroma
INFO:     Started server process
INFO:     Uvicorn running on unix socket /tmp/ecommerceb2b-embedding.sock
```

Once you see "Uvicorn running on unix socket," the service is ready.

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_SOCKET_PATH` | `/tmp/ecommerceb2b-embedding.sock` | Unix socket path (used by `run.sh`) |
| `EMBEDDING_SERVICE_TOKEN` | `dev-token-change-me` | Shared secret for auth. Must match Django's `EMBEDDING_SERVICE_TOKEN` setting. |
| `CHROMA_PERSIST_DIR` | `../../data/chroma` | Where ChromaDB stores its data (relative to this directory, so defaults to `<repo>/data/chroma`) |

## API Reference

All endpoints except `/health` require the `X-Service-Token` header.

### `POST /index` - Index a listing

Add or update a single listing in the vector index.

**Request:**
```json
{
  "id": "supply_lot_42",
  "text": "Organic heirloom tomatoes, 500 lbs",
  "metadata": {
    "pk": 42,
    "listing_type": "supply_lot",
    "status": "active",
    "category": "food_fresh",
    "location_country": "US",
    "created_by_id": 7
  }
}
```

**Response:** `{"ok": true}`

### `POST /search` - Semantic search

Search for listings by semantic similarity. Returns PKs and distances only (Django fetches full objects from the ORM).

**Request:**
```json
{
  "query": "fresh organic tomatoes",
  "filters": {
    "$and": [
      {"listing_type": {"$eq": "supply_lot"}},
      {"status": {"$eq": "active"}},
      {"created_by_id": {"$ne": 7}}
    ]
  },
  "limit": 20
}
```

**Response:**
```json
{
  "results": [
    {"pk": 42, "distance": 0.12},
    {"pk": 88, "distance": 0.31}
  ]
}
```

Results are filtered through an adaptive cutoff algorithm that finds the natural cluster boundary in the distance distribution, discarding low-relevance results automatically.

#### Debugging flags (optional)

You can pass query parameters to inspect raw distances or bypass cutoff:

- `?debug=1` — include raw PKs + distances and the cutoff keep_count in the response.
- `?bypass_cutoff=1` — return all raw results without applying the adaptive cutoff.

Example:
```bash
curl --unix-socket /tmp/ecommerceb2b-embedding.sock \
  -H "X-Service-Token: dev-token-change-me" \
  -H "Content-Type: application/json" \
  -d '{ ... }' \
  "http://localhost/search?debug=1"
```

The `filters` object uses [ChromaDB where-clause syntax](https://docs.trychroma.com/guides#filtering-by-metadata).

### `POST /remove` - Remove a listing

**Request:**
```json
{"id": "supply_lot_42"}
```

**Response:** `{"ok": true}`

### `POST /rebuild` - Rebuild entire index

Deletes and recreates the index from scratch. Used by the `rebuild_vector_index` management command.

**Request:**
```json
{
  "listings": [
    {"id": "supply_lot_42", "text": "Organic tomatoes", "metadata": {"pk": 42, "...": "..."}},
    {"id": "demand_post_10", "text": "Looking for tomatoes", "metadata": {"pk": 10, "...": "..."}}
  ]
}
```

**Response:** `{"ok": true, "count": 2}`

### `GET /health` - Health check

No authentication required.

**Response:**
```json
{
  "status": "ok",
  "model_loaded": true,
  "collection_count": 147
}
```

## Verifying it works

```bash
# Health check
curl --unix-socket /tmp/ecommerceb2b-embedding.sock http://localhost/health

# From Django
.venv/bin/python manage.py rebuild_vector_index
```

## Troubleshooting

**"Connection refused" from Django**
The service isn't running. Start it with `bash run.sh` in `services/embedding/`.

**"Address already in use" on startup**
A stale socket file exists. `run.sh` handles this automatically, but if running uvicorn manually:
```bash
rm /tmp/ecommerceb2b-embedding.sock
```

**Model download hangs or fails**
The model is downloaded from Hugging Face on first run. If behind a proxy, set `HTTPS_PROXY`. If the download was interrupted, clear the cache:
```bash
rm -rf ~/.cache/torch/sentence_transformers/paraphrase-multilingual-MiniLM-L12-v2
```

**ChromaDB data is stale or corrupt**
Rebuild from Django:
```bash
.venv/bin/python manage.py rebuild_vector_index
```
Or delete the data directory and rebuild:
```bash
rm -rf data/chroma
.venv/bin/python manage.py rebuild_vector_index
```

**pip install fails with `AssertionError` in `get_topological_weights`**
Your pip is too old. Use the project venv's pip instead of the system pip:
```bash
../../.venv/bin/pip install -r requirements.txt
```
