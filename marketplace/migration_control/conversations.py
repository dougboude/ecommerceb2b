from dataclasses import dataclass

from django.db import transaction

from marketplace.models import (
    Listing,
    MessageThread,
    WatchlistItem,
    WatchlistSource,
    WatchlistStatus,
)


@dataclass
class ThreadStartResult:
    thread: MessageThread
    created: bool
    watchlist_item: WatchlistItem


class ThreadWatchlistCoordinator:
    @transaction.atomic
    def ensure_watchlist_saved(self, *, user, listing: Listing, source=WatchlistSource.DIRECT):
        item, _ = WatchlistItem.objects.get_or_create(
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
        thread, created = MessageThread.objects.get_or_create(
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
        return ThreadStartResult(thread=thread, created=created, watchlist_item=watch_item)
