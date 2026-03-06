from django.db import transaction

from marketplace.models import (
    CanonicalSource,
    MigrationMode,
    MigrationStage,
    MigrationState,
)


CHECKPOINT_ORDER = {
    "CP0": 0,
    "CP1": 1,
    "CP2": 2,
    "CP3": 3,
    "CP4": 4,
    "CP5": 5,
}


@transaction.atomic
def get_or_create_state(name: str = "default") -> MigrationState:
    state, _ = MigrationState.objects.select_for_update().get_or_create(
        name=name,
        defaults={
            "mode": MigrationMode.LEGACY,
            "stage": MigrationStage.SCHEMA,
            "checkpoint": "CP0",
            "checkpoint_order": 0,
            "dual_write_enabled": False,
            "dual_read_enabled": False,
            "read_canonical": CanonicalSource.LEGACY,
            "write_canonical": CanonicalSource.LEGACY,
        },
    )
    return state


@transaction.atomic
def set_state(
    *,
    name: str = "default",
    mode: str | None = None,
    stage: str | None = None,
    checkpoint: str | None = None,
    dual_write_enabled: bool | None = None,
    dual_read_enabled: bool | None = None,
    read_canonical: str | None = None,
    write_canonical: str | None = None,
) -> MigrationState:
    state = get_or_create_state(name=name)

    if mode is not None:
        state.mode = mode
    if stage is not None:
        state.stage = stage
    if checkpoint is not None:
        if checkpoint not in CHECKPOINT_ORDER:
            raise ValueError(f"Unknown checkpoint: {checkpoint}")
        state.checkpoint = checkpoint
        state.checkpoint_order = CHECKPOINT_ORDER[checkpoint]
    if dual_write_enabled is not None:
        state.dual_write_enabled = dual_write_enabled
    if dual_read_enabled is not None:
        state.dual_read_enabled = dual_read_enabled
    if read_canonical is not None:
        state.read_canonical = read_canonical
    if write_canonical is not None:
        state.write_canonical = write_canonical

    state.save()
    return state
