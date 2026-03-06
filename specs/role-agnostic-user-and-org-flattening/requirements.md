# Requirements Document

## Introduction

This spec defines the transition from a role-based user model and separate organization entity to a role-agnostic user profile with organization data flattened onto `User`. The goal is to remove role assumptions from identity and profile data while preserving current product behavior during migration. This spec covers only user/organization schema and model behavior changes required for architectural alignment.

## Dependencies

- **Required predecessor spec:** `migration-safety-and-compatibility-rails`
- This spec SHALL execute under the migration stages, compatibility controls, checkpoint gates, and rollback rules defined by `migration-safety-and-compatibility-rails`.
- Any schema/data operation in this spec that conflicts with additive-first migration, parity validation, or rollback safety is out of scope until the predecessor spec allows it.

## Glossary

- **Role-Agnostic User Model**: User model with no permanent role field; platform behavior derives from user actions.
- **Org Flattening**: Moving organization name data from `Organization` into optional `User.organization_name`.
- **Legacy Identity Schema**: Existing `User.role` + `Organization` data model and related read/write paths.
- **Target Identity Schema**: Updated `User` shape with optional `organization_name` and no role field.
- **Compatibility Mode**: Transitional mode where legacy and target schemas can coexist under controlled read/write behavior.
- **Behavior Parity**: No user-visible regression in signup, login, profile edit/view, listing ownership, and messaging identity display.

## Requirements

### Requirement 1: Enforce Migration Dependency and Safety Contract

**User Story:** As a platform operator, I want this refactor gated by migration safety controls, so that user identity changes do not introduce irreversible risk.

#### Acceptance Criteria

1. WHEN work on `role-agnostic-user-and-org-flattening` begins, THE System SHALL require dependency on `migration-safety-and-compatibility-rails` before destructive operations are allowed.
2. WHILE this spec is in progress, THE System SHALL apply schema/data changes using additive-first sequencing defined by `migration-safety-and-compatibility-rails`.
3. IF a proposed model change violates the predecessor spec’s checkpoint or rollback rules, THEN THE System SHALL block progression until the change is made compliant.
4. WHEN checkpoint gates fail during this spec, THE System SHALL follow predecessor rollback procedures before continuing.

### Requirement 2: Remove Permanent Role from User Model

**User Story:** As a product owner, I want the user identity model to be role-agnostic, so that users can act as demander and supplier based on listings rather than profile role.

#### Acceptance Criteria

1. WHEN target identity schema is active, THE System SHALL represent users without a persistent `User.role` field.
2. WHILE compatibility mode is active, THE System SHALL preserve existing runtime behavior for authentication and profile workflows without relying on new role-based logic.
3. IF any application path still requires role-based branching, THEN THE System SHALL flag it as non-compliant and block cutover for this spec.
4. WHEN role removal cutover occurs, THE System SHALL ensure role-derived behavior is replaced by ownership/action-derived behavior without user-visible regression.

### Requirement 3: Flatten Organization Data onto User

**User Story:** As a user, I want my organization name to remain available on my profile without requiring a separate organization model.

#### Acceptance Criteria

1. WHEN target identity schema is introduced, THE System SHALL add optional `User.organization_name` as the canonical organization display field.
2. WHILE compatibility mode is active, THE System SHALL backfill organization name values from legacy organization data into `User.organization_name` deterministically.
3. IF multiple legacy organization records create ambiguity for a user, THEN THE System SHALL apply a deterministic conflict rule and log the resolution outcome.
4. WHEN cutover completes, THE System SHALL not require `Organization.type` and SHALL treat it as removed from product semantics.

### Requirement 4: Preserve Identity-Related Product Behavior During Transition

**User Story:** As an authenticated user, I want signup/login/profile behavior to remain stable during migration, so that I am not disrupted by backend model changes.

#### Acceptance Criteria

1. WHEN schema and model migration steps are applied, THE System SHALL preserve behavior parity for signup, login, logout, profile view, and profile edit flows.
2. WHILE compatibility mode is active, THE System SHALL preserve existing display behavior for user identity fields in listings and messaging surfaces.
3. IF identity data is unavailable in the target path during transition, THEN THE System SHALL use compliant fallback behavior defined by the predecessor migration spec.
4. WHEN parity validation runs, THE System SHALL verify no launch-critical identity flow regresses before checkpoint advancement.

### Requirement 5: Update Validation and Data Constraints for Target User Schema

**User Story:** As a maintainer, I want explicit constraints for the flattened user schema, so that data quality is preserved without the old organization model.

#### Acceptance Criteria

1. THE System SHALL enforce `organization_name` as optional and bounded by an explicit maximum length.
2. WHEN users do not provide organization data, THE System SHALL accept and persist null/empty-equivalent values according to schema rules.
3. WHILE target schema is active, THE System SHALL enforce existing validation rules for unaffected user fields (email, display name, location, preferences).
4. IF incoming data violates target field constraints, THEN THE System SHALL reject the write with deterministic validation behavior.

### Requirement 6: Eliminate Organization Model as Runtime Dependency

**User Story:** As a platform operator, I want the application runtime to no longer depend on `Organization`, so that identity data ownership is simplified.

#### Acceptance Criteria

1. WHEN target read paths are active, THE System SHALL resolve organization display data from `User.organization_name` rather than `Organization` joins.
2. WHILE compatibility mode is active, THE System SHALL support transitional read/write behavior without requiring new runtime dependence on `Organization.type`.
3. IF runtime code paths still require direct `Organization` dependency after cutover checkpoint, THEN THE System SHALL fail compliance validation for this spec.
4. WHEN this spec reaches cleanup readiness, THE System SHALL mark legacy organization structures as removable only under predecessor destructive-change gates.

### Requirement 7: Testing and Validation Requirements

**User Story:** As a quality owner, I want targeted tests for role removal and org flattening, so that regression risk is controlled.

#### Acceptance Criteria

1. WHEN implementation for this spec is prepared, THE System SHALL include automated tests for user schema changes, org flattening transforms, and behavior parity across compatibility stages.
2. WHILE compatibility mode is active, THE System SHALL validate dual-path consistency for organization display values and user identity reads.
3. WHEN pre-cutover gates run, THE System SHALL verify that role-based branching is eliminated from identity/auth/profile flows covered by this spec.
4. IF any validation in this spec fails, THEN THE System SHALL block checkpoint advancement and follow predecessor rollback/hold rules.

### Requirement 8: Scope Boundaries and Non-Goals

**User Story:** As a product owner, I want this spec constrained to identity architecture alignment, so that unrelated feature work does not expand migration risk.

#### Acceptance Criteria

1. THE System SHALL limit this spec to role-agnostic user modeling and organization flattening behavior.
2. THE System SHALL not include new marketplace capabilities such as payments, escrow, auctions, bidding, or logistics.
3. WHILE this spec is active, THE System SHALL defer unrelated listing, discovery, and messaging feature expansion to separate specs.
4. IF a requested change is not necessary for role removal, org flattening, or migration compliance, THEN THE System SHALL defer it.
