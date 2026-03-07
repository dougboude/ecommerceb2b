from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from marketplace.models import (
    BackfillAuditRecord,
    BackfillAuditStatus,
    DemandPost,
    DemandStatus,
    LegacyToTargetMapping,
    Listing,
    ListingMessageThread,
    ListingShippingScope,
    ListingStatus,
    ListingType,
    ListingWatchlistItem,
    MessageThread,
    SupplyLot,
    SupplyStatus,
    User,
    WatchlistItem,
    WatchlistSource,
    WatchlistStatus,
)
from marketplace.migration_control.identity import IdentityCompatibilityAdapter


STATUS_MAP_DEMAND = {
    DemandStatus.ACTIVE: ListingStatus.ACTIVE,
    DemandStatus.PAUSED: ListingStatus.PAUSED,
    DemandStatus.FULFILLED: ListingStatus.FULFILLED,
    DemandStatus.EXPIRED: ListingStatus.EXPIRED,
    DemandStatus.DELETED: ListingStatus.DELETED,
}

STATUS_MAP_SUPPLY = {
    SupplyStatus.ACTIVE: ListingStatus.ACTIVE,
    SupplyStatus.WITHDRAWN: ListingStatus.WITHDRAWN,
    SupplyStatus.EXPIRED: ListingStatus.EXPIRED,
    SupplyStatus.DELETED: ListingStatus.DELETED,
}

SHIPPING_MAP = {
    "local_only": ListingShippingScope.LOCAL_ONLY,
    "domestic": ListingShippingScope.DOMESTIC,
    "north_america": ListingShippingScope.NORTH_AMERICA,
    "international": ListingShippingScope.WORLDWIDE,
}


@dataclass
class BackfillStats:
    processed: int = 0
    success: int = 0
    failed: int = 0


class BackfillEngine:
    @transaction.atomic
    def backfill_users(self) -> BackfillStats:
        stats = BackfillStats()
        adapter = IdentityCompatibilityAdapter()
        processed, success, failed = adapter.backfill_org_names()
        stats.processed = processed
        stats.success = success
        stats.failed = failed
        return stats

    @transaction.atomic
    def backfill_listings(self) -> BackfillStats:
        stats = BackfillStats()
        for post in DemandPost.objects.all():
            stats.processed += 1
            try:
                listing, _ = Listing.objects.update_or_create(
                    legacy_source_type="demand_post",
                    legacy_source_pk=post.pk,
                    defaults={
                        "type": ListingType.DEMAND,
                        "created_by_user": post.created_by,
                        "title": post.item_text[:255],
                        "description": post.notes,
                        "category": post.category,
                        "status": STATUS_MAP_DEMAND.get(post.status, ListingStatus.ACTIVE),
                        "location_country": post.location_country,
                        "location_locality": post.location_locality,
                        "location_region": post.location_region,
                        "location_postal_code": post.location_postal_code,
                        "location_lat": post.location_lat,
                        "location_lng": post.location_lng,
                        "quantity": Decimal(post.quantity_value) if post.quantity_value is not None else None,
                        "unit": post.quantity_unit,
                        "radius_km": post.radius_km,
                        "frequency": post.frequency,
                        "expires_at": post.expires_at,
                        "created_at": post.created_at,
                    },
                )
                LegacyToTargetMapping.objects.update_or_create(
                    entity_type="listing",
                    legacy_pk=post.pk,
                    defaults={"target_pk": listing.pk, "mapping_version": 1},
                )
                self._audit("listing", post.pk, listing.pk, BackfillAuditStatus.SUCCESS, "demand_post_backfilled")
                stats.success += 1
            except Exception as exc:  # noqa: BLE001
                self._audit("listing", post.pk, None, BackfillAuditStatus.FAILED, f"demand_post_failed:{exc}")
                stats.failed += 1

        offset = DemandPost.objects.count()
        for lot in SupplyLot.objects.all():
            stats.processed += 1
            try:
                listing, _ = Listing.objects.update_or_create(
                    legacy_source_type="supply_lot",
                    legacy_source_pk=lot.pk,
                    defaults={
                        "type": ListingType.SUPPLY,
                        "created_by_user": lot.created_by,
                        "title": lot.item_text[:255],
                        "description": lot.notes,
                        "category": lot.category,
                        "status": STATUS_MAP_SUPPLY.get(lot.status, ListingStatus.ACTIVE),
                        "location_country": lot.location_country,
                        "location_locality": lot.location_locality,
                        "location_region": lot.location_region,
                        "location_postal_code": lot.location_postal_code,
                        "location_lat": lot.location_lat,
                        "location_lng": lot.location_lng,
                        "quantity": Decimal(lot.quantity_value) if lot.quantity_value is not None else None,
                        "unit": lot.quantity_unit,
                        "price_value": Decimal(lot.asking_price) if lot.asking_price is not None else None,
                        "price_unit": lot.price_unit,
                        "shipping_scope": SHIPPING_MAP.get(lot.shipping_scope, ListingShippingScope.LOCAL_ONLY),
                        "expires_at": lot.available_until,
                        "created_at": lot.created_at,
                    },
                )
                LegacyToTargetMapping.objects.update_or_create(
                    entity_type="listing",
                    legacy_pk=offset + lot.pk,
                    defaults={"target_pk": listing.pk, "mapping_version": 1},
                )
                self._audit("listing", offset + lot.pk, listing.pk, BackfillAuditStatus.SUCCESS, "supply_lot_backfilled")
                stats.success += 1
            except Exception as exc:  # noqa: BLE001
                self._audit("listing", offset + lot.pk, None, BackfillAuditStatus.FAILED, f"supply_lot_failed:{exc}")
                stats.failed += 1
        return stats

    @transaction.atomic
    def backfill_threads_and_watchlist(self) -> BackfillStats:
        stats = BackfillStats()

        for item in WatchlistItem.objects.select_related("supply_lot", "demand_post", "user"):
            stats.processed += 1
            listing = None
            if item.supply_lot_id:
                listing = Listing.objects.filter(
                    legacy_source_type="supply_lot",
                    legacy_source_pk=item.supply_lot_id,
                ).first()
            elif item.demand_post_id:
                listing = Listing.objects.filter(
                    legacy_source_type="demand_post",
                    legacy_source_pk=item.demand_post_id,
                ).first()

            if not listing:
                self._audit("watchlist", item.pk, None, BackfillAuditStatus.FAILED, "missing_target_listing")
                stats.failed += 1
                continue

            target_item, _ = ListingWatchlistItem.objects.update_or_create(
                user=item.user,
                listing=listing,
                defaults={"status": item.status, "source": item.source},
            )
            LegacyToTargetMapping.objects.update_or_create(
                entity_type="watchlist",
                legacy_pk=item.pk,
                defaults={"target_pk": target_item.pk, "mapping_version": 1},
            )
            self._audit("watchlist", item.pk, target_item.pk, BackfillAuditStatus.SUCCESS, "watchlist_backfilled")
            stats.success += 1

        for thread in MessageThread.objects.select_related("watchlist_item"):
            stats.processed += 1
            target_watchlist = None
            if thread.watchlist_item_id:
                mapped = LegacyToTargetMapping.objects.filter(
                    entity_type="watchlist",
                    legacy_pk=thread.watchlist_item_id,
                ).first()
                if mapped:
                    target_watchlist = ListingWatchlistItem.objects.filter(pk=mapped.target_pk).first()
            if target_watchlist is None and thread.listing_id and thread.created_by_user_id:
                target_watchlist, _ = ListingWatchlistItem.objects.get_or_create(
                    user=thread.created_by_user,
                    listing=thread.listing,
                    defaults={"status": WatchlistStatus.WATCHING, "source": WatchlistSource.DIRECT},
                )
            if target_watchlist is None:
                self._audit("thread", thread.pk, None, BackfillAuditStatus.FAILED, "missing_target_watchlist")
                stats.failed += 1
                continue

            target_thread, _ = ListingMessageThread.objects.update_or_create(
                listing=target_watchlist.listing,
                created_by_user=target_watchlist.user,
            )
            # Populate listing-centric fields on legacy thread model for compatibility cutover.
            update_fields = []
            if thread.listing_id != target_watchlist.listing_id:
                thread.listing = target_watchlist.listing
                update_fields.append("listing")
            if thread.created_by_user_id != target_watchlist.user_id:
                thread.created_by_user = target_watchlist.user
                update_fields.append("created_by_user")
            if update_fields:
                thread.save(update_fields=update_fields)

            LegacyToTargetMapping.objects.update_or_create(
                entity_type="thread",
                legacy_pk=thread.pk,
                defaults={"target_pk": target_thread.pk, "mapping_version": 1},
            )
            self._audit("thread", thread.pk, target_thread.pk, BackfillAuditStatus.SUCCESS, "thread_backfilled")
            stats.success += 1

        return stats

    def _audit(self, entity_type: str, source_pk: int, target_pk: int | None, status: str, reason: str):
        BackfillAuditRecord.objects.create(
            entity_type=entity_type,
            source_pk=source_pk,
            target_pk=target_pk,
            status=status,
            reason_code=reason,
            details={},
        )
