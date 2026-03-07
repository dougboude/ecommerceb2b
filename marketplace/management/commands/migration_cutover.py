from django.core.management.base import BaseCommand, CommandError

from marketplace.migration_control.backfill import BackfillEngine
from marketplace.migration_control.checkpoints import CheckpointController
from marketplace.migration_control.parity import ParityValidator
from marketplace.migration_control.state import get_or_create_state


class Command(BaseCommand):
    help = "Execute staged migration cutover progression with validation gates"

    def add_arguments(self, parser):
        parser.add_argument("--to", default="CP4", choices=["CP1", "CP2", "CP3", "CP4", "CP5"])

    def handle(self, *args, **options):
        target = options["to"]
        controller = CheckpointController()
        validator = ParityValidator()
        backfill = BackfillEngine()

        state = get_or_create_state()
        order = ["CP1", "CP2", "CP3", "CP4", "CP5"]
        to_index = order.index(target)

        for checkpoint in order[: to_index + 1]:
            if state.checkpoint == checkpoint:
                continue

            if checkpoint == "CP2":
                backfill.backfill_users()
                backfill.backfill_listings()
                backfill.backfill_threads_and_watchlist()
                r = validator.validate_relationships()
                validator.create_report(stage=state.stage, scope="relationships", result=r)

            if checkpoint == "CP4":
                r_counts = validator.validate_counts()
                r_rels = validator.validate_relationships()
                r_identity = validator.validate_identity()
                r_listing = validator.validate_listing_contract()
                r_permission = validator.validate_permission_policy()
                validator.create_report(stage=state.stage, scope="counts", result=r_counts)
                validator.create_report(stage=state.stage, scope="relationships", result=r_rels)
                validator.create_report(stage=state.stage, scope="identity", result=r_identity)
                validator.create_report(stage=state.stage, scope="listing", result=r_listing)
                validator.create_report(stage=state.stage, scope="permission", result=r_permission)

            if checkpoint == "CP5":
                # Emit explicit cutover-stage evidence before cleanup.
                pre = get_or_create_state()
                pre.stage = "cutover"
                pre.save(update_fields=["stage"])
                r_counts = validator.validate_counts()
                r_rels = validator.validate_relationships()
                r_identity = validator.validate_identity()
                r_listing = validator.validate_listing_contract()
                r_permission = validator.validate_permission_policy()
                validator.create_report(stage="cutover", scope="counts", result=r_counts)
                validator.create_report(stage="cutover", scope="relationships", result=r_rels)
                validator.create_report(stage="cutover", scope="identity", result=r_identity)
                validator.create_report(stage="cutover", scope="listing", result=r_listing)
                validator.create_report(stage="cutover", scope="permission", result=r_permission)

            result = controller.advance_to(checkpoint)
            if not result.ok:
                raise CommandError(result.message)
            self.stdout.write(self.style.SUCCESS(f"Advanced to {checkpoint}"))
            state = get_or_create_state()

        self.stdout.write(self.style.SUCCESS(f"Migration cutover progression complete at {state.checkpoint}"))
