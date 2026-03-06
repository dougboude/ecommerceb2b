from django.conf import settings

from marketplace.models import MigrationMode


def get_runtime_mode() -> str:
    mode = getattr(settings, "MIGRATION_CONTROL_MODE", MigrationMode.LEGACY)
    if mode not in {MigrationMode.LEGACY, MigrationMode.COMPATIBILITY, MigrationMode.TARGET}:
        return MigrationMode.LEGACY
    return mode


def dual_write_enabled() -> bool:
    return bool(getattr(settings, "MIGRATION_DUAL_WRITE_ENABLED", False))


def dual_read_enabled() -> bool:
    return bool(getattr(settings, "MIGRATION_DUAL_READ_ENABLED", False))


def write_canonical() -> str:
    source = getattr(settings, "MIGRATION_WRITE_CANONICAL", "legacy")
    return source if source in {"legacy", "target"} else "legacy"


def read_canonical() -> str:
    source = getattr(settings, "MIGRATION_READ_CANONICAL", "legacy")
    return source if source in {"legacy", "target"} else "legacy"
