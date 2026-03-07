from dataclasses import dataclass

from django.db import transaction

from marketplace.migration_control.config import get_runtime_mode
from marketplace.models import (
    BackfillAuditRecord,
    BackfillAuditStatus,
    LegacyToTargetMapping,
    User,
)


@dataclass
class IdentityProfile:
    user_id: int
    email: str
    display_name: str
    organization_name: str | None


class IdentityCompatibilityAdapter:
    def get_profile(self, user: User) -> IdentityProfile:
        return IdentityProfile(
            user_id=user.pk,
            email=user.email,
            display_name=user.display_name,
            organization_name=self.get_organization_name(user),
        )

    def get_organization_name(self, user: User) -> str | None:
        return self._normalize_name(user.organization_name)

    @transaction.atomic
    def update_identity(self, user: User, *, organization_name: str | None = None) -> User:
        normalized_org_name = self._normalize_name(organization_name)
        user.organization_name = normalized_org_name
        user.save(update_fields=["organization_name"])

        return user

    @transaction.atomic
    def backfill_org_names(self) -> tuple[int, int, int]:
        processed = 0
        success = 0
        failed = 0

        for user in User.objects.all().order_by("pk"):
            processed += 1
            existing = self._normalize_name(user.organization_name)
            resolved = existing
            reason = "identity_org_kept_existing" if existing else "identity_org_empty"

            user.organization_name = resolved
            user.save(update_fields=["organization_name"])

            BackfillAuditRecord.objects.create(
                entity_type="user",
                source_pk=user.pk,
                target_pk=user.pk,
                status=BackfillAuditStatus.SUCCESS,
                reason_code=reason,
                details={"resolved": resolved},
            )
            LegacyToTargetMapping.objects.update_or_create(
                entity_type="user",
                legacy_pk=user.pk,
                defaults={"target_pk": user.pk, "mapping_version": 2},
            )
            success += 1

        return processed, success, failed

    @staticmethod
    def _normalize_name(name: str | None) -> str | None:
        if name is None:
            return None
        value = name.strip()
        return value or None


class IdentityComplianceScanner:
    """
    Scope-limited scanner for identity/auth/profile paths.
    This does not block role-based listing/discovery behavior from other specs.
    """

    def scan(self) -> tuple[bool, list[str]]:
        violations: list[str] = []

        # In target mode, signup/profile forms should not expose role semantics.
        from marketplace.forms import SignupForm

        form = SignupForm()
        if get_runtime_mode() == "target" and "role" in form.fields:
            violations.append("SignupForm exposes role field in target mode")

        return (len(violations) == 0, violations)
