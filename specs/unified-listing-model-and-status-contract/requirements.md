# Requirements Document

## Introduction

This spec defines the transition from split listing models (`DemandPost`, `SupplyLot`) to a single unified `Listing` model with `type` and shared status semantics. The goal is to establish one canonical listing architecture while preserving current product behavior through staged migration. This spec covers model shape, validation, data consistency, and compatibility behavior for listing-domain architecture only.

## Dependencies

- **Required predecessor spec:** `migration-safety-and-compatibility-rails`
- This spec SHALL comply with additive-first schema rules, compatibility controls, checkpoint gates, cutover sequencing, and rollback procedures defined by `migration-safety-and-compatibility-rails`.
- Any destructive listing-schema operation is prohibited until predecessor cutover and cleanup gates allow it.

## Glossary

- **Unified Listing Model**: Single `Listing` entity representing both supply and demand via `type`.
- **Listing Type**: Enum value `SUPPLY` or `DEMAND` determining type-specific field semantics.
- **Base Fields**: Shared listing fields valid for all listing types.
- **Type-Specific Fields**: Nullable columns valid only for one listing type.
- **Status Contract**: Shared status field with type-specific validity rules.
- **Behavior Parity**: No user-visible regression in listing create/edit/view/delete/toggle and discovery compatibility.

## Requirements

### Requirement 1: Enforce Migration Dependency and Safe Sequencing

**User Story:** As a platform operator, I want listing unification constrained by migration safety rails, so architecture changes remain reversible until proven stable.

#### Acceptance Criteria

1. WHEN this spec executes, THE System SHALL require dependency on `migration-safety-and-compatibility-rails` for all schema and data transitions.
2. WHILE compatibility mode is active, THE System SHALL keep legacy listing paths operational under predecessor rules.
3. IF checkpoint gates fail, THEN THE System SHALL block listing cutover and execute predecessor rollback/hold behavior.
4. WHEN cleanup is requested, THE System SHALL permit destructive legacy listing removal only after predecessor destructive-change gates pass.

### Requirement 2: Define Canonical Unified Listing Schema

**User Story:** As a maintainer, I want one listing model with explicit type semantics, so listing behavior is consistent and extensible.

#### Acceptance Criteria

1. THE System SHALL provide a single canonical listing entity with `type` set to `SUPPLY` or `DEMAND`.
2. THE System SHALL include shared base fields for title, description, category, status, location, price fields, timestamps, and ownership.
3. THE System SHALL store type-specific attributes in nullable columns on the same table rather than JSON subtype blobs or multi-table inheritance.
4. WHEN a listing type does not use a type-specific field, THE System SHALL store null for that field.

### Requirement 3: Enforce Type-Specific Field and Status Validation

**User Story:** As a quality owner, I want strict type/status constraints, so invalid listing states are prevented.

#### Acceptance Criteria

1. WHEN `type = SUPPLY`, THE System SHALL allow supply-specific fields and enforce demand-only fields as null.
2. WHEN `type = DEMAND`, THE System SHALL allow demand-specific fields and enforce supply-only fields as null.
3. WHEN status is set to `FULFILLED`, THE System SHALL allow it only for demand listings.
4. WHEN status is set to `WITHDRAWN`, THE System SHALL allow it only for supply listings.

### Requirement 4: Preserve Existing Listing Behavior During Compatibility Window

**User Story:** As an end user, I want listing workflows to remain stable during migration, so backend refactors do not disrupt usage.

#### Acceptance Criteria

1. WHILE migration compatibility mode is active, THE System SHALL preserve behavior parity for listing create, edit, detail, toggle, and delete workflows.
2. WHEN dual-path listing persistence is enabled, THE System SHALL maintain consistent user-visible outcomes across legacy and target models.
3. IF target listing writes diverge from legacy writes, THEN THE System SHALL record divergence and block unsafe checkpoint advancement.
4. WHEN parity validation runs, THE System SHALL verify listing behavior parity before cutover is allowed.

### Requirement 5: Deterministic Listing Data Backfill and Mapping

**User Story:** As a platform operator, I want deterministic mapping from legacy listing models to unified listings, so data integrity is preserved.

#### Acceptance Criteria

1. WHEN backfill executes, THE System SHALL deterministically map each `DemandPost` and `SupplyLot` record to exactly one unified listing record.
2. THE System SHALL preserve ownership, created/expiry timestamps, category, status, and location/price semantics during mapping.
3. IF a legacy record cannot be transformed to a valid unified listing, THEN THE System SHALL log record-level failure details and block cutover.
4. WHEN backfill completes, THE System SHALL produce parity evidence for record counts and critical field distributions.

### Requirement 6: Canonical Cutover to Unified Listings

**User Story:** As a release manager, I want explicit listing cutover criteria, so the canonical listing source switches safely.

#### Acceptance Criteria

1. WHEN cutover is initiated, THE System SHALL switch canonical listing reads to unified listings before disabling legacy listing writes.
2. WHILE rollback window remains open, THE System SHALL retain compliant fallback behavior per predecessor rules.
3. IF post-cutover listing validations fail, THEN THE System SHALL execute rollback to the prior approved checkpoint.
4. WHEN rollback window closes successfully, THE System SHALL allow legacy listing schema cleanup under predecessor controls.

### Requirement 7: Testing and Validation Scope

**User Story:** As a quality owner, I want dedicated listing-unification validation, so regressions are detected before launch-critical phases.

#### Acceptance Criteria

1. THE System SHALL include automated tests for unified listing validation rules, including type-specific field and status constraints.
2. THE System SHALL include migration/backfill tests for deterministic legacy-to-unified mapping and replay idempotency.
3. THE System SHALL include integration tests for listing CRUD and discovery compatibility across compatibility and cutover stages.
4. IF any launch-critical listing parity test fails, THEN THE System SHALL block checkpoint advancement.

### Requirement 8: Scope Boundaries and Non-Goals

**User Story:** As a product owner, I want this spec focused on listing architecture, so unrelated features do not increase migration risk.

#### Acceptance Criteria

1. THE System SHALL limit scope to unified listing schema, validation, migration behavior, and cutover compliance.
2. THE System SHALL not include deferred capabilities such as payments, escrow, auctions, bidding, or logistics.
3. THE System SHALL not introduce unrelated product behavior changes beyond what is required for listing architecture alignment.
4. IF requested work falls outside listing architecture migration scope, THEN THE System SHALL defer it to another spec.
