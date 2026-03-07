from django.core.management import call_command
from django.test import TestCase

from marketplace.migration_control.parity import ParityValidator


class CleanupComplianceValidationTests(TestCase):
    def test_cleanup_listing_scope_runs(self):
        call_command("migration_validate", "--scope", "cleanup_listing")

    def test_cleanup_messaging_scope_runs(self):
        call_command("migration_validate", "--scope", "cleanup_messaging")

    def test_cleanup_role_org_scope_runs(self):
        call_command("migration_validate", "--scope", "cleanup_role_org")

    def test_cleanup_validator_methods_return_result_objects(self):
        validator = ParityValidator()
        listing = validator.validate_cleanup_listing_dependencies()
        messaging = validator.validate_cleanup_messaging_dependencies()
        role_org = validator.validate_cleanup_role_org_dependencies()

        self.assertIsInstance(listing.passed, bool)
        self.assertIsInstance(messaging.passed, bool)
        self.assertIsInstance(role_org.passed, bool)
