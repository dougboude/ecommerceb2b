from dataclasses import dataclass

from django.db import transaction

from marketplace.migration_control.backfill import BackfillEngine
from marketplace.migration_control.listings import ListingCompatibilityService
from marketplace.models import (
    Listing,
    ListingMessageThread,
    ListingType,
    ListingWatchlistItem,
    MessageThread,
    WatchlistItem,
    WatchlistSource,
    WatchlistStatus,
)


@dataclass
class ThreadStartResult:
    thread: MessageThread
    created: bool
    watchlist_item: ListingWatchlistItem


class ThreadWatchlistCoordinator:
    def __init__(self):
        self.listing_service = ListingCompatibilityService()
        self.backfill_engine = BackfillEngine()

    def _target_listing_from_legacy(self, *, supply_lot=None, demand_post=None):
        if supply_lot is not None:
            listing = self.listing_service.target_listing_for_legacy(supply_lot)
            if listing is None:
                self.backfill_engine.backfill_listings()
                listing = self.listing_service.target_listing_for_legacy(supply_lot)
            return listing

        if demand_post is not None:
            listing = self.listing_service.target_listing_for_legacy(demand_post)
            if listing is None:
                self.backfill_engine.backfill_listings()
                listing = self.listing_service.target_listing_for_legacy(demand_post)
            return listing

        return None

    @transaction.atomic
    def ensure_watchlist_saved(self, *, user, listing: Listing, source=WatchlistSource.DIRECT):
        item, _ = ListingWatchlistItem.objects.get_or_create(
            user=user,
            listing=listing,
            defaults={
                "source": source,
                "status": WatchlistStatus.WATCHING,
            },
        )
        return item

    @transaction.atomic
    def ensure_thread_uniqueness(self, *, listing: Listing, initiator):
        owner = listing.created_by_user

        defaults = {
            "buyer": initiator if listing.type == ListingType.SUPPLY else owner,
            "supplier": owner if listing.type == ListingType.SUPPLY else initiator,
        }
        thread, created = MessageThread.objects.get_or_create(
            listing=listing,
            created_by_user=initiator,
            defaults=defaults,
        )

        # Shadow target-thread record for migration parity.
        ListingMessageThread.objects.get_or_create(
            listing=listing,
            created_by_user=initiator,
        )

        return thread, created

    @transaction.atomic
    def start_thread_with_autosave(
        self,
        *,
        user,
        listing: Listing,
        source=WatchlistSource.DIRECT,
        legacy_watchlist_item: WatchlistItem | None = None,
    ) -> ThreadStartResult:
        watch_item = self.ensure_watchlist_saved(user=user, listing=listing, source=source)
        thread, created = self.ensure_thread_uniqueness(listing=listing, initiator=user)

        # Keep legacy linkage best-effort during compatibility window.
        if legacy_watchlist_item is not None and thread.watchlist_item_id is None:
            thread.watchlist_item = legacy_watchlist_item
            thread.save(update_fields=["watchlist_item"])

        return ThreadStartResult(thread=thread, created=created, watchlist_item=watch_item)

    @transaction.atomic
    def start_from_legacy_listing(self, *, user, listing_type: str, listing_pk: int, source=WatchlistSource.DIRECT):
        if listing_type == "supply_lot":
            from marketplace.models import SupplyLot

            lot = SupplyLot.objects.get(pk=listing_pk)
            listing = self._target_listing_from_legacy(supply_lot=lot)
            if listing is None:
                raise ValueError("Unable to resolve target listing from supply lot")

            legacy_item, _ = WatchlistItem.objects.get_or_create(
                user=user,
                supply_lot=lot,
                defaults={"source": source, "status": WatchlistStatus.WATCHING},
            )
            return self.start_thread_with_autosave(
                user=user,
                listing=listing,
                source=source,
                legacy_watchlist_item=legacy_item,
            )

        if listing_type == "demand_post":
            from marketplace.models import DemandPost

            post = DemandPost.objects.get(pk=listing_pk)
            listing = self._target_listing_from_legacy(demand_post=post)
            if listing is None:
                raise ValueError("Unable to resolve target listing from demand post")

            legacy_item, _ = WatchlistItem.objects.get_or_create(
                user=user,
                demand_post=post,
                defaults={"source": source, "status": WatchlistStatus.WATCHING},
            )
            return self.start_thread_with_autosave(
                user=user,
                listing=listing,
                source=source,
                legacy_watchlist_item=legacy_item,
            )

        raise ValueError(f"Unsupported listing_type: {listing_type}")
