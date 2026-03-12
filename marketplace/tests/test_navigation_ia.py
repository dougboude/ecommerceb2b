from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings, tag
from django.urls import reverse

from marketplace.context_processors import nav_section
from marketplace.models import User


_STATIC_TEST_SETTINGS = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@tag("navigation_ia")
class NavSectionMappingTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _resolve(self, path):
        request = self.factory.get(path)
        return nav_section(request)["nav_section"]

    def test_canonical_route_families_map_to_expected_sections(self):
        self.assertEqual(self._resolve("/"), "dashboard")
        self.assertEqual(self._resolve("/discover/"), "discover")
        self.assertEqual(self._resolve("/messages/"), "messages")
        self.assertEqual(self._resolve("/threads/12/"), "messages")
        self.assertEqual(self._resolve("/watchlist/"), "watchlist")
        self.assertEqual(self._resolve("/profile/edit/"), "profile")
        self.assertEqual(self._resolve("/available/"), "supply")
        self.assertEqual(self._resolve("/available/12/edit/"), "supply")
        self.assertEqual(self._resolve("/wanted/"), "demand")
        self.assertEqual(self._resolve("/wanted/34/delete/"), "demand")

    def test_unknown_routes_have_no_active_section(self):
        self.assertEqual(self._resolve("/does-not-exist/"), "")


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
@tag("navigation_ia")
class NavigationTemplateBehaviorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="nav@example.com",
            password="testpass123",
            country="US",
            display_name="Nav User",
        )
        self.client.force_login(self.user)

    def test_authenticated_nav_uses_canonical_labels(self):
        response = self.client.get(reverse("marketplace:discover"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn(">Discover<", html)
        self.assertIn(">Messages<", html)
        self.assertIn(">Watchlist<", html)
        self.assertIn(">Supply<", html)
        self.assertIn(">Demand<", html)
        self.assertIn(">Profile<", html)
        self.assertIn(">Log out<", html)
        self.assertNotIn(">Dashboard<", html)
        self.assertNotIn("Your Listings:", html)

    def test_supply_nav_active_does_not_activate_demand(self):
        response = self.client.get(reverse("marketplace:supply_lot_list"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn(
            f'href="{reverse("marketplace:supply_lot_list")}" class="nav-active" aria-current="page"',
            html,
        )
        self.assertNotIn(
            f'href="{reverse("marketplace:demand_post_list")}" class="nav-active" aria-current="page"',
            html,
        )

    def test_demand_nav_active_does_not_activate_supply(self):
        response = self.client.get(reverse("marketplace:demand_post_list"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn(
            f'href="{reverse("marketplace:demand_post_list")}" class="nav-active" aria-current="page"',
            html,
        )
        self.assertNotIn(
            f'href="{reverse("marketplace:supply_lot_list")}" class="nav-active" aria-current="page"',
            html,
        )

    def test_inbox_empty_state_offers_primary_next_action(self):
        response = self.client.get(reverse("marketplace:inbox"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("No conversations yet.", html)
        self.assertIn(reverse("marketplace:discover"), html)
        self.assertIn(reverse("marketplace:watchlist"), html)
        self.assertIn("Discover listings", html)
