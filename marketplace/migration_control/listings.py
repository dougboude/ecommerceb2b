from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q

from marketplace.migration_control.compatibility import CompatibilityRepository
from marketplace.migration_control.config import dual_read_enabled, read_canonical
from marketplace.models import (
    DemandPost,
    DemandStatus,
    Listing,
    ListingStatus,
    SupplyLot,
    SupplyStatus,
)


@dataclass
class ListingTransitionResult:
    ok: bool
    error: str | None = None


class ListingCompatibilityService:
    """
    Central listing adapter used by views during unification migration.
    """

    def __init__(self):
        self.repo = CompatibilityRepository()

    def discover_queryset(self, *, listing_type: str, query: str, category: str | None, country: str | None):
        if read_canonical() == "target" and dual_read_enabled():
            qs = Listing.objects.filter(type=listing_type, status=ListingStatus.ACTIVE)
            if query:
                qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))
            if category:
                qs = qs.filter(category=category)
            if country:
                qs = qs.filter(location_country=country)
            return list(qs.order_by("-created_at")[:20])
        return None

    @transaction.atomic
    def sync_shadow(self, legacy_listing):
        return self.repo.sync_listing_shadow(legacy_listing)

    @transaction.atomic
    def transition_status(self, legacy_listing, next_status: str) -> ListingTransitionResult:
        legacy_listing.status = next_status
        legacy_listing.save(update_fields=["status"])
        result = self.repo.sync_listing_shadow(legacy_listing)
        return ListingTransitionResult(ok=result.ok, error=result.error)

    @transaction.atomic
    def soft_delete(self, legacy_listing) -> ListingTransitionResult:
        if isinstance(legacy_listing, DemandPost):
            legacy_listing.status = DemandStatus.DELETED
        else:
            legacy_listing.status = SupplyStatus.DELETED
        legacy_listing.save(update_fields=["status"])
        result = self.repo.sync_listing_shadow(legacy_listing)
        return ListingTransitionResult(ok=result.ok, error=result.error)

    def target_listing_for_legacy(self, legacy_listing):
        if isinstance(legacy_listing, DemandPost):
            return Listing.objects.filter(
                legacy_source_type="demand_post",
                legacy_source_pk=legacy_listing.pk,
            ).first()
        return Listing.objects.filter(
            legacy_source_type="supply_lot",
            legacy_source_pk=legacy_listing.pk,
        ).first()
