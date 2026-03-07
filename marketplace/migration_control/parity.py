from dataclasses import dataclass

from django.db.models import Q
from django.db.models import Count

from marketplace.models import (
    DemandPost,
    LegacyToTargetMapping,
    Listing,
    ListingStatus,
    ListingType,
    ListingMessageThread,
    ListingWatchlistItem,
    ListingWatchlistItem,
    Message,
    MessageThread,
    ParityReport,
    SupplyLot,
    User,
    WatchlistItem,
)
from marketplace.migration_control.identity import IdentityComplianceScanner
from marketplace.migration_control.permissions import RoleAuthComplianceScanner
from marketplace.migration_control.discover import DiscoverComplianceScanner


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

    def validate_listing_contract(self) -> ValidationResult:
        failures = 0
        notes = []

        invalid_supply = Listing.objects.filter(
            type=ListingType.SUPPLY,
        ).filter(
            Q(radius_km__isnull=False)
            | ~Q(frequency="")
            | Q(status=ListingStatus.FULFILLED)
        ).count()
        if invalid_supply:
            failures += 1
            notes.append(f"invalid_supply_rows={invalid_supply}")

        invalid_demand = Listing.objects.filter(
            type=ListingType.DEMAND,
        ).filter(
            ~Q(shipping_scope="")
            | ~Q(price_unit="")
            | Q(status=ListingStatus.WITHDRAWN)
        ).count()
        if invalid_demand:
            failures += 1
            notes.append(f"invalid_demand_rows={invalid_demand}")

        missing_mappings = Listing.objects.filter(
            legacy_source_type__in=["demand_post", "supply_lot"],
            legacy_source_pk__isnull=False,
        ).exclude(
            pk__in=LegacyToTargetMapping.objects.filter(entity_type="listing").values_list("target_pk", flat=True)
        ).count()
        if missing_mappings:
            failures += 1
            notes.append(f"missing_listing_mappings={missing_mappings}")

        return ValidationResult(
            passed=failures == 0,
            total_checked=3,
            failures=failures,
            summary="; ".join(notes),
        )

    def validate_messaging_contract(self) -> ValidationResult:
        failures = 0
        notes = []

        missing_listing = MessageThread.objects.filter(listing__isnull=True).count()
        if missing_listing:
            failures += 1
            notes.append(f"threads_missing_listing={missing_listing}")

        missing_initiator = MessageThread.objects.filter(created_by_user__isnull=True).count()
        if missing_initiator:
            failures += 1
            notes.append(f"threads_missing_initiator={missing_initiator}")

        source_pairs = set(
            MessageThread.objects.filter(
                listing__isnull=False,
                created_by_user__isnull=False,
            ).values_list("listing_id", "created_by_user_id")
        )
        target_pairs = set(
            ListingMessageThread.objects.values_list("listing_id", "created_by_user_id")
        )
        mismatched_target_threads = len(source_pairs.symmetric_difference(target_pairs))
        if mismatched_target_threads:
            failures += 1
            notes.append(f"messaging_thread_mismatch={mismatched_target_threads}")

        orphan_target_watchlists = ListingWatchlistItem.objects.filter(listing__isnull=True).count()
        if orphan_target_watchlists:
            failures += 1
            notes.append(f"orphan_target_watchlists={orphan_target_watchlists}")

        orphan_target_threads = ListingMessageThread.objects.filter(listing__isnull=True).count()
        if orphan_target_threads:
            failures += 1
            notes.append(f"orphan_target_threads={orphan_target_threads}")

        return ValidationResult(
            passed=failures == 0,
            total_checked=5,
            failures=failures,
            summary="; ".join(notes),
        )

    def validate_identity(self) -> ValidationResult:
        scanner = IdentityComplianceScanner()
        passed, violations = scanner.scan()
        failures = len(violations)
        return ValidationResult(
            passed=passed,
            total_checked=max(failures, 1),
            failures=failures,
            summary="; ".join(violations),
        )

    def validate_permission_policy(self) -> ValidationResult:
        """
        Validate that no role-based authorization remains in launch-critical views.
        Uses RoleAuthComplianceScanner to detect residual role-check patterns.
        """
        scanner = RoleAuthComplianceScanner()
        passed, violations = scanner.scan()
        failures = len(violations)
        return ValidationResult(
            passed=passed,
            total_checked=max(failures, 1),
            failures=failures,
            summary="; ".join(violations),
        )

    def validate_discover_contract(self) -> ValidationResult:
        scanner = DiscoverComplianceScanner()
        passed, violations = scanner.scan()
        failures = len(violations)
        return ValidationResult(
            passed=passed,
            total_checked=max(failures, 1),
            failures=failures,
            summary="; ".join(violations),
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
