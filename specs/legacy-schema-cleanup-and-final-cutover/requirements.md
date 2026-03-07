# Requirements Document

## Introduction

This spec defines the final migration phase: make unified `Listing` and listing-centric conversations/watchlists the only production architecture, then execute irreversible cleanup. It removes legacy role-based constructs and compatibility dual-read/dual-write shims while preserving product behavior.

## Dependencies

- **Required predecessor specs:** all six foundation specs must be `EXEC`:
  - `migration-safety-and-compatibility-rails`
  - `role-agnostic-user-and-org-flattening`
  - `unified-listing-model-and-status-contract`
  - `ownership-based-permission-policy`
  - `listing-centric-messaging-and-watchlist-decoupling`
  - `discover-direction-and-visibility-contract`
- CP4 must be reached before CP5.
- All CP4 parity gates must be passing before cleanup: `counts`, `relationships`, `identity`, `listing`, `permission`, `messaging`, `discover`.
- CP5 advancement is irreversible. Rollback to pre-cleanup state is not available after CP5 executes.

## Glossary

- **Legacy listing models**: `DemandPost`, `SupplyLot`
- **Legacy role/org constructs**: `User.role`, `Organization`
- **Legacy thread/watchlist linkage**: `MessageThread` fields `buyer/supplier/watchlist_item`, and `WatchlistItem` fields `supply_lot/demand_post`
- **Canonical post-cleanup models**:
  - `Listing`
  - `MessageThread` (listing-centric: `listing`, `created_by_user`; unique `(listing, created_by_user)`)
  - `WatchlistItem` (listing-centric: `user`, `listing`, status/source)
- **Compatibility shim**: code whose only purpose is dual-read/dual-write bridging during migration

## Requirements

### Requirement 1: Prerequisite and Gate Enforcement

#### Acceptance Criteria

1. WHEN cleanup begins, THE System SHALL verify passing parity reports for `counts`, `relationships`, `identity`, `listing`, `permission`, `messaging`, and `discover`.
2. IF any required gate is failing, THEN THE System SHALL block CP5 advancement and cleanup migration.
3. WHEN the system is not at CP4, THEN THE System SHALL block CP5 advancement.
4. WHEN CP5 is advanced, THEN THE System SHALL persist an explicit irreversible-cutover state transition record.

### Requirement 2: Convert Production Code to Unified Listing

#### Acceptance Criteria

1. THE System SHALL remove production-path imports/queries of `DemandPost` and `SupplyLot`.
2. Listing create/edit/toggle/delete/detail/list flows SHALL operate on `Listing` filtered by `type`.
3. Matching, suggestions, and vector-search integration SHALL operate on `Listing`.
4. IF any production path still depends on `DemandPost`/`SupplyLot`, THEN cleanup SHALL be blocked.

### Requirement 3: Canonicalize Messaging and Watchlist Models

#### Acceptance Criteria

1. Messaging flows SHALL operate on listing-centric `MessageThread` semantics (`listing`, `created_by_user`) with no participant-role FKs.
2. Watchlist flows SHALL operate on listing-centric `WatchlistItem` semantics (`user`, `listing`) with no supply/demand split FKs.
3. THE System SHALL preserve existing user-visible messaging/watchlist behavior.
4. Inbox, thread detail, watchlist, discover save/unsave/message, and suggestion save/dismiss/message flows SHALL use canonical listing-centric models only.

### Requirement 4: Remove Role and Organization Constructs

#### Acceptance Criteria

1. THE System SHALL remove `User.role` via migration.
2. THE System SHALL remove `Organization` via migration.
3. THE System SHALL remove production references to `Role` and `Organization`.
4. `User.organization_name` SHALL remain as the org identity field.

### Requirement 5: Execute Destructive Schema Cleanup Safely

#### Acceptance Criteria

1. BEFORE CP5 advancement, THE System SHALL require:
   - a verified pre-cleanup database backup/snapshot checkpoint
   - a reviewed migration plan for destructive operations
2. AFTER CP5 advancement, THE System SHALL apply an irreversible cleanup migration dropping legacy listing/role/org schemas and obsolete thread/watchlist legacy fields/tables.
3. THE System SHALL preserve migration audit records (`MigrationState`, `LegacyToTargetMapping`, `BackfillAuditRecord`, `ParityReport`).
4. The final state SHALL choose one `ThreadReadState` outcome and implement it consistently:
   - retained and pointed at canonical listing-centric threads, or
   - removed and replaced by a defined alternative.

### Requirement 6: Remove or Retire Compatibility Shims with Operational Integrity

#### Acceptance Criteria

1. THE System SHALL remove dual-write/dual-read runtime shims from production paths.
2. Any management command kept for audit/operations SHALL continue to run without importing deleted shim modules.
3. If a command is intentionally retired post-cleanup, THEN the retirement SHALL be explicit in docs and command output.
4. Core migration governance components (`state`, `checkpoints`, `parity`, `permission/discover compliance`) SHALL be retained.

### Requirement 7: Validation and Regression

#### Acceptance Criteria

1. THE System SHALL include regression tests for unified listing CRUD and listing-type-specific behavior.
2. THE System SHALL include regression tests for listing-centric messaging/watchlist behavior.
3. THE System SHALL include tests asserting legacy role/org constructs are gone.
4. THE System SHALL include compliance checks that block CP5 when legacy model dependencies remain in scoped production paths.
5. Full test suite SHALL pass before and after destructive cleanup.

### Requirement 8: Scope Boundaries

#### Acceptance Criteria

1. Scope SHALL be limited to final migration, cleanup, and behavior-preserving refactors.
2. No deferred marketplace features (payments, escrow, auctions/bidding, logistics) SHALL be added.
3. URL/navigation redesign and broad copy overhaul SHALL remain out of scope for this spec.
