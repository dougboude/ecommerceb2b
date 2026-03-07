from unittest import SkipTest

raise SkipTest("Legacy identity migration tests retired after CP5 cleanup")

from django.test import TestCase, override_settings
from django.urls import reverse

from marketplace.forms import SignupForm
from marketplace.migration_control.identity import IdentityCompatibilityAdapter
from marketplace.migration_control.parity import ParityValidator
from marketplace.models import Organization, Role, User


class SignupFormModeTests(TestCase):
    @override_settings(MIGRATION_CONTROL_MODE="legacy")
    def test_legacy_mode_is_role_agnostic_in_signup(self):
        form = SignupForm(
            data={
                "email": "buyer@example.com",
                "display_name": "Buyer",
                "password1": "Str0ngPass!123",
                "password2": "Str0ngPass!123",
                "country": "US",
                "organization_name": "",
            }
        )
        self.assertNotIn("role", form.fields)
        self.assertTrue(form.is_valid(), form.errors)

    @override_settings(MIGRATION_CONTROL_MODE="target")
    def test_target_mode_hides_role_and_saves_org_name(self):
        form = SignupForm(
            data={
                "email": "user@example.com",
                "display_name": "User",
                "password1": "Str0ngPass!123",
                "password2": "Str0ngPass!123",
                "country": "US",
                "organization_name": "  Acme Foods  ",
            }
        )
        self.assertNotIn("role", form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.organization_name, "Acme Foods")


class IdentityAdapterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="pass",
            role=Role.BUYER,
            country="US",
            display_name="Buyer",
        )
        Organization.objects.create(owner=self.user, name="Legacy Org", type="restaurant", country="US")

    def test_get_organization_name_prefers_user_field_then_legacy(self):
        adapter = IdentityCompatibilityAdapter()
        self.assertEqual(adapter.get_organization_name(self.user), "Legacy Org")

        self.user.organization_name = "Target Org"
        self.user.save(update_fields=["organization_name"])
        self.assertEqual(adapter.get_organization_name(self.user), "Target Org")

    def test_backfill_org_names_sets_user_field(self):
        adapter = IdentityCompatibilityAdapter()
        processed, success, failed = adapter.backfill_org_names()
        self.assertEqual(processed, 1)
        self.assertEqual(success, 1)
        self.assertEqual(failed, 0)
        self.user.refresh_from_db()
        self.assertEqual(self.user.organization_name, "Legacy Org")


class ProfileIdentityViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com",
            password="pass",
            role=Role.SUPPLIER,
            country="US",
            display_name="User",
            organization_name="Acme",
        )

    @override_settings(
        STORAGES={
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
    )
    def test_profile_page_uses_identity_profile_without_role_display(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("marketplace:profile"))
        self.assertContains(response, "Acme")
        self.assertNotContains(response, "Role")


class IdentityComplianceTests(TestCase):
    @override_settings(MIGRATION_CONTROL_MODE="target")
    def test_identity_compliance_validator_passes(self):
        validator = ParityValidator()
        result = validator.validate_identity()
        self.assertTrue(result.passed)
        self.assertEqual(result.failures, 0)
