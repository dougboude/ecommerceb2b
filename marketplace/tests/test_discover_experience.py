from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings, tag
from django.urls import reverse
from django.utils import timezone

from marketplace.forms import DiscoverForm
from marketplace.models import (
    Listing,
    ListingStatus,
    ListingType,
    ListingShippingScope,
    MessageThread,
    User,
    WatchlistItem,
)


_STATIC_TEST_SETTINGS = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def _make_user(email):
    return User.objects.create_user(
        email=email,
        password="testpass123",
        country="US",
        display_name="Discover User",
    )


def _make_supply(owner, title):
    return Listing.objects.create(
        type=ListingType.SUPPLY,
        created_by_user=owner,
        title=title,
        status=ListingStatus.ACTIVE,
        location_country="US",
        shipping_scope=ListingShippingScope.DOMESTIC,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=10),
    )


def _make_demand(owner, title):
    return Listing.objects.create(
        type=ListingType.DEMAND,
        created_by_user=owner,
        title=title,
        status=ListingStatus.ACTIVE,
        location_country="US",
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=10),
    )


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
@tag("discover_experience")
class DiscoverExperienceTests(TestCase):
    def setUp(self):
        self.search_user = _make_user("searcher@discover.test")
        self.owner = _make_user("owner@discover.test")
        self.client.force_login(self.search_user)

    def _discover_post(self, **overrides):
        payload = {
            "query": "alpha",
            "direction": DiscoverForm.DIRECTION_FIND_SUPPLY,
            "search_mode": DiscoverForm.SEARCH_MODE_KEYWORD,
            "sort_by": DiscoverForm.SORT_BEST_MATCH,
            "category": "",
            "location_country": "",
            "radius": "",
            "exclude_watched": "",
        }
        payload.update(overrides)
        return self.client.post(reverse("marketplace:discover"), payload)

    def test_direction_isolation_and_labeling(self):
        supply = _make_supply(self.owner, "alpha supply")
        demand = _make_demand(self.owner, "alpha demand")

        supply_resp = self._discover_post(direction=DiscoverForm.DIRECTION_FIND_SUPPLY)
        self.assertEqual(supply_resp.status_code, 200)
        self.assertContains(supply_resp, "Showing matches for Find Supply.")
        self.assertEqual(len(supply_resp.context["results"]), 1)
        self.assertEqual(supply_resp.context["results"][0].discover_listing_type, "supply_lot")
        self.assertEqual(supply_resp.context["results"][0].pk, supply.pk)

        demand_resp = self._discover_post(direction=DiscoverForm.DIRECTION_FIND_DEMAND)
        self.assertEqual(demand_resp.status_code, 200)
        self.assertContains(demand_resp, "Showing matches for Find Demand.")
        self.assertEqual(len(demand_resp.context["results"]), 1)
        self.assertEqual(demand_resp.context["results"][0].discover_listing_type, "demand_post")
        self.assertEqual(demand_resp.context["results"][0].pk, demand.pk)

    def test_save_unsave_preserves_discover_context(self):
        listing = _make_supply(self.owner, "alpha cardamom")
        self._discover_post(direction=DiscoverForm.DIRECTION_FIND_SUPPLY)

        save_resp = self.client.post(
            reverse("marketplace:discover_save"),
            {"listing_type": "supply_lot", "listing_pk": listing.pk},
            follow=True,
        )
        self.assertEqual(save_resp.status_code, 200)
        self.assertContains(save_resp, "Showing matches for Find Supply.")
        self.assertContains(save_resp, "Unsave")
        self.assertTrue(
            WatchlistItem.objects.filter(user=self.search_user, listing=listing).exists()
        )

        unsave_resp = self.client.post(
            reverse("marketplace:discover_unsave"),
            {"listing_type": "supply_lot", "listing_pk": listing.pk},
            follow=True,
        )
        self.assertEqual(unsave_resp.status_code, 200)
        self.assertContains(unsave_resp, "Showing matches for Find Supply.")
        self.assertContains(unsave_resp, "Save")
        self.assertFalse(
            WatchlistItem.objects.filter(user=self.search_user, listing=listing).exists()
        )

    def test_discover_message_starts_conversation(self):
        listing = _make_supply(self.owner, "alpha turmeric")

        response = self.client.post(
            reverse("marketplace:discover_message"),
            {"listing_type": "supply_lot", "listing_pk": listing.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/threads/", response.url)
        self.assertTrue(
            MessageThread.objects.filter(
                listing=listing,
                created_by_user=self.search_user,
            ).exists()
        )

    def test_clear_resets_discover_state(self):
        session = self.client.session
        session["discover_last_query"] = "alpha"
        session["discover_last_direction"] = DiscoverForm.DIRECTION_FIND_DEMAND
        session["discover_last_sort_by"] = DiscoverForm.SORT_NEWEST
        session.save()

        response = self.client.get(reverse("marketplace:discover_clear"))
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertNotIn("discover_last_query", session)
        self.assertNotIn("discover_last_direction", session)
        self.assertNotIn("discover_last_sort_by", session)

    @patch("marketplace.views._run_discover_search", return_value=[])
    def test_short_query_hint_and_empty_state_recovery_action(self, _mock_search):
        response = self.client.post(
            reverse("marketplace:discover"),
            {
                "query": "rice",
                "direction": DiscoverForm.DIRECTION_FIND_SUPPLY,
                "search_mode": DiscoverForm.SEARCH_MODE_SIMILAR,
                "sort_by": DiscoverForm.SORT_BEST_MATCH,
                "category": "",
                "location_country": "",
                "radius": "",
                "exclude_watched": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No results found for Find Supply.")
        self.assertContains(response, "Tip: try a more descriptive search (3+ words)")
        self.assertContains(response, "Start a new search")
        self.assertContains(response, reverse("marketplace:discover_clear"))
