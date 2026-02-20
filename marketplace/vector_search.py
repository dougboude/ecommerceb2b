"""
Vector search client — talks to the embedding sidecar service over a
Unix Domain Socket.  Same public API as before so no callers need to change.

The sidecar (services/embedding/app.py) holds the SentenceTransformer model
and ChromaDB; this module is now a thin HTTP client.
"""
import logging

import httpx
from django.conf import settings

from .models import DemandPost, SupplyLot

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTTP client (lazy singleton — cheap to create, no model loading)
# ---------------------------------------------------------------------------
_client = None


def _get_client():
    global _client
    if _client is None:
        socket_path = getattr(
            settings, "EMBEDDING_SOCKET_PATH", "/tmp/ecommerceb2b-embedding.sock"
        )
        transport = httpx.HTTPTransport(uds=socket_path)
        _client = httpx.Client(
            transport=transport,
            base_url="http://embedding-service",
            timeout=30.0,
            headers={
                "x-service-token": getattr(
                    settings, "EMBEDDING_SERVICE_TOKEN", "dev-token-change-me"
                ),
            },
        )
    return _client


# ---------------------------------------------------------------------------
# Helpers (unchanged public interface)
# ---------------------------------------------------------------------------
def _listing_id(listing):
    """Generate a document ID from a listing."""
    if isinstance(listing, SupplyLot):
        return f"supply_lot_{listing.pk}"
    return f"demand_post_{listing.pk}"


def _listing_metadata(listing):
    """Build metadata dict for a listing."""
    if isinstance(listing, SupplyLot):
        listing_type = "supply_lot"
    else:
        listing_type = "demand_post"
    meta = {
        "pk": listing.pk,
        "listing_type": listing_type,
        "status": listing.status,
        "category": listing.category or "",
        "location_country": listing.location_country,
        "created_by_id": listing.created_by_id,
    }
    if listing.location_lat is not None:
        meta["location_lat"] = listing.location_lat
    if listing.location_lng is not None:
        meta["location_lng"] = listing.location_lng
    return meta


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def index_listing(listing):
    """Add or update a listing in the vector index."""
    try:
        client = _get_client()
        client.post("/index", json={
            "id": _listing_id(listing),
            "text": listing.item_text,
            "metadata": _listing_metadata(listing),
        })
    except Exception:
        logger.exception("Failed to index listing %s", listing)


def remove_listing(listing):
    """Remove a listing from the vector index."""
    try:
        client = _get_client()
        client.post("/remove", json={
            "id": _listing_id(listing),
        })
    except Exception:
        logger.exception("Failed to remove listing %s", listing)


def search_listings(query, listing_type, user, category=None, country=None, limit=20):
    """
    Search for listings by semantic similarity.

    Returns a list of Django model instances (SupplyLot or DemandPost),
    ordered by relevance (best match first). Each instance gets a
    `search_distance` attribute with the cosine distance score.

    Adaptive thresholding is applied server-side by the embedding service.
    """
    try:
        client = _get_client()

        # Build ChromaDB-style where clause (service passes it through)
        where_clause = {
            "$and": [
                {"listing_type": {"$eq": listing_type}},
                {"status": {"$eq": "active"}},
                {"created_by_id": {"$ne": user.pk}},
            ]
        }
        if category:
            where_clause["$and"].append({"category": {"$eq": category}})
        if country:
            where_clause["$and"].append({"location_country": {"$eq": country}})

        resp = client.post("/search", json={
            "query": query,
            "filters": where_clause,
            "limit": limit,
        })
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            return []

        pks = [r["pk"] for r in results]
        distances_by_pk = {r["pk"]: r["distance"] for r in results}

        # Fetch full objects from Django ORM, preserving relevance order
        if listing_type == "supply_lot":
            objects = {obj.pk: obj for obj in SupplyLot.objects.filter(pk__in=pks)}
        else:
            objects = {obj.pk: obj for obj in DemandPost.objects.filter(pk__in=pks)}

        ordered = []
        for pk in pks:
            if pk in objects:
                obj = objects[pk]
                obj.search_distance = distances_by_pk.get(pk)
                ordered.append(obj)
        return ordered

    except Exception:
        logger.exception("Vector search failed")
        return []


def rebuild_index():
    """Rebuild the entire vector index from all listings."""
    try:
        client = _get_client()

        # Collect all listings from ORM
        listings_payload = []

        for lot in SupplyLot.objects.all():
            listings_payload.append({
                "id": _listing_id(lot),
                "text": lot.item_text,
                "metadata": _listing_metadata(lot),
            })

        for post in DemandPost.objects.all():
            listings_payload.append({
                "id": _listing_id(post),
                "text": post.item_text,
                "metadata": _listing_metadata(post),
            })

        resp = client.post(
            "/rebuild",
            json={"listings": listings_payload},
            timeout=300.0,  # rebuild can take a while
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("count", 0)

    except Exception:
        logger.exception("Vector index rebuild failed")
        return 0
