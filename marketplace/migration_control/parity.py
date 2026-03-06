from dataclasses import dataclass

from django.db.models import Count

from marketplace.models import (
    DemandPost,
    LegacyToTargetMapping,
    Listing,
    ListingMessageThread,
    ListingWatchlistItem,
    Message,
    MessageThread,
    ParityReport,
    SupplyLot,
    User,
    WatchlistItem,
)


@dataclass
class ValidationResult:
    passed: bool
    total_checked: int
    failures: int
    summary: str


class ParityValidator:
    def validate_counts(self) -> ValidationResult:
        checks = {
            "users": (User.objects.count(), User.objects.count()),
            "listings": (DemandPost.objects.count() + SupplyLot.objects.count(), Listing.objects.count()),
            "watchlists": (WatchlistItem.objects.count(), ListingWatchlistItem.objects.count()),
            "threads": (MessageThread.objects.count(), ListingMessageThread.objects.count()),
            "messages": (Message.objects.count(), Message.objects.count()),
        }
        failures = 0
        diffs = []
        for key, (legacy_count, target_count) in checks.items():
            if legacy_count != target_count:
                failures += 1
                diffs.append(f"{key}: legacy={legacy_count} target={target_count}")

        total = len(checks)
        return ValidationResult(
            passed=failures == 0,
            total_checked=total,
            failures=failures,
            summary="; ".join(diffs),
        )

    def validate_relationships(self) -> ValidationResult:
        failures = 0
        notes = []

        dup_mappings = (
            LegacyToTargetMapping.objects.values("entity_type", "legacy_pk")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
            .count()
        )
        if dup_mappings:
            failures += 1
            notes.append(f"duplicate mappings={dup_mappings}")

        orphan_target_watchlist = ListingWatchlistItem.objects.filter(listing__isnull=True).count()
        if orphan_target_watchlist:
            failures += 1
            notes.append(f"orphan target watchlist rows={orphan_target_watchlist}")

        return ValidationResult(
            passed=failures == 0,
            total_checked=2,
            failures=failures,
            summary="; ".join(notes),
        )

    def create_report(self, stage: str, scope: str, result: ValidationResult) -> ParityReport:
        return ParityReport.objects.create(
            stage=stage,
            scope=scope,
            passed=result.passed,
            total_checked=result.total_checked,
            failures=result.failures,
            failure_summary=result.summary,
        )
