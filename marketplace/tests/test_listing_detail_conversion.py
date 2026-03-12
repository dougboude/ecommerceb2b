from datetime import timedelta

from django.test import TestCase, override_settings, tag
from django.urls import reverse
from django.utils import timezone

from marketplace.models import (
    Listing,
    ListingShippingScope,
    ListingStatus,
    ListingType,
    MessageThread,
    User,
    WatchlistItem,
    WatchlistSource,
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
        display_name="Detail User",
    )


def _make_supply(owner, title="Supply detail", status=ListingStatus.ACTIVE):
    return Listing.objects.create(
        type=ListingType.SUPPLY,
        created_by_user=owner,
        title=title,
        status=status,
        location_country="US",
        shipping_scope=ListingShippingScope.DOMESTIC,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=15),
    )


def _make_demand(owner, title="Demand detail", status=ListingStatus.ACTIVE):
    return Listing.objects.create(
        type=ListingType.DEMAND,
        created_by_user=owner,
        title=title,
        status=status,
        location_country="US",
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=15),
    )


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
@tag("listing_detail_conversion")
class ListingDetailConversionTests(TestCase):
    def setUp(self):
        self.owner = _make_user("owner@detail.test")
        self.viewer = _make_user("viewer@detail.test")
        self.client.force_login(self.viewer)

    def test_non_owner_active_supply_shows_message_and_save(self):
        lot = _make_supply(self.owner, title="Active lot")
        response = self.client.get(reverse("marketplace:supply_lot_detail", kwargs={"pk": lot.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Take action")
        self.assertContains(response, "Message")
        self.assertContains(response, "Save")

    def test_non_owner_active_demand_shows_message_and_save(self):
        post = _make_demand(self.owner, title="Active post")
        response = self.client.get(reverse("marketplace:demand_post_detail", kwargs={"pk": post.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Take action")
        self.assertContains(response, "Message")
        self.assertContains(response, "Save")

    def test_owner_does_not_render_non_owner_conversion_block(self):
        lot = _make_supply(self.owner, title="Owner lot")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("marketplace:supply_lot_detail", kwargs={"pk": lot.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Take action")

    def test_save_and_unsave_from_supply_detail_preserves_listing_context(self):
        lot = _make_supply(self.owner, title="Save flow lot")
        detail_url = reverse("marketplace:supply_lot_detail", kwargs={"pk": lot.pk})

        save_resp = self.client.post(
            reverse("marketplace:discover_save"),
            {
                "listing_type": "supply_lot",
                "listing_pk": lot.pk,
                "next": detail_url,
            },
            follow=True,
        )
        self.assertEqual(save_resp.status_code, 200)
        self.assertContains(save_resp, "Saved to watchlist.")
        self.assertContains(save_resp, "Unsave")
        self.assertTrue(
            WatchlistItem.objects.filter(user=self.viewer, listing=lot).exists()
        )

        unsave_resp = self.client.post(
            reverse("marketplace:discover_unsave"),
            {
                "listing_type": "supply_lot",
                "listing_pk": lot.pk,
                "next": detail_url,
            },
            follow=True,
        )
        self.assertEqual(unsave_resp.status_code, 200)
        self.assertContains(unsave_resp, "Removed from watchlist.")
        self.assertContains(unsave_resp, "Save")
        self.assertFalse(
            WatchlistItem.objects.filter(user=self.viewer, listing=lot).exists()
        )

    def test_message_from_detail_starts_thread(self):
        lot = _make_supply(self.owner, title="Thread lot")
        response = self.client.post(
            reverse("marketplace:discover_message"),
            {"listing_type": "supply_lot", "listing_pk": lot.pk},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Back to messages")
        self.assertTrue(
            MessageThread.objects.filter(
                listing=lot,
                created_by_user=self.viewer,
            ).exists()
        )

    def test_inactive_listing_explains_why_message_not_available(self):
        lot = _make_supply(self.owner, title="Withdrawn lot", status=ListingStatus.WITHDRAWN)
        WatchlistItem.objects.create(
            user=self.viewer,
            listing=lot,
            source=WatchlistSource.DIRECT,
        )
        response = self.client.get(reverse("marketplace:supply_lot_detail", kwargs={"pk": lot.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Messaging is unavailable because this listing is not active.",
        )
        self.assertNotContains(response, ">Message<")
        self.assertContains(response, "Unsave")
