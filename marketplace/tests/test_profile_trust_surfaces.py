"""
Tests for Feature 10: Profile and Trust Surfaces.

Test plan:

Profile surface clarity (Req 1):
  F10-1  profile page renders identity summary (display name + email shown)
  F10-2  profile page renders supply and demand listing sections
  F10-3  profile page shows Edit profile button
  F10-4  profile page shows Back to dashboard link
  F10-5  profile page shows Django success messages when present
  F10-6  profile listings include status badge

Profile edit continuity (Req 4):
  F10-7  profile_edit page renders Save changes button (btn-primary)
  F10-8  profile_edit page renders Cancel link back to profile
  F10-9  successful profile_edit redirects to profile page
  F10-10 profile_edit shows updated data after save

Avatar and identity fallback (Req 2):
  F10-11 user with no avatar has a non-empty profile_image_url (no broken state)
  F10-12 profile page avatar img has correct src (default or uploaded)
  F10-13 listing detail owner block renders avatar img with profile_image_url
  F10-14 thread detail counterparty block renders avatar img
  F10-15 inbox thread list renders counterparty avatar img

Trust context on listing/thread surfaces (Req 3):
  F10-16 supply_lot_detail shows listing-owner div with avatar
  F10-17 demand_post_detail shows listing-owner div with avatar
  F10-18 thread_detail renders counterparty avatar in listing-owner div
  F10-19 thread_detail send button has btn-primary class

Safety boundary (Req 5):
  F10-20 unauthenticated profile access redirects to login
  F10-21 unauthenticated thread_detail access redirects to login
"""

from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from marketplace.models import (
    Listing,
    ListingShippingScope,
    ListingStatus,
    ListingType,
    MessageThread,
    User,
)


_STATIC_TEST_SETTINGS = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def _make_user(email, display_name="Test User"):
    return User.objects.create_user(
        email=email,
        password="testpass123",
        country="US",
        display_name=display_name,
        email_verified=True,
    )


def _make_supply(owner, title="Test Supply Item", status=ListingStatus.ACTIVE):
    return Listing.objects.create(
        type=ListingType.SUPPLY,
        created_by_user=owner,
        title=title,
        status=status,
        location_country="US",
        shipping_scope=ListingShippingScope.DOMESTIC,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=30),
    )


def _make_demand(owner, title="Test Demand Item", status=ListingStatus.ACTIVE):
    return Listing.objects.create(
        type=ListingType.DEMAND,
        created_by_user=owner,
        title=title,
        status=status,
        location_country="US",
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=30),
    )


def _make_thread(listing_owner, other_user, listing):
    """Create a MessageThread initiated by other_user about a listing owned by listing_owner."""
    return MessageThread.objects.create(
        listing=listing,
        created_by_user=other_user,
    )


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class ProfileSurfaceClarityTests(TestCase):
    """Req 1 — Profile page identity summary and navigation."""

    def setUp(self):
        self.user = _make_user("profile@example.com", display_name="Jane Doe")
        self.client.force_login(self.user)

    def test_f10_1_profile_shows_email(self):
        """F10-1: profile page renders user email."""
        resp = self.client.get(reverse("marketplace:profile"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "profile@example.com")

    def test_f10_2_profile_shows_listing_sections(self):
        """F10-2: profile page renders supply and demand listing sections."""
        resp = self.client.get(reverse("marketplace:profile"))
        self.assertContains(resp, "Supply Listings")
        self.assertContains(resp, "Demand Listings")

    def test_f10_3_profile_shows_edit_button(self):
        """F10-3: profile page shows Edit profile button."""
        resp = self.client.get(reverse("marketplace:profile"))
        self.assertContains(resp, reverse("marketplace:profile_edit"))
        self.assertContains(resp, "Edit profile")

    def test_f10_4_profile_shows_dashboard_link(self):
        """F10-4: profile page shows Back to dashboard link."""
        resp = self.client.get(reverse("marketplace:profile"))
        self.assertContains(resp, reverse("marketplace:dashboard"))
        self.assertContains(resp, "Back to dashboard")

    def test_f10_5_profile_shows_django_messages(self):
        """F10-5: profile page renders Django success messages."""
        from django.contrib.messages import get_messages
        session = self.client.session
        self.client.force_login(self.user)
        # Trigger a real profile save to generate a success message
        resp = self.client.post(
            reverse("marketplace:profile_edit"),
            {"display_name": "Jane Doe", "skin": "simple-blue", "timezone": "UTC", "distance_unit": "km"},
            follow=True,
        )
        self.assertContains(resp, "Profile updated")

    def test_f10_6_profile_listing_shows_status_badge(self):
        """F10-6: supply and demand listings on profile show status badge."""
        supply = _make_supply(self.user, title="Widget Supply")
        demand = _make_demand(self.user, title="Gadget Demand")
        resp = self.client.get(reverse("marketplace:profile"))
        self.assertContains(resp, "status-active")
        self.assertContains(resp, "Widget Supply")
        self.assertContains(resp, "Gadget Demand")


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class ProfileEditContinuityTests(TestCase):
    """Req 4 — Profile edit feedback and navigation."""

    def setUp(self):
        self.user = _make_user("edit@example.com", display_name="Edit User")
        self.client.force_login(self.user)

    def test_f10_7_profile_edit_has_save_button(self):
        """F10-7: profile_edit renders a btn-primary Save changes button."""
        resp = self.client.get(reverse("marketplace:profile_edit"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "btn-primary")
        self.assertContains(resp, "Save changes")

    def test_f10_8_profile_edit_has_cancel_link(self):
        """F10-8: profile_edit renders a Cancel link back to profile page."""
        resp = self.client.get(reverse("marketplace:profile_edit"))
        self.assertContains(resp, reverse("marketplace:profile"))
        self.assertContains(resp, "Cancel")

    def test_f10_9_profile_edit_redirects_to_profile_on_success(self):
        """F10-9: successful profile edit redirects to profile page."""
        resp = self.client.post(
            reverse("marketplace:profile_edit"),
            {"display_name": "Updated Name", "skin": "simple-blue", "timezone": "UTC", "distance_unit": "km"},
        )
        self.assertRedirects(resp, reverse("marketplace:profile"), fetch_redirect_response=False)

    def test_f10_10_profile_edit_saves_data(self):
        """F10-10: profile_edit saves updated display name to the model."""
        self.client.post(
            reverse("marketplace:profile_edit"),
            {"display_name": "Brand New Name", "skin": "simple-blue", "timezone": "UTC", "distance_unit": "km"},
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "Brand New Name")


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class AvatarFallbackTests(TestCase):
    """Req 2 — Avatar fallback and identity consistency."""

    def setUp(self):
        self.user = _make_user("avatar@example.com", display_name="Avatar User")
        self.client.force_login(self.user)

    def test_f10_11_no_avatar_has_valid_profile_image_url(self):
        """F10-11: user with no avatar still has a non-empty profile_image_url."""
        url = self.user.profile_image_url
        self.assertTrue(url)
        self.assertNotEqual(url, "")

    def test_f10_12_profile_page_avatar_img_present(self):
        """F10-12: profile page renders avatar img tag with valid src."""
        resp = self.client.get(reverse("marketplace:profile"))
        self.assertContains(resp, 'id="avatar-display"')
        self.assertContains(resp, self.user.profile_image_url)

    def test_f10_13_supply_detail_owner_avatar(self):
        """F10-13: supply_lot_detail shows listing-owner div with avatar img."""
        viewer = _make_user("viewer13@example.com")
        supply = _make_supply(self.user, title="Owner Avatar Supply")
        self.client.force_login(viewer)
        resp = self.client.get(reverse("marketplace:supply_lot_detail", kwargs={"pk": supply.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "listing-owner")
        self.assertContains(resp, self.user.profile_image_url)

    def test_f10_14_thread_detail_counterparty_avatar(self):
        """F10-14: thread_detail renders counterparty avatar in the header."""
        other = _make_user("counter14@example.com", display_name="Counter Party")
        supply = _make_supply(self.user, title="Thread Supply")
        thread = _make_thread(self.user, other, supply)
        self.client.force_login(self.user)
        resp = self.client.get(reverse("marketplace:thread_detail", kwargs={"pk": thread.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "listing-owner")
        self.assertContains(resp, other.profile_image_url)

    def test_f10_15_inbox_counterparty_avatar(self):
        """F10-15: inbox thread list renders counterparty avatar img."""
        other = _make_user("counter15@example.com", display_name="Inbox Counter")
        supply = _make_supply(self.user, title="Inbox Supply")
        thread = _make_thread(self.user, other, supply)
        # Add a message so thread appears in inbox (inbox filters on last_message_at annotation)
        thread.messages.create(sender=other, body="Hello")
        self.client.force_login(self.user)
        resp = self.client.get(reverse("marketplace:inbox"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, other.profile_image_url)


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class TrustContextTests(TestCase):
    """Req 3 — Owner/counterparty identity shown on listing/thread surfaces."""

    def setUp(self):
        self.owner = _make_user("owner@example.com", display_name="Owner User")
        self.viewer = _make_user("viewer@example.com", display_name="Viewer User")

    def test_f10_16_supply_detail_shows_listing_owner_section(self):
        """F10-16: supply_lot_detail contains listing-owner identity block."""
        supply = _make_supply(self.owner, title="Trust Supply")
        self.client.force_login(self.viewer)
        resp = self.client.get(reverse("marketplace:supply_lot_detail", kwargs={"pk": supply.pk}))
        self.assertContains(resp, "listing-owner")
        self.assertContains(resp, self.owner.display_name)

    def test_f10_17_demand_detail_shows_listing_owner_section(self):
        """F10-17: demand_post_detail contains listing-owner identity block."""
        demand = _make_demand(self.owner, title="Trust Demand")
        self.client.force_login(self.viewer)
        resp = self.client.get(reverse("marketplace:demand_post_detail", kwargs={"pk": demand.pk}))
        self.assertContains(resp, "listing-owner")
        self.assertContains(resp, self.owner.display_name)

    def test_f10_18_thread_detail_counterparty_in_listing_owner_div(self):
        """F10-18: thread_detail counterparty identity is in a listing-owner div."""
        supply = _make_supply(self.owner, title="Counter Trust Supply")
        thread = _make_thread(self.owner, self.viewer, supply)
        self.client.force_login(self.viewer)
        resp = self.client.get(reverse("marketplace:thread_detail", kwargs={"pk": thread.pk}))
        self.assertContains(resp, "listing-owner")
        self.assertContains(resp, self.owner.display_name)

    def test_f10_19_thread_detail_send_button_has_primary_class(self):
        """F10-19: thread_detail Send button has btn-primary class."""
        supply = _make_supply(self.owner, title="Send Button Supply")
        thread = _make_thread(self.owner, self.viewer, supply)
        self.client.force_login(self.viewer)
        resp = self.client.get(reverse("marketplace:thread_detail", kwargs={"pk": thread.pk}))
        self.assertContains(resp, 'class="btn btn-primary"')
        self.assertContains(resp, "Send")


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class SafetyBoundaryTests(TestCase):
    """Req 5 — Access permissions unchanged."""

    def test_f10_20_unauthenticated_profile_redirects(self):
        """F10-20: unauthenticated access to profile redirects to login."""
        resp = self.client.get(reverse("marketplace:profile"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp["Location"])

    def test_f10_21_unauthenticated_thread_detail_redirects(self):
        """F10-21: unauthenticated access to thread_detail redirects to login."""
        owner = _make_user("owner21@example.com")
        other = _make_user("other21@example.com")
        supply = _make_supply(owner, title="Auth Thread Supply")
        thread = _make_thread(owner, other, supply)
        resp = self.client.get(reverse("marketplace:thread_detail", kwargs={"pk": thread.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp["Location"])
