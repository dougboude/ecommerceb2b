from django.core.management.base import BaseCommand, CommandError

from marketplace.migration_control.checkpoints import CheckpointController
from marketplace.migration_control.parity import ParityValidator
from marketplace.migration_control.state import CHECKPOINT_ORDER, get_or_create_state


class Command(BaseCommand):
    help = "Execute staged migration cutover progression with validation gates"

    def add_arguments(self, parser):
        parser.add_argument("--to", default="CP4", choices=["CP1", "CP2", "CP3", "CP4", "CP5"])

    def handle(self, *args, **options):
        target = options["to"]
        controller = CheckpointController()
        validator = ParityValidator()

        state = get_or_create_state()
        order = ["CP1", "CP2", "CP3", "CP4", "CP5"]
        to_index = order.index(target)

        for checkpoint in order[: to_index + 1]:
            # Skip already-reached checkpoints.
            if state.checkpoint == checkpoint:
                continue
            if state.checkpoint_order >= CHECKPOINT_ORDER[checkpoint]:
                continue

            if checkpoint == "CP2":
                r = validator.validate_relationships()
                validator.create_report(stage=state.stage, scope="relationships", result=r)

            if checkpoint == "CP4":
                r_counts = validator.validate_counts()
                r_rels = validator.validate_relationships()
                r_identity = validator.validate_identity()
                r_listing = validator.validate_listing_contract()
                r_permission = validator.validate_permission_policy()
                r_messaging = validator.validate_messaging_contract()
                r_discover = validator.validate_discover_contract()
                validator.create_report(stage=state.stage, scope="counts", result=r_counts)
                validator.create_report(stage=state.stage, scope="relationships", result=r_rels)
                validator.create_report(stage=state.stage, scope="identity", result=r_identity)
                validator.create_report(stage=state.stage, scope="listing", result=r_listing)
                validator.create_report(stage=state.stage, scope="permission", result=r_permission)
                validator.create_report(stage=state.stage, scope="messaging", result=r_messaging)
                validator.create_report(stage=state.stage, scope="discover", result=r_discover)

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
                r_messaging = validator.validate_messaging_contract()
                r_discover = validator.validate_discover_contract()
                r_cleanup_listing = validator.validate_cleanup_listing_dependencies()
                r_cleanup_messaging = validator.validate_cleanup_messaging_dependencies()
                r_cleanup_role_org = validator.validate_cleanup_role_org_dependencies()
                validator.create_report(stage="cutover", scope="counts", result=r_counts)
                validator.create_report(stage="cutover", scope="relationships", result=r_rels)
                validator.create_report(stage="cutover", scope="identity", result=r_identity)
                validator.create_report(stage="cutover", scope="listing", result=r_listing)
                validator.create_report(stage="cutover", scope="permission", result=r_permission)
                validator.create_report(stage="cutover", scope="messaging", result=r_messaging)
                validator.create_report(stage="cutover", scope="discover", result=r_discover)
                validator.create_report(stage="cutover", scope="cleanup_listing", result=r_cleanup_listing)
                validator.create_report(stage="cutover", scope="cleanup_messaging", result=r_cleanup_messaging)
                validator.create_report(stage="cutover", scope="cleanup_role_org", result=r_cleanup_role_org)

            result = controller.advance_to(checkpoint)
            if not result.ok:
                raise CommandError(result.message)
            self.stdout.write(self.style.SUCCESS(f"Advanced to {checkpoint}"))
            state = get_or_create_state()

        self.stdout.write(self.style.SUCCESS(f"Migration cutover progression complete at {state.checkpoint}"))
