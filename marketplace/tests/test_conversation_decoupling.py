from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from marketplace.migration_control.backfill import BackfillEngine
from marketplace.migration_control.conversations import ThreadWatchlistCoordinator
from marketplace.migration_control.parity import ParityValidator
from marketplace.models import (
    DemandPost,
    DemandStatus,
    ListingMessageThread,
    ListingWatchlistItem,
    MessageThread,
    Organization,
    Role,
    SupplyLot,
    SupplyStatus,
    User,
    WatchlistItem,
    WatchlistSource,
)


class ConversationCoordinatorTests(TestCase):
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
        self.org = Organization.objects.create(owner=self.buyer, name="Org", type="r", country="US")
        self.lot = SupplyLot.objects.create(
            created_by=self.supplier,
            item_text="Morels",
            category="food_fresh",
            available_until=timezone.now() + timedelta(days=3),
            notes="fresh",
            status=SupplyStatus.ACTIVE,
            location_country="US",
        )
        self.post = DemandPost.objects.create(
            organization=self.org,
            created_by=self.buyer,
            item_text="Need morels",
            category="food_fresh",
            frequency="one_time",
            notes="urgent",
            status=DemandStatus.ACTIVE,
            location_country="US",
        )
        BackfillEngine().backfill_listings()
        self.coordinator = ThreadWatchlistCoordinator()

    def test_thread_start_autosaves_and_enforces_uniqueness(self):
        first = self.coordinator.start_from_legacy_listing(
            user=self.buyer,
            listing_type="supply_lot",
            listing_pk=self.lot.pk,
            source=WatchlistSource.DIRECT,
        )
        second = self.coordinator.start_from_legacy_listing(
            user=self.buyer,
            listing_type="supply_lot",
            listing_pk=self.lot.pk,
            source=WatchlistSource.DIRECT,
        )

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.thread.pk, second.thread.pk)
        self.assertEqual(ListingWatchlistItem.objects.count(), 1)
        self.assertEqual(ListingMessageThread.objects.count(), 1)

    def test_thread_and_watchlist_decoupled(self):
        result = self.coordinator.start_from_legacy_listing(
            user=self.buyer,
            listing_type="supply_lot",
            listing_pk=self.lot.pk,
            source=WatchlistSource.DIRECT,
        )
        thread_id = result.thread.pk
        legacy_item = WatchlistItem.objects.get(user=self.buyer, supply_lot=self.lot)
        legacy_item.delete()

        thread = MessageThread.objects.get(pk=thread_id)
        self.assertIsNone(thread.watchlist_item)
        self.assertIsNotNone(thread.listing)
        self.assertIsNotNone(thread.created_by_user)


class MessagingBackfillTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email="buyer2@example.com",
            password="pass",
            role=Role.BUYER,
            country="US",
            display_name="Buyer2",
        )
        self.supplier = User.objects.create_user(
            email="supplier2@example.com",
            password="pass",
            role=Role.SUPPLIER,
            country="US",
            display_name="Supplier2",
        )
        self.org = Organization.objects.create(owner=self.buyer, name="Org2", type="r", country="US")
        self.lot = SupplyLot.objects.create(
            created_by=self.supplier,
            item_text="Chanterelles",
            category="food_fresh",
            available_until=timezone.now() + timedelta(days=4),
            notes="fresh",
            status=SupplyStatus.ACTIVE,
            location_country="US",
        )
        self.watch = WatchlistItem.objects.create(
            user=self.buyer,
            supply_lot=self.lot,
            source=WatchlistSource.DIRECT,
        )
        self.thread = MessageThread.objects.create(
            watchlist_item=self.watch,
            buyer=self.buyer,
            supplier=self.supplier,
        )

    def test_backfill_populates_listing_and_initiator_on_legacy_threads(self):
        engine = BackfillEngine()
        engine.backfill_listings()
        engine.backfill_threads_and_watchlist()

        thread = MessageThread.objects.get(pk=self.thread.pk)
        self.assertIsNotNone(thread.listing)
        self.assertEqual(thread.created_by_user_id, self.buyer.pk)

    def test_messaging_parity_validator(self):
        engine = BackfillEngine()
        engine.backfill_listings()
        engine.backfill_threads_and_watchlist()

        result = ParityValidator().validate_messaging_contract()
        self.assertTrue(result.passed)
