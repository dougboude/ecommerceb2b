from datetime import datetime
from types import SimpleNamespace

from django.test import SimpleTestCase

from marketplace.forms import DiscoverForm
from marketplace.views import _sort_discover_results


class DiscoverSortingTests(SimpleTestCase):
    def test_best_match_keeps_existing_order(self):
        a = SimpleNamespace(pk=1, created_at=datetime(2026, 1, 1))
        b = SimpleNamespace(pk=2, created_at=datetime(2026, 1, 2))
        c = SimpleNamespace(pk=3, created_at=datetime(2026, 1, 3))

        results = _sort_discover_results(
            [b, a, c], DiscoverForm.SORT_BEST_MATCH, DiscoverForm.DIRECTION_FIND_SUPPLY,
        )
        self.assertEqual([r.pk for r in results], [2, 1, 3])

    def test_newest_posted_orders_descending_created_at(self):
        a = SimpleNamespace(pk=1, created_at=datetime(2026, 1, 1))
        b = SimpleNamespace(pk=2, created_at=datetime(2026, 1, 2))
        c = SimpleNamespace(pk=3, created_at=datetime(2026, 1, 3))

        results = _sort_discover_results(
            [a, c, b], DiscoverForm.SORT_NEWEST, DiscoverForm.DIRECTION_FIND_SUPPLY,
        )
        self.assertEqual([r.pk for r in results], [3, 2, 1])

    def test_ending_soon_for_buyers_uses_expires_at(self):
        a = SimpleNamespace(pk=1, created_at=datetime(2026, 1, 1), expires_at=datetime(2026, 2, 10))
        b = SimpleNamespace(pk=2, created_at=datetime(2026, 1, 2), expires_at=datetime(2026, 2, 5))
        c = SimpleNamespace(pk=3, created_at=datetime(2026, 1, 3), expires_at=None)

        results = _sort_discover_results(
            [a, c, b], DiscoverForm.SORT_ENDING_SOON, DiscoverForm.DIRECTION_FIND_SUPPLY,
        )
        self.assertEqual([r.pk for r in results], [2, 1, 3])

    def test_ending_soon_for_suppliers_uses_expires_at(self):
        a = SimpleNamespace(pk=1, created_at=datetime(2026, 1, 1), expires_at=datetime(2026, 3, 2))
        b = SimpleNamespace(pk=2, created_at=datetime(2026, 1, 2), expires_at=None)
        c = SimpleNamespace(pk=3, created_at=datetime(2026, 1, 3), expires_at=datetime(2026, 2, 20))

        results = _sort_discover_results(
            [a, b, c], DiscoverForm.SORT_ENDING_SOON, DiscoverForm.DIRECTION_FIND_DEMAND,
        )
        self.assertEqual([r.pk for r in results], [3, 1, 2])
