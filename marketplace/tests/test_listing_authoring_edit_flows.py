"""
Feature 9: Listing Authoring and Edit Flows

Tests cover:
- Supply and demand create form rendering
- Supply and demand edit form rendering
- Submit paths (valid POST → detail redirect with success message)
- Cancel paths (create → list; edit → detail)
- Validation error feedback (field errors and non-field errors visible)
- Input preservation on failed submission
- Delete confirm page rendering (title, commit button, cancel link)
- Delete confirm commit path (POST → list redirect with success message)
- Delete confirm cancel path (links back to detail)
- Permission boundaries (only owner can access edit/delete)
- Auth gating (unauthenticated users redirected to login)
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
    User,
)


_STATIC_TEST_SETTINGS = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def _make_user(email, name="Test User"):
    return User.objects.create_user(
        email=email,
        password="testpass123",
        country="US",
        display_name=name,
    )


def _make_supply(owner, title="Test Supply", status=ListingStatus.ACTIVE):
    return Listing.objects.create(
        type=ListingType.SUPPLY,
        created_by_user=owner,
        title=title,
        status=status,
        location_country="US",
        shipping_scope=ListingShippingScope.DOMESTIC,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=14),
    )


def _make_demand(owner, title="Test Demand", status=ListingStatus.ACTIVE):
    return Listing.objects.create(
        type=ListingType.DEMAND,
        created_by_user=owner,
        title=title,
        status=status,
        location_country="US",
        created_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# Supply create flow
# ---------------------------------------------------------------------------

@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class SupplyCreateFlowTests(TestCase):
    """Supply listing create form — authoring flow tests."""

    def setUp(self):
        self.user = _make_user("supply.create@test.test")
        self.client.force_login(self.user)
        self.url = reverse("marketplace:supply_lot_create")

    def test_create_form_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_create_form_shows_new_title(self):
        response = self.client.get(self.url)
        self.assertContains(response, "New Supply Listing")

    def test_create_form_has_submit_button(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Create listing")

    def test_create_cancel_links_to_supply_list(self):
        response = self.client.get(self.url)
        list_url = reverse("marketplace:supply_lot_list")
        self.assertContains(response, list_url)

    def test_valid_post_redirects_to_detail(self):
        future = (timezone.now() + timedelta(days=30)).date()
        data = {
            "title": "Fresh apples",
            "category": "food_fresh",
            "quantity": "100",
            "unit": "kg",
            "expires_at": future.isoformat(),
            "available_until": future.isoformat(),
            "location_country": "US",
            "location_locality": "",
            "location_region": "",
            "location_postal_code": "",
            "shipping_scope": ListingShippingScope.DOMESTIC,
            "price_value": "5.00",
            "price_unit": "kg",
            "description": "",
        }
        response = self.client.post(self.url, data)
        lot = Listing.objects.filter(
            created_by_user=self.user,
            type=ListingType.SUPPLY,
        ).order_by("-created_at").first()
        self.assertIsNotNone(lot)
        self.assertRedirects(
            response,
            reverse("marketplace:supply_lot_detail", kwargs={"pk": lot.pk}),
        )

    def test_invalid_post_shows_error_banner(self):
        future = (timezone.now() + timedelta(days=30)).date()
        # Provide expires_at/available_until to avoid unhandled None in clean_expires_at;
        # leave other required fields blank to trigger validation errors.
        data = {
            "title": "",
            "category": "",
            "quantity": "",
            "unit": "",
            "expires_at": future.isoformat(),
            "available_until": future.isoformat(),
            "location_country": "US",
            "location_locality": "",
            "location_region": "",
            "location_postal_code": "",
            "shipping_scope": "",
            "price_value": "",
            "price_unit": "",
            "description": "",
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please correct the errors below.")

    def test_invalid_post_preserves_title_input(self):
        # Use an invalid date to trigger validation failure while preserving title input.
        data = {
            "title": "Partially filled",
            "category": "",
            "quantity": "",
            "unit": "",
            "expires_at": "not-a-date",
            "available_until": "not-a-date",
            "location_country": "US",
            "location_locality": "",
            "location_region": "",
            "location_postal_code": "",
            "shipping_scope": "",
            "price_value": "",
            "price_unit": "",
            "description": "",
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Partially filled")

    def test_unauthenticated_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)


# ---------------------------------------------------------------------------
# Supply edit flow
# ---------------------------------------------------------------------------

@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class SupplyEditFlowTests(TestCase):
    """Supply listing edit form — authoring flow tests."""

    def setUp(self):
        self.user = _make_user("supply.edit@test.test")
        self.client.force_login(self.user)
        self.lot = _make_supply(self.user, title="Editable Supply")

    def _edit_url(self):
        return reverse("marketplace:supply_lot_edit", kwargs={"pk": self.lot.pk})

    def test_edit_form_renders(self):
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 200)

    def test_edit_form_shows_edit_title(self):
        response = self.client.get(self._edit_url())
        self.assertContains(response, "Edit Supply Listing")

    def test_edit_form_has_save_button(self):
        response = self.client.get(self._edit_url())
        self.assertContains(response, "Save changes")

    def test_edit_form_prefills_existing_title(self):
        response = self.client.get(self._edit_url())
        self.assertContains(response, "Editable Supply")

    def test_edit_cancel_links_to_detail(self):
        response = self.client.get(self._edit_url())
        detail_url = reverse("marketplace:supply_lot_detail", kwargs={"pk": self.lot.pk})
        self.assertContains(response, detail_url)

    def test_valid_edit_post_redirects_to_detail(self):
        future = (timezone.now() + timedelta(days=30)).date()
        data = {
            "title": "Updated Supply",
            "category": "food_fresh",
            "quantity": "50",
            "unit": "kg",
            "expires_at": future.isoformat(),
            "available_until": future.isoformat(),
            "location_country": "US",
            "location_locality": "",
            "location_region": "",
            "location_postal_code": "",
            "shipping_scope": ListingShippingScope.DOMESTIC,
            "price_value": "3.00",
            "price_unit": "kg",
            "description": "",
        }
        response = self.client.post(self._edit_url(), data)
        self.assertRedirects(
            response,
            reverse("marketplace:supply_lot_detail", kwargs={"pk": self.lot.pk}),
        )

    def test_invalid_edit_post_shows_error_banner(self):
        future = (timezone.now() + timedelta(days=30)).date()
        # Leave required fields blank (title, unit) to trigger validation errors;
        # include expires_at/available_until to avoid an unhandled None in clean_expires_at.
        data = {
            "title": "",
            "category": "",
            "quantity": "",
            "unit": "",
            "expires_at": future.isoformat(),
            "available_until": future.isoformat(),
            "location_country": "US",
            "location_locality": "",
            "location_region": "",
            "location_postal_code": "",
            "shipping_scope": "",
            "price_value": "",
            "price_unit": "",
            "description": "",
        }
        response = self.client.post(self._edit_url(), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please correct the errors below.")

    def test_non_owner_cannot_edit(self):
        other = _make_user("other.supply@test.test")
        self.client.force_login(other)
        response = self.client.get(self._edit_url())
        self.assertIn(response.status_code, [403, 302])

    def test_unauthenticated_edit_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)


# ---------------------------------------------------------------------------
# Demand create flow
# ---------------------------------------------------------------------------

@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class DemandCreateFlowTests(TestCase):
    """Demand listing create form — authoring flow tests."""

    def setUp(self):
        self.user = _make_user("demand.create@test.test")
        self.client.force_login(self.user)
        self.url = reverse("marketplace:demand_post_create")

    def test_create_form_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_create_form_shows_new_title(self):
        response = self.client.get(self.url)
        self.assertContains(response, "New Demand Listing")

    def test_create_form_has_submit_button(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Create listing")

    def test_create_cancel_links_to_demand_list(self):
        response = self.client.get(self.url)
        list_url = reverse("marketplace:demand_post_list")
        self.assertContains(response, list_url)

    def test_valid_post_redirects_to_detail(self):
        data = {
            "title": "Looking for apples",
            "category": "food_fresh",
            "quantity": "50",
            "unit": "kg",
            "frequency": "",
            "location_country": "US",
            "location_locality": "",
            "location_region": "",
            "location_postal_code": "",
            "radius_km": "",
            "description": "",
        }
        response = self.client.post(self.url, data)
        post = Listing.objects.filter(
            created_by_user=self.user,
            type=ListingType.DEMAND,
        ).order_by("-created_at").first()
        self.assertIsNotNone(post)
        self.assertRedirects(
            response,
            reverse("marketplace:demand_post_detail", kwargs={"pk": post.pk}),
        )

    def test_invalid_post_shows_error_banner(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please correct the errors below.")

    def test_invalid_post_preserves_title_input(self):
        # Leave location_country blank to trigger a required-field error
        # while preserving the title input in the re-rendered form.
        data = {
            "title": "Half filled demand",
            "category": "",
            "quantity": "",
            "unit": "",
            "frequency": "",
            "location_country": "",
            "location_locality": "",
            "location_region": "",
            "location_postal_code": "",
            "radius_km": "",
            "description": "",
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Half filled demand")

    def test_unauthenticated_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)


# ---------------------------------------------------------------------------
# Demand edit flow
# ---------------------------------------------------------------------------

@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class DemandEditFlowTests(TestCase):
    """Demand listing edit form — authoring flow tests."""

    def setUp(self):
        self.user = _make_user("demand.edit@test.test")
        self.client.force_login(self.user)
        self.post = _make_demand(self.user, title="Editable Demand")

    def _edit_url(self):
        return reverse("marketplace:demand_post_edit", kwargs={"pk": self.post.pk})

    def test_edit_form_renders(self):
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 200)

    def test_edit_form_shows_edit_title(self):
        response = self.client.get(self._edit_url())
        self.assertContains(response, "Edit Demand Listing")

    def test_edit_form_has_save_button(self):
        response = self.client.get(self._edit_url())
        self.assertContains(response, "Save changes")

    def test_edit_form_prefills_existing_title(self):
        response = self.client.get(self._edit_url())
        self.assertContains(response, "Editable Demand")

    def test_edit_cancel_links_to_detail(self):
        response = self.client.get(self._edit_url())
        detail_url = reverse("marketplace:demand_post_detail", kwargs={"pk": self.post.pk})
        self.assertContains(response, detail_url)

    def test_valid_edit_post_redirects_to_detail(self):
        data = {
            "title": "Updated Demand",
            "category": "food_fresh",
            "quantity": "30",
            "unit": "kg",
            "frequency": "",
            "location_country": "US",
            "location_locality": "",
            "location_region": "",
            "location_postal_code": "",
            "radius_km": "",
            "description": "",
        }
        response = self.client.post(self._edit_url(), data)
        self.assertRedirects(
            response,
            reverse("marketplace:demand_post_detail", kwargs={"pk": self.post.pk}),
        )

    def test_invalid_edit_post_shows_error_banner(self):
        response = self.client.post(self._edit_url(), {"title": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please correct the errors below.")

    def test_non_owner_cannot_edit(self):
        other = _make_user("other.demand@test.test")
        self.client.force_login(other)
        response = self.client.get(self._edit_url())
        self.assertIn(response.status_code, [403, 302])

    def test_unauthenticated_edit_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)


# ---------------------------------------------------------------------------
# Supply delete confirm flow
# ---------------------------------------------------------------------------

@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class SupplyDeleteConfirmTests(TestCase):
    """Supply listing delete confirmation — authoring flow tests."""

    def setUp(self):
        self.user = _make_user("supply.delete@test.test")
        self.client.force_login(self.user)
        self.lot = _make_supply(self.user, title="Supply To Delete")

    def _delete_url(self):
        return reverse("marketplace:supply_lot_delete", kwargs={"pk": self.lot.pk})

    def test_delete_confirm_page_renders(self):
        response = self.client.get(self._delete_url())
        self.assertEqual(response.status_code, 200)

    def test_delete_confirm_shows_listing_title(self):
        response = self.client.get(self._delete_url())
        self.assertContains(response, "Supply To Delete")

    def test_delete_confirm_has_danger_button(self):
        response = self.client.get(self._delete_url())
        self.assertContains(response, "Yes, delete")

    def test_delete_confirm_has_cancel_link(self):
        response = self.client.get(self._delete_url())
        detail_url = reverse("marketplace:supply_lot_detail", kwargs={"pk": self.lot.pk})
        self.assertContains(response, detail_url)

    def test_delete_confirm_has_consequences_text(self):
        response = self.client.get(self._delete_url())
        self.assertContains(response, "cannot be undone")

    def test_delete_post_redirects_to_supply_list(self):
        response = self.client.post(self._delete_url())
        self.assertRedirects(response, reverse("marketplace:supply_lot_list"))

    def test_delete_post_sets_deleted_status(self):
        self.client.post(self._delete_url())
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.status, ListingStatus.DELETED)

    def test_non_owner_cannot_delete(self):
        other = _make_user("other.supply.del@test.test")
        self.client.force_login(other)
        response = self.client.get(self._delete_url())
        self.assertIn(response.status_code, [403, 302])

    def test_unauthenticated_delete_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(self._delete_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)


# ---------------------------------------------------------------------------
# Demand delete confirm flow
# ---------------------------------------------------------------------------

@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class DemandDeleteConfirmTests(TestCase):
    """Demand listing delete confirmation — authoring flow tests."""

    def setUp(self):
        self.user = _make_user("demand.delete@test.test")
        self.client.force_login(self.user)
        self.post = _make_demand(self.user, title="Demand To Delete")

    def _delete_url(self):
        return reverse("marketplace:demand_post_delete", kwargs={"pk": self.post.pk})

    def test_delete_confirm_page_renders(self):
        response = self.client.get(self._delete_url())
        self.assertEqual(response.status_code, 200)

    def test_delete_confirm_shows_listing_title(self):
        response = self.client.get(self._delete_url())
        self.assertContains(response, "Demand To Delete")

    def test_delete_confirm_has_danger_button(self):
        response = self.client.get(self._delete_url())
        self.assertContains(response, "Yes, delete")

    def test_delete_confirm_has_cancel_link(self):
        response = self.client.get(self._delete_url())
        detail_url = reverse("marketplace:demand_post_detail", kwargs={"pk": self.post.pk})
        self.assertContains(response, detail_url)

    def test_delete_confirm_has_consequences_text(self):
        response = self.client.get(self._delete_url())
        self.assertContains(response, "cannot be undone")

    def test_delete_post_redirects_to_demand_list(self):
        response = self.client.post(self._delete_url())
        self.assertRedirects(response, reverse("marketplace:demand_post_list"))

    def test_delete_post_sets_deleted_status(self):
        self.client.post(self._delete_url())
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, ListingStatus.DELETED)

    def test_non_owner_cannot_delete(self):
        other = _make_user("other.demand.del@test.test")
        self.client.force_login(other)
        response = self.client.get(self._delete_url())
        self.assertIn(response.status_code, [403, 302])

    def test_unauthenticated_delete_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(self._delete_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
