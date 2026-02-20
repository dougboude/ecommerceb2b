"""
Embedding sidecar service.

Loads SentenceTransformer model + ChromaDB at startup and exposes
search/index/remove/rebuild over HTTP (Unix Domain Socket).

Start with:  uvicorn app:app --uds /tmp/ecommerceb2b-embedding.sock
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("embedding_service")
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# NOTE: Model choice is intentionally locked. Changing the model will
# materially shift cosine distance distributions and invalidates current
# cutoff behavior unless re-evaluated with a human-in-the-loop.
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "listings"
CHROMA_PERSIST_DIR = os.environ.get("CHROMA_PERSIST_DIR", "../../data/chroma")
SERVICE_TOKEN = os.environ.get("EMBEDDING_SERVICE_TOKEN", "dev-token-change-me")

# ---------------------------------------------------------------------------
# Globals (populated at startup)
# ---------------------------------------------------------------------------
embedding_model = None
chroma_client = None


def _get_collection():
    return chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Adaptive cutoff (moved from Django)
# ---------------------------------------------------------------------------
QUALITY_FLOOR = 0.50
GAP_MULTIPLIER = 2.5
MAX_DISTANCE = 0.75
AVG_FLOOR = 0.01


def _find_adaptive_cutoff(distances):
    """Find the natural break point in sorted distances."""
    if not distances:
        return 0
    if distances[0] > QUALITY_FLOOR:
        return 0
    distances = [d for d in distances if d <= MAX_DISTANCE]
    if not distances:
        return 0
    if len(distances) == 1:
        return 1

    gaps = [distances[i + 1] - distances[i] for i in range(len(distances) - 1)]

    if len(gaps) == 1:
        if gaps[0] > distances[0]:
            return 1
        return len(distances)

    for i in range(len(gaps)):
        if i == 0:
            avg_rest = sum(gaps[1:]) / len(gaps[1:])
            baseline = max(avg_rest, AVG_FLOOR)
            if gaps[0] / baseline >= GAP_MULTIPLIER:
                return 1
        else:
            avg_prior = sum(gaps[:i]) / i
            baseline = max(avg_prior, AVG_FLOOR)
            if gaps[i] / baseline >= GAP_MULTIPLIER:
                return i + 1
    return len(distances)


# ---------------------------------------------------------------------------
# Lifespan — load model and ChromaDB once at startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedding_model, chroma_client

    logger.info("Loading SentenceTransformer model '%s' ...", MODEL_NAME)
    from sentence_transformers import SentenceTransformer
    embedding_model = SentenceTransformer(MODEL_NAME)
    logger.info("Model loaded.")

    import chromadb
    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    logger.info("ChromaDB ready at %s", CHROMA_PERSIST_DIR)

    yield

    logger.info("Shutting down embedding service.")


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def check_service_token(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    token = request.headers.get("x-service-token", "")
    if token != SERVICE_TOKEN:
        return JSONResponse(status_code=401, content={"error": "invalid token"})
    return await call_next(request)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class IndexRequest(BaseModel):
    id: str
    text: str
    metadata: dict


class SearchRequest(BaseModel):
    query: str
    filters: dict | None = None
    limit: int = 20


class RemoveRequest(BaseModel):
    id: str


class RebuildRequest(BaseModel):
    listings: list[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/index")
async def index_listing(req: IndexRequest):
    collection = _get_collection()
    emb = embedding_model.encode(req.text, convert_to_numpy=True).tolist()
    collection.upsert(
        ids=[req.id],
        embeddings=[emb],
        documents=[req.text],
        metadatas=[req.metadata],
    )
    return {"ok": True}


@app.post("/search")
async def search(req: SearchRequest, debug: int = 0, bypass_cutoff: int = 0):
    collection = _get_collection()
    count = collection.count()
    if count == 0:
        return {"results": []}

    emb = embedding_model.encode(req.query, convert_to_numpy=True).tolist()

    where_clause = req.filters if req.filters else None

    results = collection.query(
        query_embeddings=[emb],
        n_results=min(req.limit, count),
        where=where_clause,
        include=["metadatas", "distances"],
    )

    if not results or not results["ids"] or not results["ids"][0]:
        return {"results": []}

    all_pks = []
    all_distances = []
    for meta, distance in zip(results["metadatas"][0], results["distances"][0]):
        all_pks.append(meta["pk"])
        all_distances.append(distance)

    if bypass_cutoff:
        return {
            "results": [
                {"pk": pk, "distance": dist}
                for pk, dist in zip(all_pks, all_distances)
            ],
            "debug": {
                "bypass_cutoff": True,
                "raw_count": len(all_distances),
            },
        }

    keep_count = _find_adaptive_cutoff(all_distances)
    if keep_count == 0:
        if debug:
            return {
                "results": [],
                "debug": {
                    "bypass_cutoff": False,
                    "raw_count": len(all_distances),
                    "raw_pks": all_pks,
                    "raw_distances": all_distances,
                    "keep_count": 0,
                },
            }
        return {"results": []}

    response = {
        "results": [
            {"pk": pk, "distance": dist}
            for pk, dist in zip(all_pks[:keep_count], all_distances[:keep_count])
        ]
    }
    if debug:
        response["debug"] = {
            "bypass_cutoff": False,
            "raw_count": len(all_distances),
            "raw_pks": all_pks,
            "raw_distances": all_distances,
            "keep_count": keep_count,
        }
    return response


@app.post("/remove")
async def remove_listing(req: RemoveRequest):
    collection = _get_collection()
    collection.delete(ids=[req.id])
    return {"ok": True}


@app.post("/rebuild")
async def rebuild(req: RebuildRequest):
    # Delete and recreate collection
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = _get_collection()
    indexed = 0
    for item in req.listings:
        try:
            emb = embedding_model.encode(item["text"], convert_to_numpy=True).tolist()
            collection.upsert(
                ids=[item["id"]],
                embeddings=[emb],
                documents=[item["text"]],
                metadatas=[item["metadata"]],
            )
            indexed += 1
        except Exception:
            logger.exception("Failed to index item %s", item.get("id"))

    return {"ok": True, "count": indexed}


@app.get("/health")
async def health():
    collection = _get_collection()
    return {
        "status": "ok",
        "model_loaded": embedding_model is not None,
        "collection_count": collection.count(),
    }
