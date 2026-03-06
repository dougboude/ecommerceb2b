from dataclasses import dataclass

from django.db import transaction

from marketplace.models import CanonicalSource, MigrationMode, MigrationStage
from marketplace.models import ParityReport

from .state import CHECKPOINT_ORDER, get_or_create_state


@dataclass
class CheckpointResult:
    ok: bool
    checkpoint: str
    message: str


class CheckpointController:
    def __init__(self, name: str = "default"):
        self.name = name

    @transaction.atomic
    def advance_to(self, checkpoint: str) -> CheckpointResult:
        state = get_or_create_state(name=self.name)
        if checkpoint not in CHECKPOINT_ORDER:
            return CheckpointResult(False, state.checkpoint, f"Unknown checkpoint {checkpoint}")

        target_order = CHECKPOINT_ORDER[checkpoint]
        if target_order <= state.checkpoint_order:
            return CheckpointResult(False, state.checkpoint, "Checkpoint must advance forward")

        gate_error = self._check_gates(state=state, target_checkpoint=checkpoint)
        if gate_error:
            return CheckpointResult(False, state.checkpoint, gate_error)

        state.checkpoint = checkpoint
        state.checkpoint_order = target_order

        # Minimal canonical transitions aligned to design stages.
        if checkpoint == "CP3":
            state.mode = MigrationMode.COMPATIBILITY
            state.stage = MigrationStage.COMPAT
            state.dual_write_enabled = True
            state.dual_read_enabled = True
            state.write_canonical = CanonicalSource.LEGACY
            state.read_canonical = CanonicalSource.LEGACY
        elif checkpoint == "CP4":
            state.mode = MigrationMode.TARGET
            state.stage = MigrationStage.CUTOVER
            state.dual_write_enabled = False
            state.dual_read_enabled = True
            state.write_canonical = CanonicalSource.TARGET
            state.read_canonical = CanonicalSource.TARGET
        elif checkpoint == "CP5":
            state.stage = MigrationStage.CLEANUP
            state.dual_read_enabled = False

        state.save()
        return CheckpointResult(True, checkpoint, "Checkpoint advanced")

    @transaction.atomic
    def rollback_to(self, checkpoint: str) -> CheckpointResult:
        state = get_or_create_state(name=self.name)
        if checkpoint not in CHECKPOINT_ORDER:
            return CheckpointResult(False, state.checkpoint, f"Unknown checkpoint {checkpoint}")

        target_order = CHECKPOINT_ORDER[checkpoint]
        if target_order > state.checkpoint_order:
            return CheckpointResult(False, state.checkpoint, "Rollback target must not be ahead")

        if state.checkpoint == "CP5":
            return CheckpointResult(False, state.checkpoint, "Rollback not allowed from cleanup checkpoint")

        state.checkpoint = checkpoint
        state.checkpoint_order = target_order
        if target_order <= CHECKPOINT_ORDER["CP3"]:
            state.mode = MigrationMode.COMPATIBILITY if target_order == 3 else MigrationMode.LEGACY
            state.stage = MigrationStage.COMPAT if target_order == 3 else MigrationStage.BACKFILL
            state.read_canonical = CanonicalSource.LEGACY
            state.write_canonical = CanonicalSource.LEGACY
            state.dual_write_enabled = target_order == 3
            state.dual_read_enabled = target_order == 3
        state.save()
        return CheckpointResult(True, checkpoint, "Rolled back")

    def _check_gates(self, *, state, target_checkpoint: str) -> str | None:
        """
        Enforce minimal gate evidence before advancing key checkpoints.
        """
        if target_checkpoint == "CP2":
            # Backfill completion requires relationship parity evidence.
            if not self._latest_report_passed(scope="relationships"):
                return "Cannot advance to CP2: missing passing relationships parity report"

        if target_checkpoint == "CP4":
            # Cutover requires both count + relationship parity reports.
            if not self._latest_report_passed(scope="counts"):
                return "Cannot advance to CP4: missing passing counts parity report"
            if not self._latest_report_passed(scope="relationships"):
                return "Cannot advance to CP4: missing passing relationships parity report"
            if not self._latest_report_passed(scope="identity"):
                return "Cannot advance to CP4: missing passing identity compliance report"
            if not self._latest_report_passed(scope="listing"):
                return "Cannot advance to CP4: missing passing listing contract report"

        if target_checkpoint == "CP5":
            # Cleanup requires cutover-stage passing reports.
            if state.checkpoint != "CP4":
                return "Cannot advance to CP5: must be at CP4 first"
            if not self._latest_report_passed(scope="counts", stage=MigrationStage.CUTOVER):
                return "Cannot advance to CP5: missing passing cutover counts report"
            if not self._latest_report_passed(scope="relationships", stage=MigrationStage.CUTOVER):
                return "Cannot advance to CP5: missing passing cutover relationships report"
            if not self._latest_report_passed(scope="identity", stage=MigrationStage.CUTOVER):
                return "Cannot advance to CP5: missing passing cutover identity report"
            if not self._latest_report_passed(scope="listing", stage=MigrationStage.CUTOVER):
                return "Cannot advance to CP5: missing passing cutover listing report"

        return None

    def _latest_report_passed(self, *, scope: str, stage: str | None = None) -> bool:
        qs = ParityReport.objects.filter(scope=scope).order_by("-generated_at")
        if stage:
            qs = qs.filter(stage=stage)
        report = qs.first()
        return bool(report and report.passed)
