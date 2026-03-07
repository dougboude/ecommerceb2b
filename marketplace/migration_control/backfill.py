from dataclasses import dataclass


@dataclass
class BackfillStats:
    processed: int = 0
    success: int = 0
    failed: int = 0


class BackfillEngine:
    """Retired in CP5 cleanup. Kept only for command/interface compatibility."""

    def backfill_users(self) -> BackfillStats:
        return BackfillStats()

    def backfill_listings(self) -> BackfillStats:
        return BackfillStats()

    def backfill_threads_and_watchlist(self) -> BackfillStats:
        return BackfillStats()
