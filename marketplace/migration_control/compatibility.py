from dataclasses import dataclass

from django.db import transaction

from marketplace.models import (
    BackfillAuditRecord,
    BackfillAuditStatus,
    DemandPost,
    LegacyToTargetMapping,
    Listing,
    ListingMessageThread,
    ListingWatchlistItem,
    ListingType,
    MessageThread,
    SupplyLot,
    WatchlistItem,
)

from .backfill import BackfillEngine
from .config import dual_read_enabled, dual_write_enabled, read_canonical, write_canonical


@dataclass
class WriteResult:
    ok: bool
    primary_pk: int | None = None
    shadow_pk: int | None = None
    error: str | None = None


class CompatibilityRepository:
    def __init__(self):
        self.backfill = BackfillEngine()

    @transaction.atomic
    def sync_listing_shadow(self, legacy_listing):
        if not dual_write_enabled() and write_canonical() != "target":
            return WriteResult(ok=True, primary_pk=legacy_listing.pk)

        try:
            if isinstance(legacy_listing, DemandPost):
                stats = self.backfill.backfill_listings()
                mapped = LegacyToTargetMapping.objects.filter(
                    entity_type="listing", legacy_pk=legacy_listing.pk,
                ).first()
                return WriteResult(ok=True, primary_pk=legacy_listing.pk, shadow_pk=mapped.target_pk if mapped else None)
            if isinstance(legacy_listing, SupplyLot):
                stats = self.backfill.backfill_listings()
                offset = DemandPost.objects.count()
                mapped = LegacyToTargetMapping.objects.filter(
                    entity_type="listing", legacy_pk=offset + legacy_listing.pk,
                ).first()
                return WriteResult(ok=True, primary_pk=legacy_listing.pk, shadow_pk=mapped.target_pk if mapped else None)
            return WriteResult(ok=False, error="Unsupported listing model")
        except Exception as exc:  # noqa: BLE001
            BackfillAuditRecord.objects.create(
                entity_type="listing",
                source_pk=getattr(legacy_listing, "pk", 0) or 0,
                target_pk=None,
                status=BackfillAuditStatus.FAILED,
                reason_code="dual_write_listing_error",
                details={"error": str(exc)},
            )
            return WriteResult(ok=False, error=str(exc))

    @transaction.atomic
    def sync_watchlist_shadow(self, watchlist_item: WatchlistItem) -> WriteResult:
        if not dual_write_enabled() and write_canonical() != "target":
            return WriteResult(ok=True, primary_pk=watchlist_item.pk)
        try:
            stats = self.backfill.backfill_threads_and_watchlist()
            mapped = LegacyToTargetMapping.objects.filter(
                entity_type="watchlist",
                legacy_pk=watchlist_item.pk,
            ).first()
            return WriteResult(ok=True, primary_pk=watchlist_item.pk, shadow_pk=mapped.target_pk if mapped else None)
        except Exception as exc:  # noqa: BLE001
            BackfillAuditRecord.objects.create(
                entity_type="watchlist",
                source_pk=watchlist_item.pk,
                target_pk=None,
                status=BackfillAuditStatus.FAILED,
                reason_code="dual_write_watchlist_error",
                details={"error": str(exc)},
            )
            return WriteResult(ok=False, error=str(exc))

    @transaction.atomic
    def sync_thread_shadow(self, thread: MessageThread) -> WriteResult:
        if not dual_write_enabled() and write_canonical() != "target":
            return WriteResult(ok=True, primary_pk=thread.pk)
        try:
            self.backfill.backfill_threads_and_watchlist()
            mapped = LegacyToTargetMapping.objects.filter(entity_type="thread", legacy_pk=thread.pk).first()
            return WriteResult(ok=True, primary_pk=thread.pk, shadow_pk=mapped.target_pk if mapped else None)
        except Exception as exc:  # noqa: BLE001
            BackfillAuditRecord.objects.create(
                entity_type="thread",
                source_pk=thread.pk,
                target_pk=None,
                status=BackfillAuditStatus.FAILED,
                reason_code="dual_write_thread_error",
                details={"error": str(exc)},
            )
            return WriteResult(ok=False, error=str(exc))

    def read_listing(self, *, listing_type: str, pk: int):
        canonical = read_canonical()
        if canonical == "target" and dual_read_enabled():
            target = Listing.objects.filter(pk=pk).first()
            if target:
                return target

        if listing_type == ListingType.DEMAND:
            return DemandPost.objects.filter(pk=pk).first()
        return SupplyLot.objects.filter(pk=pk).first()

    def read_target_watchlist(self, user_id: int):
        if read_canonical() == "target":
            return ListingWatchlistItem.objects.filter(user_id=user_id)
        return WatchlistItem.objects.filter(user_id=user_id)

    def read_target_threads(self, user_id: int):
        if read_canonical() == "target":
            return ListingMessageThread.objects.filter(created_by_user_id=user_id)
        return MessageThread.objects.filter(watchlist_item__user_id=user_id)
