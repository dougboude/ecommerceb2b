from django.core.management.base import BaseCommand, CommandError

from marketplace.migration_control.checkpoints import CheckpointController


class Command(BaseCommand):
    help = "Advance or rollback migration checkpoint state"

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["advance", "rollback"])
        parser.add_argument("checkpoint")

    def handle(self, *args, **options):
        controller = CheckpointController()
        if options["action"] == "advance":
            result = controller.advance_to(options["checkpoint"])
        else:
            result = controller.rollback_to(options["checkpoint"])

        if not result.ok:
            raise CommandError(result.message)
        self.stdout.write(self.style.SUCCESS(f"{options['action']} -> {result.checkpoint}"))
