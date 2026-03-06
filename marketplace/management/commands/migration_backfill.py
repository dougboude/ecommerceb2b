from django.core.management.base import BaseCommand

from marketplace.migration_control.backfill import BackfillEngine


class Command(BaseCommand):
    help = "Run deterministic migration backfill steps"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scope",
            choices=["users", "listings", "threads-watchlist", "all"],
            default="all",
        )

    def handle(self, *args, **options):
        scope = options["scope"]
        engine = BackfillEngine()

        if scope in {"users", "all"}:
            stats = engine.backfill_users()
            self.stdout.write(f"users: processed={stats.processed} success={stats.success} failed={stats.failed}")

        if scope in {"listings", "all"}:
            stats = engine.backfill_listings()
            self.stdout.write(f"listings: processed={stats.processed} success={stats.success} failed={stats.failed}")

        if scope in {"threads-watchlist", "all"}:
            stats = engine.backfill_threads_and_watchlist()
            self.stdout.write(
                f"threads-watchlist: processed={stats.processed} success={stats.success} failed={stats.failed}"
            )
