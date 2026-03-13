from datetime import timedelta

from django.test import TestCase, override_settings, tag
from django.urls import reverse
from django.utils import timezone

from marketplace.forms import DiscoverForm
from marketplace.models import (
    Listing,
    ListingStatus,
    ListingType,
    ListingShippingScope,
    WatchlistItem,
    WatchlistSource,
    WatchlistStatus,
    User,
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
        display_name="Test User",
    )


def _make_supply_listing(owner, title="Supply listing"):
    return Listing.objects.create(
        type=ListingType.SUPPLY,
        created_by_user=owner,
        title=title,
        description="",
        status=ListingStatus.ACTIVE,
        location_country="US",
        shipping_scope=ListingShippingScope.DOMESTIC,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=10),
    )


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
@tag("feedback_recovery")
class FeedbackRecoveryTests(TestCase):
    def setUp(self):
        self.user = _make_user("feedback@example.com")
        self.client.force_login(self.user)

    def test_discover_clear_shows_feedback_message(self):
        session = self.client.session
        session["discover_last_query"] = "beans"
        session.save()

        response = self.client.get(reverse("marketplace:discover_clear"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search cleared. Try a new query.")

    def test_watchlist_archive_shows_feedback_message(self):
        listing = _make_supply_listing(self.user, title="Archive me")
        item = WatchlistItem.objects.create(
            user=self.user,
            listing=listing,
            source=WatchlistSource.DIRECT,
            status=WatchlistStatus.WATCHING,
        )
        response = self.client.post(
            reverse("marketplace:watchlist_archive", kwargs={"pk": item.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Watchlist item archived.")

    def test_watchlist_delete_shows_feedback_message(self):
        listing = _make_supply_listing(self.user, title="Delete me")
        item = WatchlistItem.objects.create(
            user=self.user,
            listing=listing,
            source=WatchlistSource.DIRECT,
            status=WatchlistStatus.WATCHING,
        )
        response = self.client.post(
            reverse("marketplace:watchlist_delete", kwargs={"pk": item.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Removed from watchlist.")

    def test_suggestion_dismiss_shows_recovery_feedback_message(self):
        other = _make_user("other@example.com")
        listing = _make_supply_listing(other, title="Dismiss me")
        response = self.client.post(
            reverse("marketplace:suggestion_dismiss"),
            {
                "listing_type": "supply_lot",
                "listing_pk": listing.pk,
                "next": reverse("marketplace:dashboard"),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Suggestion dismissed. You can find more matches in Discover.",
        )

    def test_discover_no_results_empty_state_has_primary_cta(self):
        response = self.client.post(
            reverse("marketplace:discover"),
            {
                "query": "no-matches-expected",
                "direction": DiscoverForm.DIRECTION_FIND_SUPPLY,
                "search_mode": DiscoverForm.SEARCH_MODE_KEYWORD,
                "sort_by": DiscoverForm.SORT_BEST_MATCH,
                "category": "",
                "location_country": "",
                "radius": "",
                "exclude_watched": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No results found for Find Supply.")
        self.assertContains(response, "Start a new search")
        self.assertContains(response, reverse("marketplace:discover_clear"))

    def test_profile_does_not_show_listing_sections(self):
        response = self.client.get(reverse("marketplace:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Create supply listing")
        self.assertNotContains(response, "Create demand listing")

    def test_watchlist_remove_uses_custom_confirmation_modal(self):
        listing = _make_supply_listing(self.user, title="Prompt me")
        item = WatchlistItem.objects.create(
            user=self.user,
            listing=listing,
            source=WatchlistSource.DIRECT,
            status=WatchlistStatus.WATCHING,
        )
        response = self.client.get(reverse("marketplace:watchlist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'id="watchlist-remove-modal"',
        )
        self.assertContains(
            response,
            reverse("marketplace:watchlist_delete", kwargs={"pk": item.pk}),
        )
        self.assertContains(response, "watchlist-remove-form")
