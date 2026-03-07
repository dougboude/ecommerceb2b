from dataclasses import dataclass

from marketplace.models import Listing, MessageThread, WatchlistItem


@dataclass
class WriteResult:
    ok: bool
    primary_pk: int | None = None
    shadow_pk: int | None = None
    error: str | None = None


class CompatibilityRepository:
    """Retired compatibility layer post-CP5; retained for import stability."""

    def sync_listing_shadow(self, legacy_listing):
        return WriteResult(ok=True, primary_pk=getattr(legacy_listing, "pk", None))

    def sync_watchlist_shadow(self, watchlist_item: WatchlistItem) -> WriteResult:
        return WriteResult(ok=True, primary_pk=watchlist_item.pk)

    def sync_thread_shadow(self, thread: MessageThread) -> WriteResult:
        return WriteResult(ok=True, primary_pk=thread.pk)

    def read_listing(self, *, listing_type: str, pk: int):
        return Listing.objects.filter(pk=pk).first()

    def read_target_watchlist(self, user_id: int):
        return WatchlistItem.objects.filter(user_id=user_id)

    def read_target_threads(self, user_id: int):
        return MessageThread.objects.filter(created_by_user_id=user_id)
