from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from marketplace.forms import DiscoverForm
from marketplace.migration_control.parity import ParityValidator
from marketplace.models import (
    DemandPost,
    DemandStatus,
    Organization,
    Role,
    SupplyLot,
    SupplyStatus,
    User,
)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class DiscoverDirectionAndVisibilityTests(TestCase):
    def setUp(self):
        self.search_user = User.objects.create_user(
            email="searcher@example.com",
            password="pass",
            role=Role.SUPPLIER,
            country="US",
            display_name="Searcher",
        )
        self.supply_owner = User.objects.create_user(
            email="supply-owner@example.com",
            password="pass",
            role=Role.SUPPLIER,
            country="US",
            display_name="Supply Owner",
        )
        self.demand_owner = User.objects.create_user(
            email="demand-owner@example.com",
            password="pass",
            role=Role.BUYER,
            country="US",
            display_name="Demand Owner",
        )
        self.demand_org = Organization.objects.create(
            owner=self.demand_owner,
            name="Demand Org",
            type="",
            country="US",
        )
        self.now = timezone.now()

    def _discover(self, direction, query="tomato"):
        return self.client.post(
            reverse("marketplace:discover"),
            data={
                "query": query,
                "direction": direction,
                "search_mode": DiscoverForm.SEARCH_MODE_KEYWORD,
                "sort_by": DiscoverForm.SORT_BEST_MATCH,
                "category": "",
                "location_country": "",
                "radius": "",
                "exclude_watched": "",
            },
        )

    def test_authenticated_user_can_choose_both_directions(self):
        supply = SupplyLot.objects.create(
            created_by=self.supply_owner,
            item_text="Tomato crates",
            category="food_fresh",
            quantity_value=10,
            quantity_unit="kg",
            available_until=self.now + timedelta(days=3),
            notes="Fresh",
            status=SupplyStatus.ACTIVE,
            location_country="US",
        )
        demand = DemandPost.objects.create(
            organization=self.demand_org,
            created_by=self.demand_owner,
            item_text="Tomato crates",
            category="food_fresh",
            quantity_value=5,
            quantity_unit="kg",
            frequency="one_time",
            notes="Need now",
            status=DemandStatus.ACTIVE,
            location_country="US",
            expires_at=self.now + timedelta(days=2),
        )
        self.client.force_login(self.search_user)

        resp_supply = self._discover(DiscoverForm.DIRECTION_FIND_SUPPLY)
        self.assertEqual(resp_supply.status_code, 200)
        self.assertEqual(resp_supply.context["results"][0].discover_listing_type, "supply_lot")
        self.assertEqual(resp_supply.context["results"][0].discover_listing_pk, supply.pk)
        self.assertEqual(
            self.client.session.get("discover_last_direction"),
            DiscoverForm.DIRECTION_FIND_SUPPLY,
        )

        resp_demand = self._discover(DiscoverForm.DIRECTION_FIND_DEMAND)
        self.assertEqual(resp_demand.status_code, 200)
        self.assertEqual(resp_demand.context["results"][0].discover_listing_type, "demand_post")
        self.assertEqual(resp_demand.context["results"][0].discover_listing_pk, demand.pk)
        self.assertEqual(
            self.client.session.get("discover_last_direction"),
            DiscoverForm.DIRECTION_FIND_DEMAND,
        )

    def test_clear_search_clears_persisted_direction_state(self):
        self.client.force_login(self.search_user)
        self._discover(DiscoverForm.DIRECTION_FIND_SUPPLY, query="cucumber")
        self.assertIn("discover_last_direction", self.client.session)

        resp = self.client.get(reverse("marketplace:discover_clear"))
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("discover_last_direction", self.client.session)

    def test_discover_visibility_includes_only_active_counterpart_status(self):
        active_supply = SupplyLot.objects.create(
            created_by=self.supply_owner,
            item_text="Mango pallets",
            category="food_fresh",
            quantity_value=50,
            quantity_unit="kg",
            available_until=self.now + timedelta(days=2),
            notes="Active lot",
            status=SupplyStatus.ACTIVE,
            location_country="US",
        )
        SupplyLot.objects.create(
            created_by=self.supply_owner,
            item_text="Mango pallets",
            category="food_fresh",
            quantity_value=50,
            quantity_unit="kg",
            available_until=self.now + timedelta(days=2),
            notes="Withdrawn lot",
            status=SupplyStatus.WITHDRAWN,
            location_country="US",
        )
        DemandPost.objects.create(
            organization=self.demand_org,
            created_by=self.demand_owner,
            item_text="Mango pallets",
            category="food_fresh",
            quantity_value=20,
            quantity_unit="kg",
            frequency="one_time",
            notes="Active demand",
            status=DemandStatus.ACTIVE,
            location_country="US",
            expires_at=self.now + timedelta(days=2),
        )
        DemandPost.objects.create(
            organization=self.demand_org,
            created_by=self.demand_owner,
            item_text="Mango pallets",
            category="food_fresh",
            quantity_value=20,
            quantity_unit="kg",
            frequency="one_time",
            notes="Paused demand",
            status=DemandStatus.PAUSED,
            location_country="US",
            expires_at=self.now + timedelta(days=2),
        )
        self.client.force_login(self.search_user)

        supply_resp = self._discover(DiscoverForm.DIRECTION_FIND_SUPPLY, query="mango")
        supply_ids = {r.discover_listing_pk for r in supply_resp.context["results"]}
        self.assertEqual(supply_ids, {active_supply.pk})

        demand_resp = self._discover(DiscoverForm.DIRECTION_FIND_DEMAND, query="mango")
        for listing in demand_resp.context["results"]:
            self.assertEqual(listing.status, DemandStatus.ACTIVE)


class DiscoverContractValidationTests(TestCase):
    def test_parity_validator_discover_scope_passes(self):
        result = ParityValidator().validate_discover_contract()
        self.assertTrue(result.passed, result.summary)

    def test_migration_validate_discover_scope_runs(self):
        call_command("migration_validate", "--scope", "discover")
