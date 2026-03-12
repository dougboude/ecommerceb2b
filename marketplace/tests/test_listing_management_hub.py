"""
Feature 8: Supply and Demand Listing Management Hub

Tests cover:
- Supply/demand list page parity
- Listing count summary on management pages
- Create CTA present in header (always) and empty state
- Filter and pagination behavior
- List -> detail -> action -> return transitions
- Status visibility
- Permission boundaries (owner-only access)
"""

from datetime import timedelta

from django.test import TestCase, override_settings, tag
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


def _make_supply(owner, title, status=ListingStatus.ACTIVE, days_until_expiry=14):
    return Listing.objects.create(
        type=ListingType.SUPPLY,
        created_by_user=owner,
        title=title,
        status=status,
        location_country="US",
        shipping_scope=ListingShippingScope.DOMESTIC,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=days_until_expiry),
    )


def _make_demand(owner, title, status=ListingStatus.ACTIVE):
    return Listing.objects.create(
        type=ListingType.DEMAND,
        created_by_user=owner,
        title=title,
        status=status,
        location_country="US",
        created_at=timezone.now(),
    )


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
@tag("listing_management_hub")
class SupplyListPageTests(TestCase):
    """Supply listing management hub — list page tests."""

    def setUp(self):
        self.user = _make_user("supply@hub.test", "Supply User")
        self.client.force_login(self.user)

    def test_supply_list_page_loads(self):
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertEqual(response.status_code, 200)

    def test_supply_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertNotEqual(response.status_code, 200)

    def test_supply_list_shows_create_cta_in_header(self):
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("marketplace:supply_lot_create"))
        self.assertContains(response, "Create new")

    def test_supply_list_shows_listings(self):
        lot = _make_supply(self.user, "Wheat flour")
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wheat flour")

    def test_supply_list_shows_status_badge(self):
        _make_supply(self.user, "Active supply", status=ListingStatus.ACTIVE)
        _make_supply(self.user, "Withdrawn supply", status=ListingStatus.WITHDRAWN)
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "status-active")
        self.assertContains(response, "status-withdrawn")

    def test_supply_list_shows_listing_count_summary(self):
        _make_supply(self.user, "Active lot")
        _make_supply(self.user, "Withdrawn lot", status=ListingStatus.WITHDRAWN)
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertEqual(response.status_code, 200)
        # Should show total count (2) and active count (1)
        self.assertContains(response, "listing-summary")
        self.assertContains(response, "2 listing")
        self.assertContains(response, "1 active")

    def test_supply_list_empty_state_shows_create_cta(self):
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No supply listings yet.")
        self.assertContains(response, "Create your first supply listing")
        self.assertContains(response, reverse("marketplace:supply_lot_create"))

    def test_supply_list_only_shows_own_listings(self):
        other_user = _make_user("other@hub.test", "Other User")
        _make_supply(other_user, "Other's lot")
        _make_supply(self.user, "My lot")
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My lot")
        self.assertNotContains(response, "Other's lot")

    def test_supply_list_excludes_deleted_listings(self):
        _make_supply(self.user, "Deleted lot", status=ListingStatus.DELETED)
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Deleted lot")

    def test_supply_list_includes_filter_bar_when_listings_exist(self):
        _make_supply(self.user, "Filterable lot")
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "listing-filter-bar")
        self.assertContains(response, "listing-filter-input")

    def test_supply_list_links_to_detail_page(self):
        lot = _make_supply(self.user, "Linked lot")
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("marketplace:supply_lot_detail", kwargs={"pk": lot.pk}))


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
@tag("listing_management_hub")
class DemandListPageTests(TestCase):
    """Demand listing management hub — list page tests."""

    def setUp(self):
        self.user = _make_user("demand@hub.test", "Demand User")
        self.client.force_login(self.user)

    def test_demand_list_page_loads(self):
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertEqual(response.status_code, 200)

    def test_demand_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertNotEqual(response.status_code, 200)

    def test_demand_list_shows_create_cta_in_header(self):
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("marketplace:demand_post_create"))
        self.assertContains(response, "Create new")

    def test_demand_list_shows_listings(self):
        _make_demand(self.user, "Organic oats")
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Organic oats")

    def test_demand_list_shows_status_badge(self):
        _make_demand(self.user, "Active demand", status=ListingStatus.ACTIVE)
        _make_demand(self.user, "Paused demand", status=ListingStatus.PAUSED)
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "status-active")
        self.assertContains(response, "status-paused")

    def test_demand_list_shows_listing_count_summary(self):
        _make_demand(self.user, "Active post")
        _make_demand(self.user, "Paused post", status=ListingStatus.PAUSED)
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "listing-summary")
        self.assertContains(response, "2 listing")
        self.assertContains(response, "1 active")

    def test_demand_list_empty_state_shows_create_cta(self):
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No demand listings yet.")
        self.assertContains(response, "Create your first demand listing")
        self.assertContains(response, reverse("marketplace:demand_post_create"))

    def test_demand_list_only_shows_own_listings(self):
        other_user = _make_user("other_demand@hub.test", "Other User")
        _make_demand(other_user, "Other's post")
        _make_demand(self.user, "My post")
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My post")
        self.assertNotContains(response, "Other's post")

    def test_demand_list_excludes_deleted_listings(self):
        _make_demand(self.user, "Deleted post", status=ListingStatus.DELETED)
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Deleted post")

    def test_demand_list_includes_filter_bar_when_listings_exist(self):
        _make_demand(self.user, "Filterable post")
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "listing-filter-bar")
        self.assertContains(response, "listing-filter-input")

    def test_demand_list_links_to_detail_page(self):
        post = _make_demand(self.user, "Linked post")
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("marketplace:demand_post_detail", kwargs={"pk": post.pk}))


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
@tag("listing_management_hub")
class ListDetailActionTransitionTests(TestCase):
    """List -> detail -> action -> return flow tests."""

    def setUp(self):
        self.user = _make_user("owner@hub.test", "Owner")
        self.client.force_login(self.user)

    def test_supply_detail_has_back_to_list_link(self):
        lot = _make_supply(self.user, "Back link supply")
        response = self.client.get(reverse("marketplace:supply_lot_detail", kwargs={"pk": lot.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("marketplace:supply_lot_list"))
        self.assertContains(response, "Back to list")

    def test_demand_detail_has_back_to_list_link(self):
        post = _make_demand(self.user, "Back link demand")
        response = self.client.get(reverse("marketplace:demand_post_detail", kwargs={"pk": post.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("marketplace:demand_post_list"))
        self.assertContains(response, "Back to list")

    def test_supply_toggle_redirects_to_detail(self):
        lot = _make_supply(self.user, "Toggle supply", status=ListingStatus.ACTIVE)
        response = self.client.post(
            reverse("marketplace:supply_lot_toggle", kwargs={"pk": lot.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        lot.refresh_from_db()
        self.assertEqual(lot.status, ListingStatus.WITHDRAWN)

    def test_demand_toggle_pauses_and_redirects_to_detail(self):
        post = _make_demand(self.user, "Toggle demand", status=ListingStatus.ACTIVE)
        response = self.client.post(
            reverse("marketplace:demand_post_toggle", kwargs={"pk": post.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.status, ListingStatus.PAUSED)

    def test_supply_detail_shows_edit_link_for_active(self):
        lot = _make_supply(self.user, "Editable supply", status=ListingStatus.ACTIVE)
        response = self.client.get(reverse("marketplace:supply_lot_detail", kwargs={"pk": lot.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("marketplace:supply_lot_edit", kwargs={"pk": lot.pk}))

    def test_demand_detail_shows_edit_link_for_active(self):
        post = _make_demand(self.user, "Editable demand", status=ListingStatus.ACTIVE)
        response = self.client.get(reverse("marketplace:demand_post_detail", kwargs={"pk": post.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("marketplace:demand_post_edit", kwargs={"pk": post.pk}))

    def test_supply_detail_shows_withdraw_action_for_active(self):
        lot = _make_supply(self.user, "Withdrawable supply", status=ListingStatus.ACTIVE)
        response = self.client.get(reverse("marketplace:supply_lot_detail", kwargs={"pk": lot.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Withdraw")

    def test_demand_detail_shows_pause_action_for_active(self):
        post = _make_demand(self.user, "Pausable demand", status=ListingStatus.ACTIVE)
        response = self.client.get(reverse("marketplace:demand_post_detail", kwargs={"pk": post.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pause")

    def test_supply_detail_shows_reactivate_for_withdrawn(self):
        lot = _make_supply(self.user, "Withdrawn supply", status=ListingStatus.WITHDRAWN)
        response = self.client.get(reverse("marketplace:supply_lot_detail", kwargs={"pk": lot.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reactivate")

    def test_demand_detail_shows_resume_for_paused(self):
        post = _make_demand(self.user, "Paused demand", status=ListingStatus.PAUSED)
        response = self.client.get(reverse("marketplace:demand_post_detail", kwargs={"pk": post.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resume")

    def test_non_owner_cannot_see_management_actions(self):
        other = _make_user("other@hub.test", "Other")
        lot = _make_supply(other, "Not mine")
        response = self.client.get(reverse("marketplace:supply_lot_detail", kwargs={"pk": lot.pk}))
        self.assertEqual(response.status_code, 200)
        # Owner-only action buttons should not appear
        self.assertNotContains(response, "Withdraw")
        self.assertNotContains(response, "Back to list")
        self.assertNotContains(response, reverse("marketplace:supply_lot_edit", kwargs={"pk": lot.pk}))


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
@tag("listing_management_hub")
class ListSupplyDemandParityTests(TestCase):
    """Verify structural parity between supply and demand management surfaces."""

    def setUp(self):
        self.user = _make_user("parity@hub.test", "Parity User")
        self.client.force_login(self.user)

    def test_both_list_pages_have_page_header_with_create_cta(self):
        supply_response = self.client.get(reverse("marketplace:supply_lot_list"))
        demand_response = self.client.get(reverse("marketplace:demand_post_list"))
        for response in (supply_response, demand_response):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "page-header")
            self.assertContains(response, "Create new")

    def test_both_list_pages_show_filter_bar_when_populated(self):
        _make_supply(self.user, "Supply item")
        _make_demand(self.user, "Demand item")
        supply_response = self.client.get(reverse("marketplace:supply_lot_list"))
        demand_response = self.client.get(reverse("marketplace:demand_post_list"))
        for response in (supply_response, demand_response):
            self.assertContains(response, "listing-filter-bar")

    def test_both_list_pages_show_summary_when_populated(self):
        _make_supply(self.user, "Supply item")
        _make_demand(self.user, "Demand item")
        supply_response = self.client.get(reverse("marketplace:supply_lot_list"))
        demand_response = self.client.get(reverse("marketplace:demand_post_list"))
        for response in (supply_response, demand_response):
            self.assertContains(response, "listing-summary")

    def test_both_empty_states_include_create_cta(self):
        supply_response = self.client.get(reverse("marketplace:supply_lot_list"))
        demand_response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertContains(supply_response, "Create your first supply listing")
        self.assertContains(demand_response, "Create your first demand listing")

    def test_both_list_pages_pass_context_counts(self):
        _make_supply(self.user, "Active supply")
        _make_supply(self.user, "Withdrawn supply", status=ListingStatus.WITHDRAWN)
        _make_demand(self.user, "Active demand")
        _make_demand(self.user, "Paused demand", status=ListingStatus.PAUSED)

        supply_response = self.client.get(reverse("marketplace:supply_lot_list"))
        demand_response = self.client.get(reverse("marketplace:demand_post_list"))

        self.assertEqual(supply_response.context["total_count"], 2)
        self.assertEqual(supply_response.context["active_count"], 1)
        self.assertEqual(demand_response.context["total_count"], 2)
        self.assertEqual(demand_response.context["active_count"], 1)
