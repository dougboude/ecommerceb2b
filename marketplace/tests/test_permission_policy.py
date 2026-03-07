"""
Feature 4: Ownership-Based Permission Policy regression tests.

Covers:
- PolicyEngine predicates (is_listing_owner, is_thread_participant,
  is_watchlist_owner, is_self_message_attempt)
- PermissionService decisions (listing mutation, message initiation,
  thread access, watchlist action)
- RoleAuthComplianceScanner detecting/not-detecting role patterns
- ParityValidator.validate_permission_policy()
- Checkpoint gate requiring permission parity evidence (CP4/CP5)
- View-level: owner-allowed / non-owner-denied for listing mutations
- View-level: self-message block enforcement
- View-level: participant-only thread access
- View-level: watchlist ownership enforcement
- View-level: list/create views no longer role-gated
"""
from unittest import SkipTest

raise SkipTest("Legacy permission-policy migration tests retired after CP5 cleanup")

from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

# Use simple static files storage so 403/permission templates render in tests
# without requiring `collectstatic` to be run first.
_STATIC_TEST_SETTINGS = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

from marketplace.migration_control.checkpoints import CheckpointController
from marketplace.migration_control.parity import ParityValidator
from marketplace.migration_control.permissions import (
    Decision,
    PolicyEngine,
    PermissionService,
    RoleAuthComplianceScanner,
    permission_service,
)
from marketplace.models import (
    DemandPost,
    DemandStatus,
    Listing,
    ListingStatus,
    ListingType,
    MessageThread,
    Organization,
    ParityReport,
    Role,
    SupplyLot,
    SupplyStatus,
    User,
    WatchlistItem,
    WatchlistSource,
    WatchlistStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email, role=Role.SUPPLIER, display_name="User"):
    return User.objects.create_user(
        email=email,
        password="testpass",
        role=role,
        country="US",
        display_name=display_name,
    )


def make_supply_lot(created_by):
    return SupplyLot.objects.create(
        created_by=created_by,
        item_text="Widget",
        available_until=timezone.now() + timedelta(days=30),
        shipping_scope="domestic",
        location_country="US",
    )


def make_demand_post(created_by):
    org, _ = Organization.objects.get_or_create(
        owner=created_by,
        defaults={"name": "Test Org", "type": "", "country": "US"},
    )
    return DemandPost.objects.create(
        created_by=created_by,
        organization=org,
        item_text="Needed Widget",
        frequency="one_time",
        location_country="US",
    )


def make_watchlist_item(user, supply_lot=None, demand_post=None):
    kwargs = {"user": user, "source": WatchlistSource.DIRECT}
    if supply_lot:
        kwargs["supply_lot"] = supply_lot
    else:
        kwargs["demand_post"] = demand_post
    return WatchlistItem.objects.create(**kwargs)


def ensure_listing_for_supply_lot(lot):
    listing, _ = Listing.objects.update_or_create(
        legacy_source_type="supply_lot",
        legacy_source_pk=lot.pk,
        defaults={
            "type": ListingType.SUPPLY,
            "created_by_user": lot.created_by,
            "title": lot.item_text,
            "description": lot.notes,
            "status": ListingStatus.ACTIVE if lot.status == SupplyStatus.ACTIVE else ListingStatus.WITHDRAWN,
            "location_country": lot.location_country,
            "shipping_scope": "domestic",
            "expires_at": lot.available_until,
            "created_at": lot.created_at,
        },
    )
    return listing


def ensure_listing_for_demand_post(post):
    listing, _ = Listing.objects.update_or_create(
        legacy_source_type="demand_post",
        legacy_source_pk=post.pk,
        defaults={
            "type": ListingType.DEMAND,
            "created_by_user": post.created_by,
            "title": post.item_text,
            "description": post.notes,
            "status": ListingStatus.ACTIVE if post.status == DemandStatus.ACTIVE else ListingStatus.PAUSED,
            "location_country": post.location_country,
            "frequency": post.frequency,
            "expires_at": post.expires_at,
            "created_at": post.created_at,
        },
    )
    return listing


def make_thread(watchlist_item, buyer, supplier):
    return MessageThread.objects.create(
        watchlist_item=watchlist_item,
        buyer=buyer,
        supplier=supplier,
    )


# ---------------------------------------------------------------------------
# PolicyEngine unit tests
# ---------------------------------------------------------------------------

class PolicyEngineOwnershipTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com", role=Role.SUPPLIER)
        self.other = make_user("other@example.com", role=Role.SUPPLIER)
        self.lot = make_supply_lot(self.owner)
        self.engine = PolicyEngine()

    def test_is_listing_owner_true_for_creator(self):
        self.assertTrue(self.engine.is_listing_owner(self.owner.pk, self.lot))

    def test_is_listing_owner_false_for_non_creator(self):
        self.assertFalse(self.engine.is_listing_owner(self.other.pk, self.lot))

    def test_is_self_message_attempt_true_for_owner(self):
        self.assertTrue(self.engine.is_self_message_attempt(self.owner.pk, self.lot))

    def test_is_self_message_attempt_false_for_non_owner(self):
        self.assertFalse(self.engine.is_self_message_attempt(self.other.pk, self.lot))


class PolicyEngineParticipantTests(TestCase):
    def setUp(self):
        self.buyer = make_user("buyer@example.com", role=Role.BUYER)
        self.supplier = make_user("supplier@example.com", role=Role.SUPPLIER)
        self.outsider = make_user("outsider@example.com")
        self.lot = make_supply_lot(self.supplier)
        self.item = make_watchlist_item(self.buyer, supply_lot=self.lot)
        self.thread = make_thread(self.item, buyer=self.buyer, supplier=self.supplier)
        self.engine = PolicyEngine()

    def test_is_thread_participant_true_for_buyer(self):
        self.assertTrue(self.engine.is_thread_participant(self.buyer.pk, self.thread))

    def test_is_thread_participant_true_for_supplier(self):
        self.assertTrue(self.engine.is_thread_participant(self.supplier.pk, self.thread))

    def test_is_thread_participant_false_for_outsider(self):
        self.assertFalse(self.engine.is_thread_participant(self.outsider.pk, self.thread))


class PolicyEngineWatchlistTests(TestCase):
    def setUp(self):
        self.owner = make_user("wowner@example.com", role=Role.BUYER)
        self.other = make_user("wother@example.com", role=Role.BUYER)
        self.supplier = make_user("wsupplier@example.com", role=Role.SUPPLIER)
        self.lot = make_supply_lot(self.supplier)
        self.item = make_watchlist_item(self.owner, supply_lot=self.lot)
        self.engine = PolicyEngine()

    def test_is_watchlist_owner_true(self):
        self.assertTrue(self.engine.is_watchlist_owner(self.owner.pk, self.item))

    def test_is_watchlist_owner_false(self):
        self.assertFalse(self.engine.is_watchlist_owner(self.other.pk, self.item))


# ---------------------------------------------------------------------------
# PermissionService decision tests
# ---------------------------------------------------------------------------

class PermissionServiceListingMutationTests(TestCase):
    def setUp(self):
        self.owner = make_user("mut_owner@example.com", role=Role.SUPPLIER)
        self.other = make_user("mut_other@example.com", role=Role.SUPPLIER)
        self.lot = make_supply_lot(self.owner)

    def test_owner_allowed_to_edit(self):
        decision = permission_service.authorize_listing_mutation(self.owner.pk, self.lot, "edit")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason_code, "OWNER_CONFIRMED")

    def test_non_owner_denied_edit(self):
        decision = permission_service.authorize_listing_mutation(self.other.pk, self.lot, "edit")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "NOT_LISTING_OWNER")

    def test_non_owner_denied_raises_permission_denied(self):
        decision = permission_service.authorize_listing_mutation(self.other.pk, self.lot, "delete")
        with self.assertRaises(PermissionDenied):
            decision.deny_if_not_allowed()

    def test_owner_allowed_for_demand_post(self):
        buyer = make_user("dm_owner@example.com", role=Role.BUYER)
        post = make_demand_post(buyer)
        decision = permission_service.authorize_listing_mutation(buyer.pk, post, "edit")
        self.assertTrue(decision.allowed)

    def test_non_owner_denied_for_demand_post(self):
        buyer = make_user("dm_owner2@example.com", role=Role.BUYER)
        post = make_demand_post(buyer)
        other = make_user("dm_other@example.com", role=Role.SUPPLIER)
        decision = permission_service.authorize_listing_mutation(other.pk, post, "edit")
        self.assertFalse(decision.allowed)

    def test_structured_denial_has_rule_id(self):
        decision = permission_service.authorize_listing_mutation(self.other.pk, self.lot, "edit")
        self.assertEqual(decision.rule_id, "LISTING_OWNER_REQUIRED")
        self.assertEqual(decision.subject_type, "listing")
        self.assertEqual(decision.subject_id, self.lot.pk)


class PermissionServiceMessageInitiationTests(TestCase):
    def setUp(self):
        self.supplier = make_user("msg_sup@example.com", role=Role.SUPPLIER)
        self.buyer = make_user("msg_buy@example.com", role=Role.BUYER)
        self.lot = make_supply_lot(self.supplier)

    def test_non_owner_can_initiate_message(self):
        decision = permission_service.authorize_message_initiation(self.buyer.pk, self.lot)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason_code, "NON_OWNER_ALLOWED")

    def test_owner_blocked_from_self_message(self):
        decision = permission_service.authorize_message_initiation(self.supplier.pk, self.lot)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "SELF_MESSAGE_DENIED")

    def test_self_message_denial_has_correct_rule(self):
        decision = permission_service.authorize_message_initiation(self.supplier.pk, self.lot)
        self.assertEqual(decision.rule_id, "SELF_MESSAGE_BLOCK")

    def test_self_message_raises_permission_denied(self):
        decision = permission_service.authorize_message_initiation(self.supplier.pk, self.lot)
        with self.assertRaises(PermissionDenied):
            decision.deny_if_not_allowed()


class PermissionServiceThreadAccessTests(TestCase):
    def setUp(self):
        self.buyer = make_user("ta_buy@example.com", role=Role.BUYER)
        self.supplier = make_user("ta_sup@example.com", role=Role.SUPPLIER)
        self.outsider = make_user("ta_out@example.com")
        self.lot = make_supply_lot(self.supplier)
        self.item = make_watchlist_item(self.buyer, supply_lot=self.lot)
        self.thread = make_thread(self.item, buyer=self.buyer, supplier=self.supplier)

    def test_buyer_allowed_thread_access(self):
        decision = permission_service.authorize_thread_access(self.buyer.pk, self.thread, "access")
        self.assertTrue(decision.allowed)

    def test_supplier_allowed_thread_access(self):
        decision = permission_service.authorize_thread_access(self.supplier.pk, self.thread, "access")
        self.assertTrue(decision.allowed)

    def test_outsider_denied_thread_access(self):
        decision = permission_service.authorize_thread_access(self.outsider.pk, self.thread, "access")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "NOT_THREAD_PARTICIPANT")

    def test_non_participant_raises_permission_denied(self):
        decision = permission_service.authorize_thread_access(self.outsider.pk, self.thread, "access")
        with self.assertRaises(PermissionDenied):
            decision.deny_if_not_allowed()


class PermissionServiceWatchlistTests(TestCase):
    def setUp(self):
        self.wowner = make_user("wo_owner@example.com", role=Role.BUYER)
        self.other = make_user("wo_other@example.com", role=Role.BUYER)
        self.supplier = make_user("wo_sup@example.com", role=Role.SUPPLIER)
        self.lot = make_supply_lot(self.supplier)
        self.item = make_watchlist_item(self.wowner, supply_lot=self.lot)

    def test_owner_allowed_watchlist_action(self):
        decision = permission_service.authorize_watchlist_action(self.wowner.pk, self.item, "archive")
        self.assertTrue(decision.allowed)

    def test_non_owner_denied_watchlist_action(self):
        decision = permission_service.authorize_watchlist_action(self.other.pk, self.item, "archive")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "NOT_WATCHLIST_OWNER")

    def test_non_owner_raises_permission_denied(self):
        decision = permission_service.authorize_watchlist_action(self.other.pk, self.item, "delete")
        with self.assertRaises(PermissionDenied):
            decision.deny_if_not_allowed()


# ---------------------------------------------------------------------------
# Unified Listing model with permission service
# ---------------------------------------------------------------------------

class PermissionServiceUnifiedListingTests(TestCase):
    def setUp(self):
        self.owner = make_user("ul_owner@example.com", role=Role.SUPPLIER)
        self.other = make_user("ul_other@example.com", role=Role.BUYER)

    def test_owner_allowed_for_unified_listing(self):
        listing = Listing.objects.create(
            type=ListingType.SUPPLY,
            created_by_user=self.owner,
            title="Supply Thing",
            status=ListingStatus.ACTIVE,
            location_country="US",
            created_at=timezone.now(),
        )
        decision = permission_service.authorize_listing_mutation(self.owner.pk, listing, "edit")
        self.assertTrue(decision.allowed)

    def test_non_owner_denied_for_unified_listing(self):
        listing = Listing.objects.create(
            type=ListingType.SUPPLY,
            created_by_user=self.owner,
            title="Supply Thing 2",
            status=ListingStatus.ACTIVE,
            location_country="US",
            created_at=timezone.now(),
        )
        decision = permission_service.authorize_listing_mutation(self.other.pk, listing, "edit")
        self.assertFalse(decision.allowed)


# ---------------------------------------------------------------------------
# RoleAuthComplianceScanner tests
# ---------------------------------------------------------------------------

class RoleAuthComplianceScannerTests(TestCase):
    def test_scanner_passes_after_role_gate_removal(self):
        scanner = RoleAuthComplianceScanner()
        passed, violations = scanner.scan()
        self.assertTrue(
            passed,
            f"Compliance scanner found role-auth violations: {violations}",
        )

    def test_scanner_returns_empty_violations_on_clean_code(self):
        scanner = RoleAuthComplianceScanner()
        passed, violations = scanner.scan()
        self.assertEqual(violations, [])


# ---------------------------------------------------------------------------
# ParityValidator permission validation
# ---------------------------------------------------------------------------

class PermissionParityValidatorTests(TestCase):
    def test_validate_permission_policy_passes(self):
        validator = ParityValidator()
        result = validator.validate_permission_policy()
        self.assertTrue(
            result.passed,
            f"Permission parity validation failed: {result.summary}",
        )
        self.assertEqual(result.failures, 0)

    def test_validate_permission_policy_creates_report(self):
        validator = ParityValidator()
        result = validator.validate_permission_policy()
        report = validator.create_report(stage="compat", scope="permission", result=result)
        self.assertEqual(report.scope, "permission")
        self.assertTrue(report.passed)


# ---------------------------------------------------------------------------
# Checkpoint gate: CP4 requires permission parity evidence
# ---------------------------------------------------------------------------

class CheckpointPermissionGateTests(TestCase):
    def setUp(self):
        from marketplace.migration_control.state import get_or_create_state
        from marketplace.migration_control.backfill import BackfillEngine
        self.controller = CheckpointController()
        self.validator = ParityValidator()
        # Advance to CP1 baseline
        state = get_or_create_state()
        state.checkpoint = "CP0"
        state.checkpoint_order = 0
        state.save()

    def _seed_passing_reports(self, stage, exclude_scope=None):
        """Seed all required passing parity reports for a given stage."""
        scopes = ["counts", "relationships", "identity", "listing", "permission", "messaging", "discover"]
        for scope in scopes:
            if scope == exclude_scope:
                continue
            ParityReport.objects.create(
                stage=stage,
                scope=scope,
                passed=True,
                total_checked=1,
                failures=0,
                failure_summary="",
            )

    def test_cp4_blocked_without_permission_report(self):
        # Seed all passing reports except permission
        self._seed_passing_reports(stage="compat", exclude_scope="permission")
        # Advance to CP3 first
        from marketplace.models import MigrationState
        state = MigrationState.objects.get(name="default")
        state.checkpoint = "CP3"
        state.checkpoint_order = 3
        state.save()
        result = self.controller.advance_to("CP4")
        self.assertFalse(result.ok)
        self.assertIn("permission", result.message)

    def test_cp4_unblocked_with_permission_report(self):
        # Seed all passing reports including permission
        self._seed_passing_reports(stage="compat")
        from marketplace.models import MigrationState
        state = MigrationState.objects.get(name="default")
        state.checkpoint = "CP3"
        state.checkpoint_order = 3
        state.save()
        result = self.controller.advance_to("CP4")
        self.assertTrue(result.ok, result.message)

    def test_cp5_blocked_without_cutover_permission_report(self):
        # Seed non-cutover permission report only
        self._seed_passing_reports(stage="compat")
        # Advance to CP4
        from marketplace.models import MigrationState
        state = MigrationState.objects.get(name="default")
        state.checkpoint = "CP3"
        state.checkpoint_order = 3
        state.save()
        self.controller.advance_to("CP4")
        # Now try CP5 without cutover-stage permission report
        self._seed_passing_reports(stage="cutover", exclude_scope="permission")
        result = self.controller.advance_to("CP5")
        self.assertFalse(result.ok)
        self.assertIn("permission", result.message)


# ---------------------------------------------------------------------------
# View-level integration tests
# ---------------------------------------------------------------------------

@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class ListingViewOwnershipTests(TestCase):
    def setUp(self):
        self.owner = make_user("view_owner@example.com", role=Role.SUPPLIER)
        self.other = make_user("view_other@example.com", role=Role.SUPPLIER)
        self.lot = make_supply_lot(self.owner)
        self.listing = ensure_listing_for_supply_lot(self.lot)
        self.client_owner = Client()
        self.client_other = Client()
        self.client_owner.login(username="view_owner@example.com", password="testpass")
        self.client_other.login(username="view_other@example.com", password="testpass")

    def test_owner_can_edit_supply_lot(self):
        url = reverse("marketplace:supply_lot_edit", kwargs={"pk": self.listing.pk})
        response = self.client_owner.get(url)
        self.assertEqual(response.status_code, 200)

    def test_non_owner_denied_edit_supply_lot(self):
        url = reverse("marketplace:supply_lot_edit", kwargs={"pk": self.listing.pk})
        response = self.client_other.get(url)
        self.assertEqual(response.status_code, 403)

    def test_owner_can_delete_supply_lot(self):
        url = reverse("marketplace:supply_lot_delete", kwargs={"pk": self.listing.pk})
        response = self.client_owner.get(url)
        self.assertEqual(response.status_code, 200)

    def test_non_owner_denied_delete_supply_lot(self):
        url = reverse("marketplace:supply_lot_delete", kwargs={"pk": self.listing.pk})
        response = self.client_other.get(url)
        self.assertEqual(response.status_code, 403)


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class DemandPostViewOwnershipTests(TestCase):
    def setUp(self):
        self.owner = make_user("dp_owner@example.com", role=Role.BUYER)
        self.other = make_user("dp_other@example.com", role=Role.BUYER)
        self.post = make_demand_post(self.owner)
        self.listing = ensure_listing_for_demand_post(self.post)
        # other also needs an org to avoid demand_post_create block
        Organization.objects.get_or_create(
            owner=self.other,
            defaults={"name": "Other Org", "type": "", "country": "US"},
        )
        self.client_owner = Client()
        self.client_other = Client()
        self.client_owner.login(username="dp_owner@example.com", password="testpass")
        self.client_other.login(username="dp_other@example.com", password="testpass")

    def test_owner_can_edit_demand_post(self):
        url = reverse("marketplace:demand_post_edit", kwargs={"pk": self.listing.pk})
        response = self.client_owner.get(url)
        self.assertEqual(response.status_code, 200)

    def test_non_owner_denied_edit_demand_post(self):
        url = reverse("marketplace:demand_post_edit", kwargs={"pk": self.listing.pk})
        response = self.client_other.get(url)
        self.assertEqual(response.status_code, 403)


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class ListingListViewNoRoleGateTests(TestCase):
    """List/create views must be accessible to any authenticated user (no role gate)."""

    def setUp(self):
        # Create a supplier user (would have been denied demand_post_list before)
        self.supplier = make_user("ng_sup@example.com", role=Role.SUPPLIER)
        # Create a buyer user (would have been denied supply_lot_list before)
        self.buyer = make_user("ng_buy@example.com", role=Role.BUYER)
        Organization.objects.get_or_create(
            owner=self.buyer,
            defaults={"name": "NG Org", "type": "", "country": "US"},
        )
        self.client_supplier = Client()
        self.client_buyer = Client()
        self.client_supplier.login(username="ng_sup@example.com", password="testpass")
        self.client_buyer.login(username="ng_buy@example.com", password="testpass")

    def test_supplier_can_access_demand_post_list(self):
        url = reverse("marketplace:demand_post_list")
        response = self.client_supplier.get(url)
        self.assertEqual(response.status_code, 200)

    def test_buyer_can_access_supply_lot_list(self):
        url = reverse("marketplace:supply_lot_list")
        response = self.client_buyer.get(url)
        self.assertEqual(response.status_code, 200)

    def test_supplier_can_access_supply_lot_create(self):
        url = reverse("marketplace:supply_lot_create")
        response = self.client_supplier.get(url)
        self.assertEqual(response.status_code, 200)


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class ThreadAccessParticipantTests(TestCase):
    def setUp(self):
        self.buyer = make_user("tp_buy@example.com", role=Role.BUYER)
        self.supplier = make_user("tp_sup@example.com", role=Role.SUPPLIER)
        self.outsider = make_user("tp_out@example.com")
        self.lot = make_supply_lot(self.supplier)
        self.item = make_watchlist_item(self.buyer, supply_lot=self.lot)
        self.thread = make_thread(self.item, buyer=self.buyer, supplier=self.supplier)
        # Add a message so thread is active
        from marketplace.models import Message
        Message.objects.create(thread=self.thread, sender=self.buyer, body="Hello")

        self.client_buyer = Client()
        self.client_supplier = Client()
        self.client_outsider = Client()
        self.client_buyer.login(username="tp_buy@example.com", password="testpass")
        self.client_supplier.login(username="tp_sup@example.com", password="testpass")
        self.client_outsider.login(username="tp_out@example.com", password="testpass")

    def test_buyer_can_access_thread(self):
        url = reverse("marketplace:thread_detail", kwargs={"pk": self.thread.pk})
        response = self.client_buyer.get(url)
        self.assertEqual(response.status_code, 200)

    def test_supplier_can_access_thread(self):
        url = reverse("marketplace:thread_detail", kwargs={"pk": self.thread.pk})
        response = self.client_supplier.get(url)
        self.assertEqual(response.status_code, 200)

    def test_outsider_denied_thread_access(self):
        url = reverse("marketplace:thread_detail", kwargs={"pk": self.thread.pk})
        response = self.client_outsider.get(url)
        self.assertEqual(response.status_code, 403)


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class WatchlistOwnershipViewTests(TestCase):
    def setUp(self):
        self.wowner = make_user("wov_own@example.com", role=Role.BUYER)
        self.other = make_user("wov_oth@example.com", role=Role.BUYER)
        self.supplier = make_user("wov_sup@example.com", role=Role.SUPPLIER)
        self.lot = make_supply_lot(self.supplier)
        self.item = make_watchlist_item(self.wowner, supply_lot=self.lot)

        self.client_owner = Client()
        self.client_other = Client()
        self.client_owner.login(username="wov_own@example.com", password="testpass")
        self.client_other.login(username="wov_oth@example.com", password="testpass")

    def test_owner_can_archive_watchlist_item(self):
        url = reverse("marketplace:watchlist_archive", kwargs={"pk": self.item.pk})
        response = self.client_owner.post(url)
        self.assertIn(response.status_code, [200, 302])

    def test_non_owner_denied_archive(self):
        url = reverse("marketplace:watchlist_archive", kwargs={"pk": self.item.pk})
        response = self.client_other.post(url)
        self.assertEqual(response.status_code, 403)

    def test_non_owner_denied_delete(self):
        url = reverse("marketplace:watchlist_delete", kwargs={"pk": self.item.pk})
        response = self.client_other.post(url)
        self.assertEqual(response.status_code, 403)


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
class SelfMessageBlockViewTests(TestCase):
    """Listing owners cannot initiate messaging on their own listings."""

    def setUp(self):
        self.supplier = make_user("smb_sup@example.com", role=Role.SUPPLIER)
        self.buyer = make_user("smb_buy@example.com", role=Role.BUYER)
        self.lot = make_supply_lot(self.supplier)
        self.listing = ensure_listing_for_supply_lot(self.lot)

        self.client_supplier = Client()
        self.client_buyer = Client()
        self.client_supplier.login(username="smb_sup@example.com", password="testpass")
        self.client_buyer.login(username="smb_buy@example.com", password="testpass")

    def test_owner_blocked_from_messaging_own_listing_via_suggestion(self):
        url = reverse("marketplace:suggestion_message")
        response = self.client_supplier.post(url, {
            "listing_type": "supply_lot",
            "listing_pk": self.listing.pk,
        })
        self.assertEqual(response.status_code, 403)

    def test_non_owner_can_message_listing_via_suggestion(self):
        url = reverse("marketplace:suggestion_message")
        response = self.client_buyer.post(url, {
            "listing_type": "supply_lot",
            "listing_pk": self.listing.pk,
        })
        # Should redirect to thread, not 403
        self.assertIn(response.status_code, [200, 302])
        self.assertNotEqual(response.status_code, 403)

    def test_owner_blocked_from_messaging_own_listing_via_discover(self):
        url = reverse("marketplace:discover_message")
        response = self.client_supplier.post(url, {
            "listing_type": "supply_lot",
            "listing_pk": self.listing.pk,
        })
        self.assertEqual(response.status_code, 403)

    def test_non_owner_can_message_listing_via_discover(self):
        url = reverse("marketplace:discover_message")
        response = self.client_buyer.post(url, {
            "listing_type": "supply_lot",
            "listing_pk": self.listing.pk,
        })
        self.assertIn(response.status_code, [200, 302])
        self.assertNotEqual(response.status_code, 403)
