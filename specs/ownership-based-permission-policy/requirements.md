# Requirements Document

## Introduction

This spec defines the transition from role-based authorization to ownership-based permission enforcement across listing, messaging, and watchlist actions. The goal is to remove role assumptions from authorization logic while preserving current product behavior during migration. This spec covers permission rules, enforcement boundaries, and parity requirements for launch-critical flows.

## Dependencies

- **Required predecessor spec:** `migration-safety-and-compatibility-rails`
- This spec SHALL apply all permission and enforcement changes under the migration controls, checkpoint gates, and rollback rules defined in `migration-safety-and-compatibility-rails`.
- Permission cutover SHALL not proceed if predecessor parity or rollback-readiness gates are failing.

## Glossary

- **Ownership Policy**: Authorization model based on object ownership and participant relationships rather than user role.
- **Owner**: User referenced by `listing.created_by_user` for listing-scoped permissions.
- **Participant**: User permitted to interact with listing threads according to messaging rules.
- **Self-Message Block**: Rule that users cannot initiate messaging against their own listing.
- **Behavior Parity**: No user-visible regression in allowed/denied outcomes for launch-critical actions.

## Requirements

### Requirement 1: Enforce Migration Dependency and Safe Authorization Cutover

**User Story:** As a platform operator, I want permission refactors gated by migration safety rails, so policy cutover remains reversible.

#### Acceptance Criteria

1. WHEN this spec is implemented, THE System SHALL require dependency on `migration-safety-and-compatibility-rails` for sequencing and rollback safety.
2. WHILE compatibility mode is active, THE System SHALL preserve existing allowed/denied behavior for launch-critical actions.
3. IF permission parity validation fails, THEN THE System SHALL block authorization cutover and follow predecessor rollback/hold rules.
4. WHEN cleanup is requested, THE System SHALL allow destructive removal of legacy role checks only after predecessor cleanup gates pass.

### Requirement 2: Remove Role-Based Authorization as Policy Source

**User Story:** As a maintainer, I want role checks removed from authorization logic, so policy is consistent with role-agnostic architecture.

#### Acceptance Criteria

1. WHEN ownership policy is active, THE System SHALL not require `User.role` to authorize listing, watchlist, or messaging actions.
2. IF an authorization path still depends on role-based branching, THEN THE System SHALL mark the path non-compliant and block cutover.
3. WHILE transition is active, THE System SHALL ensure no new role-based authorization logic is introduced.
4. WHEN compliance validation runs, THE System SHALL verify authorization outcomes are driven by ownership/participant rules.

### Requirement 3: Enforce Listing Ownership Permissions

**User Story:** As a user, I want only listing owners to manage their listings, so listing control remains secure.

#### Acceptance Criteria

1. WHEN a user attempts listing edit/pause/delete actions, THE System SHALL allow the action only if `user == listing.created_by_user`.
2. WHEN a non-owner attempts owner-only listing actions, THE System SHALL deny the action deterministically.
3. WHILE listing ownership enforcement is active, THE System SHALL apply the same rule for both supply and demand listing types.
4. IF listing ownership cannot be resolved, THEN THE System SHALL deny owner-only mutations and log authorization failure context.

### Requirement 4: Enforce Messaging Eligibility by Listing Ownership and Participation

**User Story:** As a user, I want messaging permissions based on listing ownership and thread participation, so conversations remain correctly scoped.

#### Acceptance Criteria

1. WHEN a user attempts to initiate messaging on a listing, THE System SHALL deny initiation if `user == listing.created_by_user`.
2. WHEN a user attempts to access a listing thread, THE System SHALL allow access only for listing owner or thread initiator participants.
3. IF a non-participant attempts thread access or message send, THEN THE System SHALL deny the action deterministically.
4. WHILE compatibility mode is active, THE System SHALL preserve current user-visible messaging permission behavior.

### Requirement 5: Enforce Watchlist and Related Action Permissions

**User Story:** As a user, I want watchlist actions controlled by ownership of watchlist records, so saved items remain private and manageable.

#### Acceptance Criteria

1. WHEN a user performs watchlist save/archive/unarchive/delete actions, THE System SHALL enforce that operations apply only to that user’s watchlist records.
2. IF a user attempts to mutate another user’s watchlist state, THEN THE System SHALL deny the action.
3. WHILE migration compatibility mode is active, THE System SHALL preserve watchlist behavior parity for existing workflows.
4. WHEN validation gates run, THE System SHALL verify watchlist permission outcomes across legacy and target policy paths.

### Requirement 6: Centralize Permission Evaluation and Auditable Denials

**User Story:** As an operator, I want permission checks centralized and auditable, so policy drift and silent inconsistencies are prevented.

#### Acceptance Criteria

1. THE System SHALL evaluate launch-critical authorization decisions through a centralized permission layer.
2. WHEN permission is denied, THE System SHALL produce structured denial context sufficient for debugging and parity analysis.
3. IF distributed ad-hoc checks create inconsistent outcomes, THEN THE System SHALL block policy cutover until normalized.
4. WHILE compatibility mode is active, THE System SHALL compare central policy outcomes against legacy outcomes where applicable.

### Requirement 7: Testing and Validation Requirements

**User Story:** As a quality owner, I want explicit authorization test coverage, so ownership policy regressions are prevented.

#### Acceptance Criteria

1. THE System SHALL include automated tests for owner-allowed and non-owner-denied outcomes across listing, messaging, and watchlist actions.
2. THE System SHALL include tests for self-message blocking and participant-only thread access.
3. WHILE compatibility mode is active, THE System SHALL validate authorization parity across legacy and ownership-based policy paths.
4. IF launch-critical authorization tests fail, THEN THE System SHALL block checkpoint advancement under predecessor rules.

### Requirement 8: Scope Boundaries and Non-Goals

**User Story:** As a product owner, I want permission policy work scoped tightly, so migration risk stays controlled.

#### Acceptance Criteria

1. THE System SHALL limit scope to replacing role-based permission logic with ownership/participation-based policy.
2. THE System SHALL not include deferred capabilities such as payments, escrow, auctions, bidding, or logistics.
3. THE System SHALL not expand unrelated feature behavior while implementing this permission policy refactor.
4. IF requested changes are unrelated to permission policy migration, THEN THE System SHALL defer them to a separate spec.
