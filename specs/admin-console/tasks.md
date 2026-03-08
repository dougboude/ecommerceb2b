# Implementation Plan

## Pre-Execution Gate Checklist

Before implementation begins, verify:

- [ ] 0.1 Confirm `specs/admin-console/requirements.md` and `specs/admin-console/design.md` are approved and unchanged from latest review.
- [ ] 0.2 Confirm this feature status is `REQ, DES, TASK` in `specs/SPEC_ORDER.md` before execution starts.
- [ ] 0.3 Confirm implementation branch is cut from current `main`.

---

## Phase 1 — Data Model and Access Foundation

### Group 1 — Admin Route Boundary and Staff Guard

- [ ] 1.1 Add Admin Console URL namespace under `/ops/` with dedicated route names.
  - Include routes for: dashboard, users list/detail, listings list/detail, flags queue/detail, global search, audit list.
  - Keep routes separate from normal user-facing URLs.
  - _Requirements: 1, 7_

- [ ] 1.2 Implement route-level staff guard.
  - Require authenticated + staff/admin capability for all `/ops/` routes.
  - Ensure unauthorized users receive explicit denial behavior.
  - _Requirements: 1, 1A_

- [ ] 1.3 Implement action-level permission checks.
  - Add fine-grained checks for sensitive actions (hard delete, account deactivate/reactivate, message oversight access).
  - _Requirements: 1A, 3, 5_

### Group 2 — New Models (Minimal Additions)

- [ ] 2.1 Add `ContentFlag` model using GenericForeignKey target pattern.
  - Fields: reporter, `target_content_type`, `target_object_id`, `target`, reason_category, reason_note, status, resolved_by, resolved_at, resolution_note, timestamps.
  - Restrict v1 flaggable targets to `User` and `Listing` through validation/form constraints.
  - _Requirements: 4_

- [ ] 2.2 Add `AdminAuditLog` model as append-only action log.
  - Capture actor, action type, target type/id, timestamp, reason, status, failure context, optional metadata.
  - _Requirements: 8_

- [ ] 2.3 Add `ModerationNote` model (admin-only internal notes).
  - Polymorphic target (`user`, `listing`, `flag`), author, body, timestamps.
  - _Requirements: 8A_

- [ ] 2.4 Create additive migrations and apply them.
  - Verify no destructive migration operations.
  - _Requirements: all model-backed requirements_

---

## Phase 2 — Admin Console Core Screens

### Group 3 — Dashboard

- [ ] 3.1 Build Admin Console dashboard view/template.
  - Display minimum required metrics:
    - total users
    - new users (7-day window)
    - active listings
    - listings created (7-day window)
    - conversations started (7-day window)
    - unresolved flags
    - recent moderation actions
  - Show metric data freshness timestamp.
  - _Requirements: 6_

### Group 4 — User Management UI

- [ ] 4.1 Build user search/list view for admin.
  - Support search by user ID, email, display name.
  - _Requirements: 2_

- [ ] 4.2 Build user detail view.
  - Show account status, listing summary by status, messaging footprint summary, moderation history timeline.
  - _Requirements: 2_

- [ ] 4.3 Add deactivate/reactivate actions with confirmations.
  - Require explicit confirmation before status change.
  - Write audit records for both success and failure.
  - _Requirements: 2, 8_

- [ ] 4.4 Add internal moderation notes on user detail.
  - Staff-only note creation/view.
  - _Requirements: 8A_

### Group 5 — Listing Moderation UI

- [ ] 5.1 Build listing search/list view for admin.
  - Search by listing ID, owner, status, and item text.
  - _Requirements: 3_

- [ ] 5.2 Build listing detail view with owner visibility.
  - Show listing owner account identity and direct link to owner’s admin user detail page.
  - _Requirements: 3_

- [ ] 5.3 Add reversible listing moderation actions.
  - Soft remove and restore.
  - Forced pause and forced expiry.
  - Confirm each action before apply.
  - Write audit logs.
  - _Requirements: 3, 8, 9_

- [ ] 5.4 Add restricted hard delete flow.
  - Elevated permission + explicit irreversible confirmation.
  - Preserve associated message threads as historical records.
  - Write audit logs for attempts and outcomes.
  - _Requirements: 3, 8, 9_

- [ ] 5.5 Add internal moderation notes on listing detail.
  - Staff-only note creation/view.
  - _Requirements: 8A_

---

## Phase 3 — Flagging, Queue, and Messaging Oversight

### Group 6 — User Flag Submission + Queue

- [ ] 6.1 Add user-facing flag submission endpoints/forms.
  - Allow flagging of users and listings only in v1.
  - Require controlled reason category selection:
    - spam
    - fraudulent_listing
    - prohibited_item
    - abusive_behavior
    - misleading_content
    - other
  - _Requirements: 4_

- [ ] 6.2 Build admin moderation queue view.
  - Show unresolved/open flags with aging context.
  - _Requirements: 4, 6_

- [ ] 6.3 Build flag detail and resolution actions.
  - Dismiss, resolve-with-action, escalate.
  - Capture resolver, resolution timestamp, outcome note.
  - _Requirements: 4_

- [ ] 6.4 Add grouped related-flag context and bulk resolution.
  - Show related flags for same target.
  - Implement bulk resolution for multiple unresolved flags on same object.
  - _Requirements: 4_

- [ ] 6.5 Add moderation notes on flag detail.
  - Staff-only note creation/view.
  - _Requirements: 8A_

### Group 7 — Messaging Oversight Guardrails

- [ ] 7.1 Implement moderation-context-only thread access path.
  - Allow admin thread view only when entering from related flagged/moderated user/listing/flag context.
  - Block unrestricted arbitrary thread browsing.
  - _Requirements: 5_

- [ ] 7.2 Require justification capture on thread access.
  - Store justification with audit entry.
  - _Requirements: 5, 8_

---

## Phase 4 — Global Search and Audit Explorer

### Group 8 — Admin Global Search

- [ ] 8.1 Build grouped global search view.
  - Return grouped results for users, listings, threads.
  - Highlight flagged/moderated results.
  - Preserve query on empty state.
  - _Requirements: 7_

### Group 9 — Audit Log Explorer

- [ ] 9.1 Build audit log list/filter view.
  - Filter by actor, action type, target type/id, date range.
  - Admin-only visibility.
  - _Requirements: 8_

---

## Phase 5 — Verification and Hardening

### Group 10 — Tests

- [ ] 10.1 Add unit tests for permission predicates and admin role checks.
  - _Requirements: 1, 1A_

- [ ] 10.2 Add model tests for `ContentFlag` constraints and reason categories.
  - Validate v1 target restriction to user/listing despite generic target schema.
  - _Requirements: 4_

- [ ] 10.3 Add model tests for `AdminAuditLog` append-only write behavior.
  - _Requirements: 8_

- [ ] 10.4 Add integration tests for admin route protection and action authorization.
  - _Requirements: 1, 1A_

- [ ] 10.5 Add integration tests for listing moderation actions and owner-link visibility.
  - _Requirements: 3_

- [ ] 10.6 Add integration tests for flag lifecycle and bulk resolution.
  - _Requirements: 4_

- [ ] 10.7 Add integration tests for message oversight guardrails + justification audit.
  - _Requirements: 5, 8_

- [ ] 10.8 Add integration tests for dashboard minimum metric cards and global search grouping.
  - _Requirements: 6, 7_

- [ ] 10.9 Add integration tests for moderation notes visibility boundaries.
  - _Requirements: 8A_

### Group 11 — Final Validation

- [ ] 11.1 Run full test suite and ensure no regressions.
  - `manage.py test marketplace --verbosity=1`

- [ ] 11.2 Run targeted manual operator smoke checks.
  - Staff login -> `/ops/` access
  - Non-staff denied
  - Deactivate/reactivate user
  - Soft remove/restore listing
  - Resolve flags (single + bulk)
  - Message oversight requires justification
  - Audit records visible for all above

- [ ] 11.3 Confirm scope boundaries remain intact.
  - No tenant admin tooling
  - No payment/escrow/logistics capabilities
  - No automated enforcement pipelines beyond manual moderation actions

- [ ] 11.4 After implementation completion, update:
  - `specs/SPEC_ORDER.md` -> add `EXEC`
  - `ai-docs/SESSION_STATUS.md` -> implementation summary + validation evidence
