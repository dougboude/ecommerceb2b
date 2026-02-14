import math
import re

from django.utils import timezone

from .models import DemandPost, Match, MessageThread, SupplyLot

STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "for"}


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


def _create_match(demand_post, supply_lot):
    from .notifications import send_match_notification

    match, created = Match.objects.get_or_create(
        demand_post=demand_post,
        supply_lot=supply_lot,
    )
    if created:
        MessageThread.objects.get_or_create(
            match=match,
            defaults={
                "buyer": demand_post.created_by,
                "supplier": supply_lot.created_by,
            },
        )
        send_match_notification(match)
    return match, created


def _active_demand_posts():
    from django.db.models import Q
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


def evaluate_supply_lot(supply_lot):
    supply_tokens = normalize(supply_lot.item_text)
    if not supply_tokens:
        return
    for dp in _active_demand_posts():
        demand_tokens = normalize(dp.item_text)
        if overlaps(supply_tokens, demand_tokens) and location_compatible(supply_lot, dp):
            _create_match(dp, supply_lot)


def evaluate_demand_post(demand_post):
    demand_tokens = normalize(demand_post.item_text)
    if not demand_tokens:
        return
    for sl in _active_supply_lots():
        supply_tokens = normalize(sl.item_text)
        if overlaps(demand_tokens, supply_tokens) and location_compatible(sl, demand_post):
            _create_match(demand_post, sl)
