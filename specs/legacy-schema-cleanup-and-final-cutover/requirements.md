# Requirements Document

## Introduction

This spec defines the final phase of the migration arc: converting all application code to use the unified `Listing` model, removing legacy models and role-based constructs, and executing the CP5 cleanup checkpoint. It is the culmination of the migration safety framework built in Feature 1 and the additive schema work done in Features 2–6. After this spec is executed, the codebase will have no legacy role-based models, no dual-write compatibility shims, and no `DemandPost`/`SupplyLot`/`Organization` constructs remaining.

## Dependencies

- **Required predecessor specs:** All six foundation specs must be `EXEC`:
  - `migration-safety-and-compatibility-rails`
  - `role-agnostic-user-and-org-flattening`
  - `unified-listing-model-and-status-contract`
  - `ownership-based-permission-policy`
  - `listing-centric-messaging-and-watchlist-decoupling`
  - `discover-direction-and-visibility-contract`
- All migration parity gates (`counts`, `relationships`, `identity`, `listing`, `permission`) must be passing at CP4 before cleanup begins.
- CP5 advancement is irreversible. Rollback to pre-cleanup state is not available after CP5 executes.

## Glossary

- **Legacy Models**: `DemandPost`, `SupplyLot`, `Organization`, old `WatchlistItem` (supply_lot/demand_post FKs), old `MessageThread` (buyer/supplier FKs).
- **Target Models**: `Listing`, `ListingWatchlistItem`, `ListingMessageThread` (and eventual renamed final forms).
- **Compatibility Shim**: Any code whose sole purpose is maintaining dual-write or dual-read behavior during migration transition.
- **CP5**: The cleanup checkpoint in the migration control state machine. Advancing to CP5 signals that legacy models are safe to remove.
- **Application Migration**: The conversion of views, forms, templates, signals, and helper code from legacy models to target models.

## Requirements

### Requirement 1: Prerequisite Gate Enforcement

**User Story:** As a platform operator, I want cleanup gated behind confirmed migration parity, so destructive model removal is never executed prematurely.

#### Acceptance Criteria

1. WHEN cleanup begins, THE System SHALL verify all parity reports pass: `counts`, `relationships`, `identity`, `listing`, `permission`.
2. WHEN any parity gate is failing, THE System SHALL block cleanup and require remediation before proceeding.
3. WHEN the system is not at CP4, THE System SHALL block CP5 advancement.
4. WHEN CP5 is advanced, THE System SHALL log the cutover event in migration state records.

### Requirement 2: Convert Application Code to Unified Listing Model

**User Story:** As a maintainer, I want all views, forms, and templates to reference the unified `Listing` model, so legacy models can be safely removed.

#### Acceptance Criteria

1. WHEN the application code migration is complete, THE System SHALL have no view, form, template, or helper that imports or queries `DemandPost` or `SupplyLot` in a production code path.
2. THE System SHALL convert listing creation, edit, toggle, delete, and detail views to operate on `Listing` objects.
3. THE System SHALL convert listing list views for both supply and demand to query `Listing` filtered by `type`.
4. THE System SHALL convert matching and suggestion logic to operate on `Listing` objects.
5. THE System SHALL convert vector search index/remove/search calls to use `Listing` objects.
6. IF any production code path still references `DemandPost` or `SupplyLot` after migration, THEN THE System SHALL treat that as a compliance violation blocking CP5.

### Requirement 3: Convert Messaging and Watchlist to Target Models

**User Story:** As a maintainer, I want messaging and watchlist flows to use `ListingMessageThread` and `ListingWatchlistItem`, so legacy thread and watchlist models can be removed.

#### Acceptance Criteria

1. WHEN messaging flows are converted, THE System SHALL use `ListingMessageThread` for all thread creation, access, and display.
2. WHEN watchlist flows are converted, THE System SHALL use `ListingWatchlistItem` for all watchlist save, archive, and delete operations.
3. THE System SHALL preserve all existing user-visible messaging and watchlist behavior during and after conversion.
4. THE System SHALL convert the inbox view, thread detail view, and watchlist view to use target model queries.

### Requirement 4: Remove User.role and Organization Model

**User Story:** As a maintainer, I want `User.role` and the `Organization` model removed, so the codebase fully reflects the role-agnostic architecture.

#### Acceptance Criteria

1. WHEN cleanup is executed, THE System SHALL remove the `role` field from the `User` model via Django migration.
2. WHEN cleanup is executed, THE System SHALL remove the `Organization` model and its table via Django migration.
3. THE System SHALL remove all references to `User.role`, `Role` enum, and `Organization` from production code paths.
4. IF any code path reads or writes `User.role` after removal, THE System SHALL fail at import or migration time, not silently.
5. THE System SHALL retain `User.organization_name` (the flat text field added in Feature 2) as the replacement for org identity.

### Requirement 5: Remove Legacy Models via Django Migration

**User Story:** As a maintainer, I want legacy database tables dropped cleanly, so the schema matches the target architecture without orphaned tables.

#### Acceptance Criteria

1. WHEN CP5 is achieved and application migration is complete, THE System SHALL apply a Django migration that drops: `DemandPost`, `SupplyLot`, `Organization`, old `WatchlistItem`, old `MessageThread`, `ThreadReadState` (if superseded).
2. THE migration SHALL be irreversible (no `database_backwards` implementation required — this is a destructive cleanup migration).
3. THE System SHALL remove legacy FK constraints and indexes in the same migration.
4. THE System SHALL not remove `MigrationState`, `LegacyToTargetMapping`, `BackfillAuditRecord`, or `ParityReport` — these are retained as permanent audit records.

### Requirement 6: Remove Compatibility Shims

**User Story:** As a maintainer, I want dual-write signals, compatibility repositories, and adapter code removed, so runtime overhead and dead code are eliminated.

#### Acceptance Criteria

1. WHEN legacy models are removed, THE System SHALL remove dual-write signal handlers in `marketplace/signals.py`.
2. THE System SHALL remove `CompatibilityRepository`, `ListingCompatibilityService`, and `IdentityCompatibilityAdapter` from production code paths.
3. THE System SHALL remove the `migration_control/compatibility.py` and `migration_control/listings.py` adapter modules.
4. THE System SHALL retain `migration_control/state.py`, `migration_control/checkpoints.py`, `migration_control/parity.py`, and `migration_control/permissions.py` as permanent migration governance infrastructure.
5. THE System SHALL retain all management commands (`migration_validate`, `migration_cutover`, etc.) for audit and operational use.

### Requirement 7: Testing and Validation Requirements

**User Story:** As a quality owner, I want full regression coverage after cleanup, so no user-visible functionality is broken by legacy model removal.

#### Acceptance Criteria

1. THE System SHALL include tests verifying listing CRUD flows operate correctly on the unified `Listing` model.
2. THE System SHALL include tests verifying messaging flows operate on `ListingMessageThread`.
3. THE System SHALL include tests verifying watchlist flows operate on `ListingWatchlistItem`.
4. THE System SHALL include tests verifying `User.role` and `Organization` no longer exist.
5. IF any test references legacy model imports that no longer exist, THEN THE System SHALL fail at import time with a clear error.

### Requirement 8: Scope Boundaries and Non-Goals

**User Story:** As a product owner, I want cleanup scoped tightly to model removal, so no unrelated feature work is bundled in.

#### Acceptance Criteria

1. THE System SHALL limit scope to converting application code and removing legacy models.
2. THE System SHALL not add new product features during cleanup.
3. THE System SHALL not change user-visible behavior beyond what is required by model conversion.
4. THE System SHALL not redesign URL structures or navigation during this spec — that is deferred to the UI derolification spec.
5. IF requested changes are unrelated to legacy model removal, THEN THE System SHALL defer them to a separate spec.
