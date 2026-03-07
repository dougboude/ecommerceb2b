from django.core.management.base import BaseCommand, CommandError

from marketplace.migration_control.parity import ParityValidator
from marketplace.migration_control.state import get_or_create_state


class Command(BaseCommand):
    help = "Validate migration parity gates and write report evidence"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scope",
            choices=["counts", "relationships", "identity", "listing", "permission", "all"],
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

        if options["fail_on_error"] and failures > 0:
            raise CommandError("Migration validation failed")
