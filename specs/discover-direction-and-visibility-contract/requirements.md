# Requirements Document

## Introduction

This spec defines explicit discover search direction and listing visibility rules for the role-agnostic architecture. The goal is to remove role-inferred discover behavior and ensure authenticated users can search counterpart listing types predictably. This spec covers search-direction selection, session persistence rules, visibility semantics, and migration-safe parity constraints.

## Dependencies

- **Required predecessor spec:** `migration-safety-and-compatibility-rails`
- This spec SHALL follow migration safety sequencing, compatibility controls, validation gates, and rollback rules defined by `migration-safety-and-compatibility-rails`.
- Discover behavior cutover SHALL be blocked whenever predecessor parity or rollback-readiness gates are not satisfied.

## Glossary

- **Search Direction**: Explicit user-selected discover mode: `Find Supply` or `Find Demand`.
- **Counterpart Type Rule**: Discover returns listing type opposite to the user’s current discovery intent.
- **Visibility Contract**: Rule set for which listings are discoverable to authenticated users.
- **Assistive Suggestions**: Semantic/keyword suggestions that enhance discovery but do not gate access.
- **Behavior Parity**: No regression in discover usability during compatibility window.

## Requirements

### Requirement 1: Enforce Migration Dependency and Safe Discover Cutover

**User Story:** As a platform operator, I want discover refactors governed by migration safety rails, so search behavior changes remain reversible.

#### Acceptance Criteria

1. WHEN this spec is implemented, THE System SHALL require dependency on `migration-safety-and-compatibility-rails` for sequencing and rollback safety.
2. WHILE compatibility mode is active, THE System SHALL preserve current discover flow reliability and availability.
3. IF discover parity validations fail, THEN THE System SHALL block behavior cutover and follow predecessor rollback/hold procedures.
4. WHEN destructive legacy discover assumptions are removed, THE System SHALL do so only under predecessor cleanup gates.

### Requirement 2: Require Explicit Search Direction Selection

**User Story:** As an authenticated user, I want to choose search direction explicitly, so discover behavior does not assume my role.

#### Acceptance Criteria

1. WHEN a user uses discover, THE System SHALL provide explicit direction options `Find Supply` and `Find Demand`.
2. THE System SHALL allow any authenticated user to select either direction regardless of what listing types they have created.
3. WHEN direction is selected, THE System SHALL pass direction explicitly to search execution.
4. IF direction is missing or invalid, THEN THE System SHALL apply deterministic fallback/validation behavior without role inference.

### Requirement 3: Enforce Counterpart Type Query Behavior

**User Story:** As a user, I want discover results to reflect the selected intent, so returned listings match my search goal.

#### Acceptance Criteria

1. WHEN direction is `Find Supply`, THE System SHALL query listings where `type = SUPPLY`.
2. WHEN direction is `Find Demand`, THE System SHALL query listings where `type = DEMAND`.
3. WHILE direction-based discover is active, THE System SHALL apply the same semantic and keyword infrastructure for both directions.
4. IF filtering/ranking logic differs between directions, THEN THE System SHALL require explicit rule definition and parity validation.

### Requirement 4: Persist and Clear Discover Direction with Search State

**User Story:** As a user, I want discover direction to persist with my active search context, so the workflow is predictable.

#### Acceptance Criteria

1. WHEN a discover search is executed, THE System SHALL persist selected direction in session alongside other discover parameters.
2. WHILE user remains in discover workflow, THE System SHALL reuse persisted direction for subsequent compatible actions.
3. WHEN Clear Search is triggered, THE System SHALL clear persisted direction and associated discover state.
4. IF session state is unavailable, THEN THE System SHALL fall back to deterministic default behavior without role inference.

### Requirement 5: Enforce Discovery Visibility Contract

**User Story:** As an authenticated user, I want active listings searchable even without suggestion matches, so discovery remains open and useful.

#### Acceptance Criteria

1. THE System SHALL make all `ACTIVE` listings discoverable to authenticated users under selected discover direction and applicable filters.
2. THE System SHALL treat suggestions/matching as assistive ranking inputs and not as mandatory access gates.
3. WHEN a listing is `PAUSED`, `EXPIRED`, or `DELETED`, THE System SHALL exclude it from active discover results according to status rules.
4. IF visibility logic attempts to hide valid active listings solely due to lack of suggestion match, THEN THE System SHALL reject that behavior.

### Requirement 6: Remove Role-Inferred Discover Assumptions

**User Story:** As a maintainer, I want discover behavior free of role assumptions, so architecture stays consistent with role-agnostic product rules.

#### Acceptance Criteria

1. WHEN discover executes, THE System SHALL not infer direction from user role or equivalent legacy role signal.
2. IF discover code paths include role-based branching, THEN THE System SHALL mark them non-compliant and block cutover.
3. WHILE migration compatibility mode is active, THE System SHALL preserve discover behavior parity without introducing new role dependencies.
4. WHEN compliance validation runs, THE System SHALL verify role-independent discover direction behavior for both options.

### Requirement 7: Testing and Validation Requirements

**User Story:** As a quality owner, I want explicit discover-direction and visibility validation, so regressions are detected before launch-critical phases.

#### Acceptance Criteria

1. THE System SHALL include automated tests for direction selection, direction persistence/clear behavior, and counterpart type filtering.
2. THE System SHALL include tests for visibility contract enforcement for active and non-active statuses.
3. WHILE compatibility mode is active, THE System SHALL validate discover parity across legacy and target paths where applicable.
4. IF launch-critical discover validation fails, THEN THE System SHALL block checkpoint advancement per predecessor rules.

### Requirement 8: Scope Boundaries and Non-Goals

**User Story:** As a product owner, I want discover contract work tightly scoped, so migration risk remains controlled.

#### Acceptance Criteria

1. THE System SHALL limit scope to discover direction and visibility contract alignment required for role-agnostic architecture.
2. THE System SHALL not include deferred capabilities such as payments, escrow, auctions, bidding, or logistics.
3. THE System SHALL not introduce unrelated ranking/ML feature expansion beyond migration-aligned behavior.
4. IF requested work is outside discover contract migration scope, THEN THE System SHALL defer it.
