from unittest import SkipTest

raise SkipTest("Legacy migration-control pre-CP5 tests retired after CP5 cleanup")

from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from marketplace.migration_control.backfill import BackfillEngine
from marketplace.migration_control.checkpoints import CheckpointController
from marketplace.migration_control.parity import ParityValidator
from marketplace.migration_control.state import CHECKPOINT_ORDER, get_or_create_state
from marketplace.models import (
    DemandPost,
    DemandStatus,
    Listing,
    ListingMessageThread,
    ListingWatchlistItem,
    MessageThread,
    MigrationMode,
    MigrationState,
    Organization,
    Role,
    SupplyLot,
    SupplyStatus,
    User,
    WatchlistItem,
    WatchlistSource,
)


class MigrationStateTests(TestCase):
    def test_get_or_create_default_state(self):
        state = get_or_create_state()
        self.assertEqual(state.checkpoint, "CP0")
        self.assertEqual(state.mode, MigrationMode.LEGACY)

    def test_checkpoint_advance_and_rollback(self):
        controller = CheckpointController()
        from marketplace.models import ParityReport

        ParityReport.objects.create(
            stage="schema",
            scope="relationships",
            passed=True,
            total_checked=1,
            failures=0,
        )
        advance_cp2 = controller.advance_to("CP2")
        self.assertTrue(advance_cp2.ok)

        advance = controller.advance_to("CP3")
        self.assertTrue(advance.ok)

        state = MigrationState.objects.get(name="default")
        self.assertEqual(state.checkpoint_order, CHECKPOINT_ORDER["CP3"])
        self.assertTrue(state.dual_write_enabled)

        rollback = controller.rollback_to("CP2")
        self.assertTrue(rollback.ok)
        state.refresh_from_db()
        self.assertEqual(state.checkpoint, "CP2")

    def test_checkpoint_gate_blocks_without_reports(self):
        controller = CheckpointController()
        result = controller.advance_to("CP2")
        self.assertFalse(result.ok)
        self.assertIn("relationships", result.message)


class MigrationAdditiveSafetyTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            password="pass",
            role=Role.BUYER,
            country="US",
            display_name="Buyer",
        )
        self.supplier = User.objects.create_user(
            email="supplier@example.com",
            password="pass",
            role=Role.SUPPLIER,
            country="US",
            display_name="Supplier",
        )
        self.org = Organization.objects.create(
            owner=self.buyer,
            name="Buyer Org",
            type="restaurant",
            country="US",
        )

    def test_legacy_models_still_operational_after_additive_schema(self):
        post = DemandPost.objects.create(
            organization=self.org,
            created_by=self.buyer,
            item_text="Morels",
            category="food_fresh",
            frequency="one_time",
            notes="Need ASAP",
            status=DemandStatus.ACTIVE,
            location_country="US",
        )
        lot = SupplyLot.objects.create(
            created_by=self.supplier,
            item_text="Morels",
            category="food_fresh",
            available_until=timezone.now() + timedelta(days=5),
            notes="Fresh",
            status=SupplyStatus.ACTIVE,
            location_country="US",
        )
        self.assertIsNotNone(post.pk)
        self.assertIsNotNone(lot.pk)


class MigrationBackfillAndCompatibilityTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            password="pass",
            role=Role.BUYER,
            country="US",
            display_name="Buyer",
        )
        self.supplier = User.objects.create_user(
            email="supplier@example.com",
            password="pass",
            role=Role.SUPPLIER,
            country="US",
            display_name="Supplier",
        )
        self.org = Organization.objects.create(
            owner=self.buyer,
            name="Buyer Org",
            type="restaurant",
            country="US",
        )
        self.post = DemandPost.objects.create(
            organization=self.org,
            created_by=self.buyer,
            item_text="Truffles",
            category="food_fresh",
            frequency="one_time",
            notes="Weekly",
            status=DemandStatus.ACTIVE,
            location_country="US",
        )
        self.lot = SupplyLot.objects.create(
            created_by=self.supplier,
            item_text="Truffles",
            category="food_fresh",
            available_until=timezone.now() + timedelta(days=7),
            notes="in stock",
            status=SupplyStatus.ACTIVE,
            location_country="US",
        )
        self.watchlist = WatchlistItem.objects.create(
            user=self.buyer,
            supply_lot=self.lot,
            source=WatchlistSource.DIRECT,
        )
        self.thread = MessageThread.objects.create(
            watchlist_item=self.watchlist,
            buyer=self.buyer,
            supplier=self.supplier,
        )

    def test_backfill_is_idempotent_for_users_listings_threads_watchlist(self):
        engine = BackfillEngine()
        engine.backfill_users()
        engine.backfill_listings()
        engine.backfill_threads_and_watchlist()

        counts_after_first = (
            Listing.objects.count(),
            ListingWatchlistItem.objects.count(),
            ListingMessageThread.objects.count(),
        )

        engine.backfill_users()
        engine.backfill_listings()
        engine.backfill_threads_and_watchlist()

        counts_after_second = (
            Listing.objects.count(),
            ListingWatchlistItem.objects.count(),
            ListingMessageThread.objects.count(),
        )
        self.assertEqual(counts_after_first, counts_after_second)

    @override_settings(MIGRATION_DUAL_WRITE_ENABLED=True)
    def test_dual_write_signal_sync_creates_target_listing(self):
        SupplyLot.objects.create(
            created_by=self.supplier,
            item_text="Chanterelles",
            category="food_fresh",
            available_until=timezone.now() + timedelta(days=2),
            notes="fresh",
            status=SupplyStatus.ACTIVE,
            location_country="US",
        )
        self.assertGreaterEqual(Listing.objects.count(), 1)

    def test_parity_validator_reports(self):
        engine = BackfillEngine()
        engine.backfill_users()
        engine.backfill_listings()
        engine.backfill_threads_and_watchlist()

        validator = ParityValidator()
        count_result = validator.validate_counts()
        relationship_result = validator.validate_relationships()

        self.assertTrue(count_result.passed)
        self.assertTrue(relationship_result.passed)


class MigrationCommandSmokeTests(TestCase):
    def test_commands_run(self):
        from marketplace.models import ParityReport

        ParityReport.objects.create(
            stage="schema",
            scope="relationships",
            passed=True,
            total_checked=1,
            failures=0,
        )
        call_command("migration_set_state", "--checkpoint", "CP1")
        call_command("migration_checkpoint", "advance", "CP2")
        call_command("migration_validate", "--scope", "relationships")

    def test_cutover_command_progresses_to_cp4(self):
        call_command("migration_cutover", "--to", "CP4")
        state = MigrationState.objects.get(name="default")
        self.assertEqual(state.checkpoint, "CP4")

    def test_cutover_then_rollback_drill(self):
        call_command("migration_cutover", "--to", "CP4")
        call_command("migration_checkpoint", "rollback", "CP3")
        state = MigrationState.objects.get(name="default")
        self.assertEqual(state.checkpoint, "CP3")


class MigrationNonGoalEnforcementTests(TestCase):
    def test_no_deferred_marketplace_models_introduced(self):
        import marketplace.models as model_module

        banned_model_names = {"Payment", "Escrow", "Auction", "Bid", "LogisticsShipment"}
        existing = {name for name in dir(model_module) if name in banned_model_names}
        self.assertEqual(existing, set())
