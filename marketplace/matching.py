import math
import re

from django.db.models import Q
from django.utils import timezone

from .models import (
    DemandPost,
    DemandStatus,
    DismissedSuggestion,
    SupplyLot,
    SupplyStatus,
    WatchlistItem,
)

STOPWORDS = {
    # Original
    "the", "a", "an", "and", "or", "of", "to", "for",
    # Function words
    "in", "on", "at", "by", "with", "from", "is", "it", "we", "i", "my",
    "our", "your", "this", "that", "are", "was", "be", "have", "has", "do",
    "does", "not", "no", "but", "if", "so", "as", "up",
    # Food/ag descriptors
    "fresh", "organic", "farm", "natural", "local", "premium", "quality",
    "best", "new", "good", "great", "fine", "pure", "raw", "real",
    # Transactional
    "need", "needed", "looking", "want", "wanted", "preferred", "available",
    "sell", "selling", "buy", "buying", "offer", "offering", "seeking",
    "source", "sourcing",
    # Generic listing terms
    "supply", "supplies", "lot", "lots", "item", "items", "product",
    "products", "goods", "order", "orders",
    # Sizing / qualifiers
    "free", "range", "grade", "bulk", "wholesale", "retail", "small",
    "large", "medium", "high", "low",
}


def normalize(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    tokens = text.split()
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]


def overlaps(tokens_a, tokens_b):
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if set_a & set_b:
        return True
    str_a = " ".join(tokens_a)
    str_b = " ".join(tokens_b)
    if str_a in str_b or str_b in str_a:
        return True
    return False


def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


NORTH_AMERICA_COUNTRIES = {"US", "CA", "MX"}


def _within_radius(supply_lot, demand_post):
    """Check proximity using coords, postal code, or locality fallback."""
    if not demand_post.radius_km:
        return True
    if (
        supply_lot.location_lat is not None
        and supply_lot.location_lng is not None
        and demand_post.location_lat is not None
        and demand_post.location_lng is not None
    ):
        dist = _haversine_km(
            supply_lot.location_lat, supply_lot.location_lng,
            demand_post.location_lat, demand_post.location_lng,
        )
        return dist <= demand_post.radius_km
    if supply_lot.location_postal_code and demand_post.location_postal_code:
        return supply_lot.location_postal_code == demand_post.location_postal_code
    if supply_lot.location_locality and demand_post.location_locality:
        return (
            supply_lot.location_locality == demand_post.location_locality
            and supply_lot.location_region == demand_post.location_region
        )
    return True


def location_compatible(supply_lot, demand_post):
    same_country = supply_lot.location_country == demand_post.location_country

    if not demand_post.shipping_allowed:
        if not same_country:
            return False
        return _within_radius(supply_lot, demand_post)

    # Shipping allowed — check supplier's shipping scope
    scope = getattr(supply_lot, "shipping_scope", "local_only")
    if scope == "international":
        return True
    if scope == "north_america":
        if (
            supply_lot.location_country in NORTH_AMERICA_COUNTRIES
            and demand_post.location_country in NORTH_AMERICA_COUNTRIES
        ):
            return True
    if scope == "domestic":
        if same_country:
            return True
    # local_only or scope didn't cover it — fall through to radius check
    if not same_country:
        return False
    return _within_radius(supply_lot, demand_post)


# ---------------------------------------------------------------------------
# Active listing querysets
# ---------------------------------------------------------------------------

def _active_demand_posts():
    now = timezone.now()
    return DemandPost.objects.filter(
        status="active",
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
    )


def _active_supply_lots():
    now = timezone.now()
    return SupplyLot.objects.filter(
        status="active",
        available_until__gt=now,
    )


# ---------------------------------------------------------------------------
# Suggestion engine (on-the-fly, not stored)
# ---------------------------------------------------------------------------

def _excluded_supply_lot_ids(user):
    """Get supply lot IDs dismissed by the user (excluded from suggestions)."""
    return set(DismissedSuggestion.objects.filter(
        user=user, supply_lot__isnull=False,
    ).values_list("supply_lot_id", flat=True))


def _excluded_demand_post_ids(user):
    """Get demand post IDs dismissed by the user (excluded from suggestions)."""
    return set(DismissedSuggestion.objects.filter(
        user=user, demand_post__isnull=False,
    ).values_list("demand_post_id", flat=True))


def watchlisted_supply_lot_ids(user):
    """Get supply lot IDs on the user's watchlist."""
    return set(WatchlistItem.objects.filter(
        user=user, supply_lot__isnull=False,
    ).values_list("supply_lot_id", flat=True))


def watchlisted_demand_post_ids(user):
    """Get demand post IDs on the user's watchlist."""
    return set(WatchlistItem.objects.filter(
        user=user, demand_post__isnull=False,
    ).values_list("demand_post_id", flat=True))


def get_suggestions_for_post(demand_post, user, limit=5):
    """Return suggested supply lots for a demand post (on the fly)."""
    demand_tokens = normalize(demand_post.item_text)
    if not demand_tokens:
        return []
    excluded = _excluded_supply_lot_ids(user)
    results = []
    for sl in _active_supply_lots():
        if sl.pk in excluded:
            continue
        supply_tokens = normalize(sl.item_text)
        if overlaps(demand_tokens, supply_tokens) and location_compatible(sl, demand_post):
            results.append(sl)
            if len(results) >= limit:
                break
    return results


def get_suggestions_for_lot(supply_lot, user, limit=5):
    """Return suggested demand posts for a supply lot (on the fly)."""
    supply_tokens = normalize(supply_lot.item_text)
    if not supply_tokens:
        return []
    excluded = _excluded_demand_post_ids(user)
    results = []
    for dp in _active_demand_posts():
        if dp.pk in excluded:
            continue
        demand_tokens = normalize(dp.item_text)
        if overlaps(supply_tokens, demand_tokens) and location_compatible(supply_lot, dp):
            results.append(dp)
            if len(results) >= limit:
                break
    return results
