from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q

from marketplace.models import Listing, ListingStatus


@dataclass
class ListingTransitionResult:
    ok: bool
    error: str | None = None


class ListingCompatibilityService:
    """Post-CP5 canonical listing service."""

    def discover_queryset(self, *, listing_type: str, query: str, category: str | None, country: str | None):
        qs = Listing.objects.filter(type=listing_type, status=ListingStatus.ACTIVE)
        if query:
            qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))
        if category:
            qs = qs.filter(category=category)
        if country:
            qs = qs.filter(location_country=country)
        return list(qs.order_by("-created_at")[:20])

    @transaction.atomic
    def sync_shadow(self, legacy_listing):
        return ListingTransitionResult(ok=True)

    @transaction.atomic
    def transition_status(self, legacy_listing, next_status: str) -> ListingTransitionResult:
        legacy_listing.status = next_status
        legacy_listing.save(update_fields=["status"])
        return ListingTransitionResult(ok=True)

    @transaction.atomic
    def soft_delete(self, legacy_listing) -> ListingTransitionResult:
        legacy_listing.status = ListingStatus.DELETED
        legacy_listing.save(update_fields=["status"])
        return ListingTransitionResult(ok=True)

    def target_listing_for_legacy(self, legacy_listing):
        return None
