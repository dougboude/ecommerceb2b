from django.core.management.base import BaseCommand, CommandError

from marketplace.migration_control.parity import ParityValidator
from marketplace.migration_control.state import get_or_create_state


class Command(BaseCommand):
    help = "Validate migration parity gates and write report evidence"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scope",
            choices=[
                "counts",
                "relationships",
                "identity",
                "listing",
                "permission",
                "messaging",
                "discover",
                "cleanup_listing",
                "cleanup_messaging",
                "cleanup_role_org",
                "ui",
                "all",
            ],
            default="all",
        )
        parser.add_argument("--fail-on-error", action="store_true")

    def handle(self, *args, **options):
        state = get_or_create_state()
        validator = ParityValidator()
        failures = 0

        if options["scope"] in {"counts", "all"}:
            result = validator.validate_counts()
            validator.create_report(stage=state.stage, scope="counts", result=result)
            self.stdout.write(f"counts: passed={result.passed} failures={result.failures} summary={result.summary}")
            failures += result.failures

        if options["scope"] in {"relationships", "all"}:
            result = validator.validate_relationships()
            validator.create_report(stage=state.stage, scope="relationships", result=result)
            self.stdout.write(
                f"relationships: passed={result.passed} failures={result.failures} summary={result.summary}"
            )
            failures += result.failures

        if options["scope"] in {"identity", "all"}:
            result = validator.validate_identity()
            validator.create_report(stage=state.stage, scope="identity", result=result)
            self.stdout.write(f"identity: passed={result.passed} failures={result.failures} summary={result.summary}")
            failures += result.failures

        if options["scope"] in {"listing", "all"}:
            result = validator.validate_listing_contract()
            validator.create_report(stage=state.stage, scope="listing", result=result)
            self.stdout.write(f"listing: passed={result.passed} failures={result.failures} summary={result.summary}")
            failures += result.failures

        if options["scope"] in {"permission", "all"}:
            result = validator.validate_permission_policy()
            validator.create_report(stage=state.stage, scope="permission", result=result)
            self.stdout.write(
                f"permission: passed={result.passed} failures={result.failures} summary={result.summary}"
            )
            failures += result.failures

        if options["scope"] in {"messaging", "all"}:
            result = validator.validate_messaging_contract()
            validator.create_report(stage=state.stage, scope="messaging", result=result)
            self.stdout.write(f"messaging: passed={result.passed} failures={result.failures} summary={result.summary}")
            failures += result.failures

        if options["scope"] in {"discover", "all"}:
            result = validator.validate_discover_contract()
            validator.create_report(stage=state.stage, scope="discover", result=result)
            self.stdout.write(f"discover: passed={result.passed} failures={result.failures} summary={result.summary}")
            failures += result.failures

        if options["scope"] in {"cleanup_listing"}:
            result = validator.validate_cleanup_listing_dependencies()
            validator.create_report(stage=state.stage, scope="cleanup_listing", result=result)
            self.stdout.write(
                f"cleanup_listing: passed={result.passed} failures={result.failures} summary={result.summary}"
            )
            failures += result.failures

        if options["scope"] in {"cleanup_messaging"}:
            result = validator.validate_cleanup_messaging_dependencies()
            validator.create_report(stage=state.stage, scope="cleanup_messaging", result=result)
            self.stdout.write(
                f"cleanup_messaging: passed={result.passed} failures={result.failures} summary={result.summary}"
            )
            failures += result.failures

        if options["scope"] in {"cleanup_role_org"}:
            result = validator.validate_cleanup_role_org_dependencies()
            validator.create_report(stage=state.stage, scope="cleanup_role_org", result=result)
            self.stdout.write(
                f"cleanup_role_org: passed={result.passed} failures={result.failures} summary={result.summary}"
            )
            failures += result.failures

        if options["scope"] in {"ui", "all"}:
            result = validator.validate_ui_language()
            validator.create_report(stage=state.stage, scope="ui", result=result)
            self.stdout.write(f"ui: passed={result.passed} failures={result.failures} summary={result.summary}")
            failures += result.failures

        if options["fail_on_error"] and failures > 0:
            raise CommandError("Migration validation failed")
