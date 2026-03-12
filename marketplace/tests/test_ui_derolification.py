from django.test import TestCase, override_settings, tag
from django.urls import reverse
from django.utils import timezone

from marketplace.migration_control.ui_compliance import TemplateLanguageComplianceScanner
from marketplace.models import Listing, ListingStatus, ListingType, User


_STATIC_TEST_SETTINGS = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
@tag("ui_derolification")
class UiDerolificationTests(TestCase):
    def setUp(self):
        self.password = "testpass123"
        self.user = User.objects.create_user(
            email="ui@example.com",
            password=self.password,
            country="US",
            display_name="UI User",
        )

    def test_signup_renders_no_role_field(self):
        response = self.client.get(reverse("marketplace:signup"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertNotIn('name="role"', html)
        self.assertIn("Create Account", html)

    def test_signup_heading_is_create_account(self):
        response = self.client.get(reverse("marketplace:signup"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Create Account", html)
        self.assertNotIn("Register as Buyer", html)
        self.assertNotIn("Register as Supplier", html)

    def test_navbar_shows_supply_and_demand_for_all_authenticated_users(self):
        self.client.login(email=self.user.email, password=self.password)
        response = self.client.get(reverse("marketplace:dashboard"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn(reverse("marketplace:supply_lot_list"), html)
        self.assertIn(reverse("marketplace:demand_post_list"), html)
        self.assertIn("Watchlist", html)

    def test_dashboard_heading_is_not_role_labeled(self):
        self.client.login(email=self.user.email, password=self.password)
        response = self.client.get(reverse("marketplace:dashboard"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Dashboard", html)
        self.assertNotIn("Buyer Dashboard", html)
        self.assertNotIn("Supplier Dashboard", html)

    def test_profile_shows_both_listing_sections(self):
        Listing.objects.create(
            type=ListingType.SUPPLY,
            created_by_user=self.user,
            title="Fresh mushrooms",
            status=ListingStatus.ACTIVE,
            location_country="US",
            shipping_scope="domestic",
            created_at=timezone.now(),
        )
        Listing.objects.create(
            type=ListingType.DEMAND,
            created_by_user=self.user,
            title="Need wild garlic",
            status=ListingStatus.ACTIVE,
            location_country="US",
            created_at=timezone.now(),
        )
        self.client.login(email=self.user.email, password=self.password)
        response = self.client.get(reverse("marketplace:profile"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Supply Listings", html)
        self.assertIn("Demand Listings", html)
        self.assertIn("Fresh mushrooms", html)
        self.assertIn("Need wild garlic", html)

    def test_no_page_contains_buyer_supplier_role_label(self):
        self.client.login(email=self.user.email, password=self.password)
        urls = [
            reverse("marketplace:dashboard"),
            reverse("marketplace:demand_post_list"),
            reverse("marketplace:supply_lot_list"),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            html = response.content.decode("utf-8")
            self.assertNotIn("Buyer Dashboard", html)
            self.assertNotIn("Supplier Dashboard", html)
            self.assertNotIn("Register as Buyer", html)
            self.assertNotIn("Register as Supplier", html)

        self.client.logout()
        signup_response = self.client.get(reverse("marketplace:signup"))
        self.assertEqual(signup_response.status_code, 200)
        signup_html = signup_response.content.decode("utf-8")
        self.assertNotIn("Register as Buyer", signup_html)
        self.assertNotIn("Register as Supplier", signup_html)

    def test_compliance_scanner_zero_violations(self):
        scanner = TemplateLanguageComplianceScanner()
        passed, violations = scanner.scan()
        self.assertTrue(passed)
        self.assertEqual(violations, [])
