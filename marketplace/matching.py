import math
import re

from django.db.models import Q
from django.utils import timezone

from .models import (
    DismissedSuggestion,
    Listing,
    ListingStatus,
    ListingType,
    WatchlistItem,
)

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for",
    "in", "on", "at", "by", "with", "from", "is", "it", "we", "i", "my",
    "our", "your", "this", "that", "are", "was", "be", "have", "has", "do",
    "does", "not", "no", "but", "if", "so", "as", "up",
    "fresh", "organic", "farm", "natural", "local", "premium", "quality",
    "best", "new", "good", "great", "fine", "pure", "raw", "real",
    "need", "needed", "looking", "want", "wanted", "preferred", "available",
    "sell", "selling", "buy", "buying", "offer", "offering", "seeking",
    "source", "sourcing",
    "supply", "supplies", "lot", "lots", "item", "items", "product",
    "products", "goods", "order", "orders",
    "free", "range", "grade", "bulk", "wholesale", "retail", "small",
    "large", "medium", "high", "low",
}

NORTH_AMERICA_COUNTRIES = {"US", "CA", "MX"}


def normalize(text):
    text = (text or "").lower().strip()
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
    return bool(str_a and str_b and (str_a in str_b or str_b in str_a))


def _haversine_km(lat1, lng1, lat2, lng2):
    radius_km = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _within_radius(supply_listing, demand_listing):
    if not demand_listing.radius_km:
        return True
    if (
        supply_listing.location_lat is not None
        and supply_listing.location_lng is not None
        and demand_listing.location_lat is not None
        and demand_listing.location_lng is not None
    ):
        dist = _haversine_km(
            supply_listing.location_lat,
            supply_listing.location_lng,
            demand_listing.location_lat,
            demand_listing.location_lng,
        )
        return dist <= demand_listing.radius_km
    if supply_listing.location_postal_code and demand_listing.location_postal_code:
        return supply_listing.location_postal_code == demand_listing.location_postal_code
    if supply_listing.location_locality and demand_listing.location_locality:
        return (
            supply_listing.location_locality == demand_listing.location_locality
            and supply_listing.location_region == demand_listing.location_region
        )
    return True


def location_compatible(supply_listing, demand_listing):
    same_country = supply_listing.location_country == demand_listing.location_country

    scope = getattr(supply_listing, "shipping_scope", "")
    if scope == "worldwide":
        return True
    if scope == "north_america":
        if (
            supply_listing.location_country in NORTH_AMERICA_COUNTRIES
            and demand_listing.location_country in NORTH_AMERICA_COUNTRIES
        ):
            return True
    if scope == "domestic" and same_country:
        return True
    if not same_country:
        return False
    return _within_radius(supply_listing, demand_listing)


def _active_listings(listing_type):
    now = timezone.now()
    qs = Listing.objects.filter(type=listing_type, status=ListingStatus.ACTIVE)
    if listing_type == ListingType.SUPPLY:
        qs = qs.filter(expires_at__gt=now)
    else:
        qs = qs.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    return qs


def _excluded_listing_ids(user):
    return set(DismissedSuggestion.objects.filter(user=user, listing__isnull=False).values_list("listing_id", flat=True))


def _watchlisted_listing_ids(user):
    return set(WatchlistItem.objects.filter(user=user, listing__isnull=False).values_list("listing_id", flat=True))


def watchlisted_supply_lot_ids(user):
    return set(
        WatchlistItem.objects.filter(
            user=user,
            listing__type=ListingType.SUPPLY,
        ).values_list("listing_id", flat=True)
    )


def watchlisted_demand_post_ids(user):
    return set(
        WatchlistItem.objects.filter(
            user=user,
            listing__type=ListingType.DEMAND,
        ).values_list("listing_id", flat=True)
    )


def bulk_suggestion_counts(user_listings, user, listing_side="supply"):
    if listing_side == "supply":
        counterparts = list(_active_listings(ListingType.DEMAND))
    else:
        counterparts = list(_active_listings(ListingType.SUPPLY))

    dismissed = _excluded_listing_ids(user)
    watchlisted = _watchlisted_listing_ids(user)

    cp_data = []
    for counterpart in counterparts:
        if counterpart.pk in dismissed:
            continue
        tokens = normalize(counterpart.item_text)
        if tokens:
            cp_data.append((counterpart, tokens))

    results = {}
    for listing in user_listings:
        listing_tokens = normalize(listing.item_text)
        if not listing_tokens:
            results[listing.pk] = (0, 0)
            continue

        unsaved = 0
        saved = 0
        for counterpart, cp_tokens in cp_data:
            if not overlaps(listing_tokens, cp_tokens):
                continue
            if listing_side == "supply":
                if not location_compatible(listing, counterpart):
                    continue
            else:
                if not location_compatible(counterpart, listing):
                    continue
            if counterpart.pk in watchlisted:
                saved += 1
            else:
                unsaved += 1
        results[listing.pk] = (unsaved, saved)
    return results


def get_suggestions_for_listing(listing, user, limit=5):
    listing_tokens = normalize(listing.item_text)
    if not listing_tokens:
        return []
    counterpart_type = ListingType.DEMAND if listing.type == ListingType.SUPPLY else ListingType.SUPPLY
    excluded = _excluded_listing_ids(user)
    results = []
    for counterpart in _active_listings(counterpart_type):
        if counterpart.pk in excluded:
            continue
        counterpart_tokens = normalize(counterpart.item_text)
        if not overlaps(listing_tokens, counterpart_tokens):
            continue
        if listing.type == ListingType.SUPPLY:
            if not location_compatible(listing, counterpart):
                continue
        else:
            if not location_compatible(counterpart, listing):
                continue
        results.append(counterpart)
        if len(results) >= limit:
            break
    return results


def get_suggestions_for_post(demand_post, user, limit=5):
    return get_suggestions_for_listing(demand_post, user, limit=limit)


def get_suggestions_for_lot(supply_lot, user, limit=5):
    return get_suggestions_for_listing(supply_lot, user, limit=limit)
