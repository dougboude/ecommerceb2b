# Requirements Document

## Introduction

This specification defines the first version of the NicheMarket Admin Console: an internal operations and moderation interface for trusted company employees.

The Admin Console is not customer-facing and is not a tenant-admin system. It exists to help internal operators safely monitor platform health, moderate harmful content/behavior, and perform auditable intervention actions with minimal risk.

This version is intentionally lean. It prioritizes operational visibility and reversible moderation controls over broad administrative power.

## Dependencies

- Existing authentication and user account system (including email verification)
- Existing listing model and lifecycle states
- Existing messaging, watchlist, discover, and profile systems
- Existing ownership-based permission model in the user-facing product

## Glossary

- **Admin Console:** Internal web UI for company operators to manage moderation and platform operations.
- **Admin Operator:** Trusted internal employee with elevated permissions to access Admin Console features.
- **Moderation Action:** Admin-initiated intervention on a user, listing, flag, or thread (for example deactivate, hide, restore).
- **Soft Remove Listing:** Reversible action that hides a listing from user-facing surfaces without deleting underlying records.
- **Hard Delete Listing:** Irreversible deletion of a listing record and directly associated presentation data; used rarely.
- **Flag:** User-submitted report on a listing or user account indicating potential policy violation.
- **Moderation Queue:** Ordered work queue of unresolved flags requiring admin review.
- **Forced Pause / Forced Expiry:** Admin action that transitions listing state for safety/operations reasons.
- **Audit Log Entry:** Immutable record of an admin action including actor, target, action, timestamp, and optional reason.
- **Justified Message Access:** Restricted admin access to message threads when linked to a flag/moderation case and accompanied by a reason.

## Actors

- **Admin Operator (Primary):** Internal staff member who monitors, investigates, and moderates platform activity.
- **Support Operator (Secondary):** Internal staff member who handles user support escalations with limited admin actions.
- **End User (Reporter):** Regular platform user who can submit flags on listings or users.
- **System:** Services that enforce access control, process moderation actions, and write audit records.

## Scope Boundaries

### In Scope (This Spec)

- Internal admin access model and admin UI entry point
- User search/view, activation status changes, activity summary, moderation history
- Listing moderation (soft remove, restore, forced pause/expiry, rare hard delete)
- User flagging flow and moderation queue handling
- Guard-railed messaging oversight tied to moderation context
- Operational dashboard metrics for platform health
- Global admin search for users/listings/threads
- Audit logging for all admin actions

### Out of Scope (This Spec)

- Customer or tenant self-service admin roles
- Role delegation workflows for external organizations
- Full BI/reporting warehouse features
- Automated enforcement pipelines (for example auto-ban rules)
- Legal hold/eDiscovery workflows
- Payment/escrow/logistics tooling
- Design and implementation details (covered in later design/tasks docs)

---

## Requirements

### Requirement 1: Admin Access Model and Console Entry

**User Story:** As an internal operator, I want a clearly separated admin interface with strict access controls so only trusted staff can use moderation tools.

#### Acceptance Criteria (EARS)

1. WHEN a signed-in user has the internal admin permission set, THE System SHALL allow access to the Admin Console routes.
2. WHEN a signed-in user does not have internal admin permissions, THE System SHALL deny Admin Console access.
3. WHEN an unauthenticated visitor requests an Admin Console route, THE System SHALL require authentication before any admin content is shown.
4. WHEN an authorized admin opens the Admin Console entry point, THE System SHALL present an interface visually separated from normal user navigation.
5. WHILE an operator is using the Admin Console, THE System SHALL preserve separation from normal user-facing workflows to reduce accidental cross-context actions.

---

### Requirement 1A: Admin Role Representation

**User Story:** As a platform architect, I want admin capability represented explicitly on user accounts so internal operators are clearly distinguishable from normal users.

#### Acceptance Criteria (EARS)

1. WHEN a user is granted Admin Console capability, THE System SHALL represent that capability through an explicit role/attribute/permission assignment on the user account.
2. WHEN an account does not have admin capability, THE System SHALL treat it as a normal user account even if it is otherwise active and verified.
3. WHEN admin capability is evaluated for access or action authorization, THE System SHALL use the explicit admin assignment rather than UI-only checks.
4. WHEN viewing account details in admin context, THE System SHALL clearly indicate whether the account is an admin operator or a normal user.

---

### Requirement 2: User Management for Internal Operators

**User Story:** As an admin operator, I want to find accounts, inspect account context, and activate/deactivate users safely so I can handle abuse and support cases.

#### Acceptance Criteria (EARS)

1. WHEN an admin searches users by email, display name, or user ID, THE System SHALL return matching user accounts with key status fields.
2. WHEN an admin opens a user detail view, THE System SHALL display an activity summary including listing counts by status, messaging footprint summary, and recent moderation events.
3. WHEN an admin deactivates a user account, THE System SHALL apply a reversible deactivation state and prevent normal account usage.
4. WHEN an admin reactivates a previously deactivated account, THE System SHALL restore normal account access.
5. WHEN a user account has prior moderation actions, THE System SHALL display a moderation history timeline on the user detail view.
6. WHEN an admin performs user activation-state changes, THE System SHALL require an explicit confirmation step before committing.

---

### Requirement 3: Listing Moderation Controls

**User Story:** As an admin operator, I want reversible listing controls first and destructive tools only when necessary so moderation actions are safe and proportionate.

#### Acceptance Criteria (EARS)

1. WHEN an admin searches listings by listing ID, title/item text, owner, or status, THE System SHALL return matching listings with moderation-relevant metadata.
2. WHEN an admin performs soft remove on a listing, THE System SHALL hide the listing from normal user-facing discovery/browse surfaces while retaining underlying records.
3. WHEN an admin restores a soft-removed listing, THE System SHALL return that listing to normal visibility according to its current lifecycle state.
4. WHEN an admin forces a listing pause, THE System SHALL transition listing state to paused with admin attribution.
5. WHEN an admin forces listing expiry, THE System SHALL transition listing state to expired with admin attribution.
6. WHEN an admin attempts hard delete on a listing, THE System SHALL require elevated confirmation and explicit acknowledgement that the action is irreversible.
7. IF a listing is hard deleted, THE System SHALL preserve associated message threads as historical records, detached from active listing display surfaces.
8. WHEN an admin views a listing detail page in the Admin Console, THE System SHALL display the listing owner account and provide direct navigation to that owner's admin user detail view.

---

### Requirement 4: Content Flagging and Moderation Queue

**User Story:** As a platform user, I want to report problematic listings or users so the operations team can review and act.

#### Acceptance Criteria (EARS)

1. WHEN a signed-in user flags a listing or user, THE System SHALL create a flag record with reporter, target type, target ID, reason category, optional notes, and timestamp.
2. WHEN a flag is created, THE System SHALL require reason category selection from a controlled set including at minimum: `spam`, `fraudulent_listing`, `prohibited_item`, `abusive_behavior`, `misleading_content`, and `other`.
3. WHEN new unresolved flags exist, THE System SHALL place them in an admin moderation queue.
4. WHEN an admin reviews a flag, THE System SHALL allow one of the core outcomes: dismiss, take moderation action, or escalate for follow-up.
5. WHEN an admin resolves a flag, THE System SHALL persist resolution status, resolver identity, resolution timestamp, and outcome note.
6. IF multiple flags reference the same target, THE System SHALL allow admins to view related flags together to support coherent decisions.
7. IF multiple unresolved flags reference the same target object, THE System SHOULD allow admins to resolve them collectively with one moderation outcome action.

---

### Requirement 5: Messaging Oversight with Justification Guardrails

**User Story:** As an admin operator, I want limited message-thread visibility for moderation investigations without enabling broad unrestricted surveillance.

#### Acceptance Criteria (EARS)

1. WHEN a listing, user, or flag under review has related message threads, THE System SHALL allow admins to access those related threads.
2. WHEN an admin opens a private thread through moderation tooling, THE System SHALL require a justification reason to be recorded for access.
3. IF a thread is not linked to a flagged or moderated object, THE System SHALL restrict direct browsing from admin tools by default.
4. WHEN message oversight access occurs, THE System SHALL write an audit record including actor, thread target, and justification.

---

### Requirement 6: Platform Activity Dashboard

**User Story:** As an internal operator, I want a high-level platform dashboard so I can quickly assess health and moderation workload.

#### Acceptance Criteria (EARS)

1. WHEN an admin opens the Admin Console home/dashboard, THE System SHALL display at minimum: total users, new users (7-day window), active listings, listings created (7-day window), conversations started (7-day window), unresolved flags, and recent moderation actions.
2. WHEN unresolved flags exist, THE System SHALL display unresolved-flag volume and aging indicators.
3. WHEN recent moderation actions exist, THE System SHALL display a recent-actions summary panel.
4. WHILE dashboard metrics are shown, THE System SHALL provide timestamp context indicating data freshness.

---

### Requirement 7: Global Admin Search

**User Story:** As an admin operator, I want one global search entry point for users, listings, and threads so I can investigate issues quickly.

#### Acceptance Criteria (EARS)

1. WHEN an admin enters a query in global admin search, THE System SHALL return grouped results for users, listings, and message threads.
2. WHEN search results include flagged or moderated objects, THE System SHALL visually indicate that moderation context in results.
3. WHEN an admin selects a search result, THE System SHALL navigate directly to the corresponding admin detail page.
4. IF no matches are found, THE System SHALL return a clear empty state and preserve the query for refinement.

---

### Requirement 8: Audit Logging for Admin Actions

**User Story:** As a compliance-conscious operator, I want complete auditability of admin interventions so every action is attributable and reviewable.

#### Acceptance Criteria (EARS)

1. WHEN any admin action is executed (including view-sensitive actions like justified message access), THE System SHALL create an immutable audit log entry.
2. WHEN an audit log entry is created, THE System SHALL capture at minimum: actor, action type, target object type, target object ID, timestamp, and optional reason/note.
3. IF an admin action fails after initiation, THE System SHALL log the failed attempt with actor, attempted action, target, timestamp, and failure context.
4. WHEN an authorized admin reviews audit logs, THE System SHALL support filtering by actor, action type, target type, target ID, and date range.
5. WHILE audit logs are retained, THE System SHALL prevent ordinary user roles from accessing them.

---

### Requirement 8A: Internal Moderation Notes

**User Story:** As an admin operator, I want to attach internal notes to moderation targets so investigation context is retained across shifts and follow-ups.

#### Acceptance Criteria (EARS)

1. WHEN an admin is viewing a user, listing, or flag in admin context, THE System SHOULD allow creating internal moderation notes attached to that object.
2. WHEN an internal note is created or updated, THE System SHALL record note author and timestamp.
3. WHILE internal moderation notes are stored, THE System SHALL keep them visible only to authorized admin operators.

---

### Requirement 9: Lean Safety Principles for V1 Admin Console

**User Story:** As a product owner, I want the first admin release to stay lean and safe so we deliver high-value operations capability without overbuilding.

#### Acceptance Criteria (EARS)

1. WHEN both reversible and irreversible moderation actions are possible, THE System SHALL prefer reversible actions in primary UI affordances.
2. WHEN an admin initiates an irreversible action, THE System SHALL require explicit confirmation and warning copy.
3. WHEN moderation outcomes are recorded, THE System SHALL link outcomes to the originating flag or investigation context where applicable.
4. IF a capability is not required for moderation or core operations visibility, THE System SHALL defer it from V1 scope.
