"""
Vector search client — talks to the embedding sidecar service over TCP (HTTP).
"""
import logging

import httpx
from django.conf import settings
from django.db.models import Q
from django.utils.timezone import now as timezone_now

from .models import Listing, ListingStatus, ListingType

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = httpx.Client(
            base_url=settings.EMBEDDING_SERVICE_URL,
            timeout=30.0,
            headers={"x-service-token": settings.EMBEDDING_SERVICE_TOKEN},
        )
    return _client


def _listing_id(listing):
    return f"listing_{listing.pk}"


def _listing_metadata(listing):
    meta = {
        "pk": listing.pk,
        "listing_type": listing.type,
        "status": listing.status,
        "category": listing.category or "",
        "location_country": listing.location_country,
        "created_by_id": listing.created_by_user_id,
    }
    if listing.location_lat is not None:
        meta["location_lat"] = listing.location_lat
    if listing.location_lng is not None:
        meta["location_lng"] = listing.location_lng
    return meta


def index_listing(listing):
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
    try:
        client = _get_client()
        client.post("/remove", json={"id": _listing_id(listing)})
    except Exception:
        logger.exception("Failed to remove listing %s", listing)


def _normalize_listing_type(listing_type):
    if listing_type in {"supply_lot", ListingType.SUPPLY}:
        return ListingType.SUPPLY
    if listing_type in {"demand_post", ListingType.DEMAND}:
        return ListingType.DEMAND
    return listing_type


def search_listings(query, listing_type, user, category=None, country=None, limit=20):
    try:
        listing_type = _normalize_listing_type(listing_type)
        client = _get_client()
        where_clause = {
            "$and": [
                {"listing_type": {"$eq": listing_type}},
                {"status": {"$eq": ListingStatus.ACTIVE}},
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
        results = resp.json().get("results", [])
        if not results:
            return []

        pks = [r["pk"] for r in results]
        distances_by_pk = {r["pk"]: r["distance"] for r in results}
        now = timezone_now()
        objects = {
            obj.pk: obj for obj in Listing.objects.filter(
                pk__in=pks,
                type=listing_type,
                status=ListingStatus.ACTIVE,
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        }
        ordered = []
        for pk in pks:
            obj = objects.get(pk)
            if obj is None:
                continue
            obj.search_distance = distances_by_pk.get(pk)
            ordered.append(obj)
        return ordered
    except Exception:
        logger.exception("Vector search failed")
        return []


def rebuild_index():
    try:
        client = _get_client()
        listings_payload = []
        for listing in Listing.objects.filter(status=ListingStatus.ACTIVE):
            listings_payload.append({
                "id": _listing_id(listing),
                "text": listing.item_text,
                "metadata": _listing_metadata(listing),
            })

        resp = client.post(
            "/rebuild",
            json={"listings": listings_payload},
            timeout=300.0,
        )
        resp.raise_for_status()
        return resp.json().get("count", 0)
    except Exception:
        logger.exception("Vector index rebuild failed")
        return 0
