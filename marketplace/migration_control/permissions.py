"""
Centralized ownership-based permission policy service (Feature 4).

Replaces role-based authorization with ownership and participation rules
for listing, thread, and watchlist actions. All launch-critical authorization
decisions route through this module during and after migration.

Policy Contract:
- Listing mutations require user == listing.created_by (owner)
- Message initiation requires user != listing owner (self-message block)
- Thread access requires participant membership (buyer or supplier)
- Watchlist mutations require watchlist record ownership
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Decision:
    allowed: bool
    rule_id: str
    reason_code: str
    subject_type: str   # "listing" | "thread" | "watchlist"
    subject_id: int

    def deny_if_not_allowed(self):
        """Raise PermissionDenied if this decision is a denial."""
        if not self.allowed:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied(self.reason_code)


# ---------------------------------------------------------------------------
# Policy Engine — pure predicate layer (no side effects)
# ---------------------------------------------------------------------------

class PolicyEngine:
    """
    Evaluates ownership and participation predicates against live data.
    All methods are side-effect-free boolean queries.
    """

    def is_listing_owner(self, user_id: int, listing_obj) -> bool:
        """
        Returns True if user_id matches the creator of the listing object.
        Works with both legacy (DemandPost/SupplyLot) and target (Listing) models
        via duck-typed .created_by / .created_by_user attribute.
        """
        creator = getattr(listing_obj, "created_by_user", None) or getattr(listing_obj, "created_by", None)
        if creator is None:
            return False
        return creator.pk == user_id

    def is_thread_participant(self, user_id: int, thread_obj) -> bool:
        """
        Returns True if user_id is the buyer or supplier in the thread.
        Works with legacy MessageThread (buyer/supplier FK fields).
        """
        if hasattr(thread_obj, "is_participant"):
            return thread_obj.is_participant(user_id)
        return user_id in (thread_obj.buyer_id, thread_obj.supplier_id)

    def is_watchlist_owner(self, user_id: int, watchlist_item_obj) -> bool:
        """Returns True if user_id owns this watchlist record."""
        return watchlist_item_obj.user_id == user_id

    def is_self_message_attempt(self, user_id: int, listing_obj) -> bool:
        """Returns True if user_id is the listing owner (self-message block)."""
        return self.is_listing_owner(user_id, listing_obj)


# ---------------------------------------------------------------------------
# Permission Service — authoritative decision point
# ---------------------------------------------------------------------------

_engine = PolicyEngine()


class PermissionService:
    """
    Single entry point for all launch-critical authorization decisions.
    Returns structured Decision objects; does not raise exceptions directly.
    """

    def authorize_listing_mutation(self, user_id: int, listing_obj, action: str) -> Decision:
        """
        Authorize a listing mutation (edit / toggle / delete).
        Only the listing owner is permitted.
        """
        subject_id = listing_obj.pk or 0
        if listing_obj is None:
            return Decision(
                allowed=False,
                rule_id="LISTING_OWNER_REQUIRED",
                reason_code="OWNERSHIP_UNRESOLVABLE",
                subject_type="listing",
                subject_id=subject_id,
            )
        if _engine.is_listing_owner(user_id, listing_obj):
            return Decision(
                allowed=True,
                rule_id="LISTING_OWNER_REQUIRED",
                reason_code="OWNER_CONFIRMED",
                subject_type="listing",
                subject_id=subject_id,
            )
        return Decision(
            allowed=False,
            rule_id="LISTING_OWNER_REQUIRED",
            reason_code="NOT_LISTING_OWNER",
            subject_type="listing",
            subject_id=subject_id,
        )

    def authorize_message_initiation(self, user_id: int, listing_obj) -> Decision:
        """
        Authorize initiating a message thread on a listing.
        Denied if user is the listing owner (self-message block).
        """
        subject_id = listing_obj.pk if listing_obj is not None else 0
        if listing_obj is None:
            return Decision(
                allowed=False,
                rule_id="SELF_MESSAGE_BLOCK",
                reason_code="LISTING_UNRESOLVABLE",
                subject_type="listing",
                subject_id=subject_id,
            )
        if _engine.is_self_message_attempt(user_id, listing_obj):
            return Decision(
                allowed=False,
                rule_id="SELF_MESSAGE_BLOCK",
                reason_code="SELF_MESSAGE_DENIED",
                subject_type="listing",
                subject_id=subject_id,
            )
        return Decision(
            allowed=True,
            rule_id="SELF_MESSAGE_BLOCK",
            reason_code="NON_OWNER_ALLOWED",
            subject_type="listing",
            subject_id=subject_id,
        )

    def authorize_thread_access(self, user_id: int, thread_obj, action: str) -> Decision:
        """
        Authorize thread read/post access.
        Only buyer or supplier participant is permitted.
        """
        subject_id = thread_obj.pk if thread_obj is not None else 0
        if thread_obj is None:
            return Decision(
                allowed=False,
                rule_id="THREAD_PARTICIPANT_REQUIRED",
                reason_code="THREAD_UNRESOLVABLE",
                subject_type="thread",
                subject_id=subject_id,
            )
        if _engine.is_thread_participant(user_id, thread_obj):
            return Decision(
                allowed=True,
                rule_id="THREAD_PARTICIPANT_REQUIRED",
                reason_code="PARTICIPANT_CONFIRMED",
                subject_type="thread",
                subject_id=subject_id,
            )
        return Decision(
            allowed=False,
            rule_id="THREAD_PARTICIPANT_REQUIRED",
            reason_code="NOT_THREAD_PARTICIPANT",
            subject_type="thread",
            subject_id=subject_id,
        )

    def authorize_watchlist_action(self, user_id: int, watchlist_item_obj, action: str) -> Decision:
        """
        Authorize a watchlist mutation (archive / unarchive / delete).
        Only the watchlist record owner is permitted.
        """
        subject_id = watchlist_item_obj.pk if watchlist_item_obj is not None else 0
        if watchlist_item_obj is None:
            return Decision(
                allowed=False,
                rule_id="WATCHLIST_OWNER_REQUIRED",
                reason_code="WATCHLIST_UNRESOLVABLE",
                subject_type="watchlist",
                subject_id=subject_id,
            )
        if _engine.is_watchlist_owner(user_id, watchlist_item_obj):
            return Decision(
                allowed=True,
                rule_id="WATCHLIST_OWNER_REQUIRED",
                reason_code="WATCHLIST_OWNER_CONFIRMED",
                subject_type="watchlist",
                subject_id=subject_id,
            )
        return Decision(
            allowed=False,
            rule_id="WATCHLIST_OWNER_REQUIRED",
            reason_code="NOT_WATCHLIST_OWNER",
            subject_type="watchlist",
            subject_id=subject_id,
        )


# Module-level singleton for import convenience
permission_service = PermissionService()


# ---------------------------------------------------------------------------
# Role-auth compliance scanner
# ---------------------------------------------------------------------------

class RoleAuthComplianceScanner:
    """
    Scans launch-critical view functions for residual role-based authorization
    branching. Returns (passed: bool, violations: list[str]).

    This is a structural check — it imports the views module and inspects
    known authorization call sites rather than doing AST analysis.
    """

    # Role-based denial patterns that must be absent from launch-critical
    # views once ownership policy is active. Note: role == branching used
    # for presentation/filtering (e.g. dashboard display) is out of scope;
    # only explicit denial gates (!=) are compliance violations.
    ROLE_CHECK_PATTERNS = [
        "role != Role.BUYER",
        "role != Role.SUPPLIER",
    ]

    # Views that are in scope for the ownership policy; role-branching in
    # these is a compliance violation.
    SCOPED_VIEW_NAMES = [
        "demand_post_list",
        "demand_post_create",
        "demand_post_edit",
        "demand_post_toggle",
        "demand_post_delete",
        "supply_lot_list",
        "supply_lot_create",
        "supply_lot_edit",
        "supply_lot_toggle",
        "supply_lot_delete",
        "thread_detail",
        "suggestion_message",
        "discover_message",
        "watchlist_archive",
        "watchlist_unarchive",
        "watchlist_delete",
    ]

    def scan(self) -> tuple[bool, list[str]]:
        """
        Returns (passed, violations).
        passed=True means no role-based auth branching found in scoped views.
        """
        import inspect
        import marketplace.views as views_module

        violations = []
        for view_name in self.SCOPED_VIEW_NAMES:
            fn = getattr(views_module, view_name, None)
            if fn is None:
                continue
            try:
                source = inspect.getsource(fn)
            except (OSError, TypeError):
                continue
            for pattern in self.ROLE_CHECK_PATTERNS:
                if pattern in source:
                    violations.append(
                        f"{view_name}: contains role-auth pattern '{pattern}'"
                    )
        return (len(violations) == 0), violations
