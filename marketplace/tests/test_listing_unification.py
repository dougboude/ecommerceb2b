from unittest import SkipTest

raise SkipTest("Legacy listing unification tests retired after CP5 cleanup")

from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from marketplace.migration_control.backfill import BackfillEngine
from marketplace.migration_control.checkpoints import CheckpointController
from marketplace.migration_control.listings import ListingCompatibilityService
from marketplace.migration_control.parity import ParityValidator
from marketplace.models import (
    DemandPost,
    DemandStatus,
    Listing,
    ListingStatus,
    ListingType,
    Organization,
    ParityReport,
    Role,
    SupplyLot,
    SupplyStatus,
    User,
)


class ListingContractValidationTests(TestCase):
    def test_supply_listing_rejects_demand_only_fields(self):
        listing = Listing(
            type=ListingType.SUPPLY,
            created_by_user=User.objects.create_user(
                email="s@example.com",
                password="pass",
                role=Role.SUPPLIER,
                country="US",
                display_name="S",
            ),
            title="Supply",
            description="Desc",
            category="food_fresh",
            status=ListingStatus.ACTIVE,
            location_country="US",
            radius_km=25,
            frequency="one_time",
            created_at=timezone.now(),
        )
        with self.assertRaises(Exception):
            listing.full_clean()

    def test_demand_listing_rejects_supply_only_fields(self):
        listing = Listing(
            type=ListingType.DEMAND,
            created_by_user=User.objects.create_user(
                email="b@example.com",
                password="pass",
                role=Role.BUYER,
                country="US",
                display_name="B",
            ),
            title="Demand",
            description="Desc",
            category="food_fresh",
            status=ListingStatus.ACTIVE,
            location_country="US",
            shipping_scope="domestic",
            price_unit="kg",
            created_at=timezone.now(),
        )
        with self.assertRaises(Exception):
            listing.full_clean()


class ListingBackfillParityTests(TestCase):
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
        self.org = Organization.objects.create(owner=self.buyer, name="Org", type="x", country="US")

        DemandPost.objects.create(
            organization=self.org,
            created_by=self.buyer,
            item_text="Need mushrooms",
            category="food_fresh",
            frequency="one_time",
            notes="desc",
            status=DemandStatus.ACTIVE,
            location_country="US",
        )
        SupplyLot.objects.create(
            created_by=self.supplier,
            item_text="Wild mushrooms",
            category="food_fresh",
            available_until=timezone.now() + timedelta(days=2),
            notes="desc",
            status=SupplyStatus.ACTIVE,
            location_country="US",
        )

    def test_backfill_and_listing_contract_parity(self):
        engine = BackfillEngine()
        engine.backfill_listings()

        validator = ParityValidator()
        result = validator.validate_listing_contract()
        self.assertTrue(result.passed)


class ListingCompatibilityServiceTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email="buyer2@example.com",
            password="pass",
            role=Role.BUYER,
            country="US",
            display_name="Buyer",
        )
        self.org = Organization.objects.create(owner=self.buyer, name="Org", type="x", country="US")
        self.post = DemandPost.objects.create(
            organization=self.org,
            created_by=self.buyer,
            item_text="Herbs",
            category="botanical",
            frequency="one_time",
            notes="fresh herbs",
            status=DemandStatus.ACTIVE,
            location_country="US",
        )
        BackfillEngine().backfill_listings()

    @override_settings(MIGRATION_READ_CANONICAL="target", MIGRATION_DUAL_READ_ENABLED=True)
    def test_discover_queryset_uses_target_listing(self):
        service = ListingCompatibilityService()
        results = service.discover_queryset(
            listing_type="demand",
            query="Herbs",
            category="botanical",
            country="US",
        )
        self.assertIsNotNone(results)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], Listing)


class ListingCutoverGateTests(TestCase):
    def test_checkpoint_cp4_requires_listing_report(self):
        ParityReport.objects.create(stage="schema", scope="counts", passed=True, total_checked=1, failures=0)
        ParityReport.objects.create(stage="schema", scope="relationships", passed=True, total_checked=1, failures=0)
        ParityReport.objects.create(stage="schema", scope="identity", passed=True, total_checked=1, failures=0)

        controller = CheckpointController()
        controller.advance_to("CP2")
        controller.advance_to("CP3")
        result = controller.advance_to("CP4")
        self.assertFalse(result.ok)
        self.assertIn("listing", result.message)

    def test_migration_validate_listing_scope(self):
        call_command("migration_validate", "--scope", "listing")

    def test_migration_cutover_generates_listing_report(self):
        call_command("migration_cutover", "--to", "CP4")
        self.assertTrue(ParityReport.objects.filter(scope="listing").exists())
