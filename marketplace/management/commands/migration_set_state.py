from django.core.management.base import BaseCommand, CommandError

from marketplace.models import CanonicalSource, MigrationMode, MigrationStage
from marketplace.migration_control.state import set_state


class Command(BaseCommand):
    help = "Set migration control state values"

    def add_arguments(self, parser):
        parser.add_argument("--name", default="default")
        parser.add_argument("--mode", choices=[c for c, _ in MigrationMode.choices])
        parser.add_argument("--stage", choices=[c for c, _ in MigrationStage.choices])
        parser.add_argument("--checkpoint")
        parser.add_argument("--dual-write", choices=["true", "false"])
        parser.add_argument("--dual-read", choices=["true", "false"])
        parser.add_argument("--read-canonical", choices=[c for c, _ in CanonicalSource.choices])
        parser.add_argument("--write-canonical", choices=[c for c, _ in CanonicalSource.choices])

    def handle(self, *args, **options):
        try:
            state = set_state(
                name=options["name"],
                mode=options.get("mode"),
                stage=options.get("stage"),
                checkpoint=options.get("checkpoint"),
                dual_write_enabled=(options["dual_write"] == "true") if options.get("dual_write") else None,
                dual_read_enabled=(options["dual_read"] == "true") if options.get("dual_read") else None,
                read_canonical=options.get("read_canonical"),
                write_canonical=options.get("write_canonical"),
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated state {state.name}: mode={state.mode} stage={state.stage} checkpoint={state.checkpoint}"
            )
        )
