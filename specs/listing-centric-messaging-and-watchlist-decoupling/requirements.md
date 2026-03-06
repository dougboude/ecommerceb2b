# Requirements Document

## Introduction

This spec defines messaging and watchlist architecture alignment around listings rather than roles, including thread identity, initiation rules, and watchlist/thread decoupling. The goal is to preserve current user-facing behavior while transitioning to listing-centric conversation semantics. This spec covers message thread schema semantics, initiation behavior, watchlist linkage rules, and migration-safe validation.

## Dependencies

- **Required predecessor spec:** `migration-safety-and-compatibility-rails`
- This spec SHALL execute under the predecessor’s additive migration, compatibility controls, checkpoint gates, cutover sequence, and rollback requirements.
- Destructive changes to legacy thread/watchlist linkage SHALL remain blocked until predecessor cleanup gates permit removal.

## Glossary

- **Listing-Centric Thread**: Conversation thread anchored to a listing rather than a role pairing.
- **Thread Initiator**: User who starts a listing thread (`created_by_user_id` on thread).
- **Listing Owner**: User who created the listing (`listing.created_by_user`).
- **Thread Uniqueness Rule**: One thread per `(listing_id, created_by_user_id)` pair.
- **Auto-Save on Message Start**: Initiating a thread saves the listing to initiator watchlist when absent.
- **Watchlist/Thread Decoupling**: `WatchlistItem` and `MessageThread` remain independent records without direct OneToOne linkage.

## Requirements

### Requirement 1: Enforce Migration Dependency and Safe Messaging Cutover

**User Story:** As a platform operator, I want messaging architecture changes gated by migration safety rails, so cutover remains reversible and low risk.

#### Acceptance Criteria

1. WHEN this spec is implemented, THE System SHALL require dependency on `migration-safety-and-compatibility-rails` for sequencing and rollback safety.
2. WHILE compatibility mode is active, THE System SHALL preserve current messaging and watchlist user-visible behavior.
3. IF messaging parity or integrity checks fail, THEN THE System SHALL block cutover and follow predecessor rollback/hold rules.
4. WHEN cleanup is proposed, THE System SHALL permit destructive legacy linkage removal only under predecessor cleanup gates.

### Requirement 2: Enforce Listing-Centric Thread Identity Model

**User Story:** As a user, I want conversations scoped to listings, so messaging context stays tied to the relevant listing.

#### Acceptance Criteria

1. WHEN a thread is created, THE System SHALL associate the thread to exactly one listing.
2. THE System SHALL record the initiator as `created_by_user_id` and derive listing owner from the listing record.
3. THE System SHALL not require an explicit second-participant foreign key when owner is derivable from listing ownership.
4. IF thread creation lacks valid listing reference or initiator identity, THEN THE System SHALL reject thread creation deterministically.

### Requirement 3: Enforce One-Thread-Per-Initiator-Per-Listing Rule

**User Story:** As a user, I want thread uniqueness per listing/initiator pair, so duplicate conversations do not fragment context.

#### Acceptance Criteria

1. WHEN a user initiates messaging for a listing, THE System SHALL enforce uniqueness for `(listing_id, created_by_user_id)`.
2. IF an existing thread already matches the pair, THEN THE System SHALL resolve to the existing thread instead of creating a duplicate.
3. WHEN concurrent initiation attempts occur for the same pair, THE System SHALL maintain uniqueness without creating multiple threads.
4. WHILE compatibility mode is active, THE System SHALL preserve current user-visible outcomes for repeated message initiation.

### Requirement 4: Enforce Auto-Save Behavior on Thread Initiation

**User Story:** As a user, I want initiating a conversation to automatically save the listing, so discussion and saved context remain aligned.

#### Acceptance Criteria

1. WHEN a thread is initiated, THE System SHALL create a watchlist save for that listing and initiator if none exists.
2. IF a valid watchlist save already exists for the same user/listing pair, THEN THE System SHALL not create a duplicate save.
3. WHILE thread creation succeeds, THE System SHALL ensure linked save semantics complete in the same user-visible transaction outcome.
4. IF auto-save cannot be completed safely, THEN THE System SHALL fail initiation with deterministic error behavior rather than creating partial state.

### Requirement 5: Decouple WatchlistItem and MessageThread Data Models

**User Story:** As a maintainer, I want watchlist and thread records independent, so each lifecycle can evolve without rigid coupling.

#### Acceptance Criteria

1. THE System SHALL treat `WatchlistItem` and `MessageThread` as independent records correlated by `(user, listing)` when needed.
2. THE System SHALL not require a direct OneToOne foreign key between watchlist and thread records in target architecture.
3. WHEN legacy coupled data is migrated, THE System SHALL backfill equivalent independent records without data loss.
4. IF migration detects inconsistent coupling state, THEN THE System SHALL log record-level failures and block unsafe checkpoint advancement.

### Requirement 6: Preserve Inbox/Thread Behavior Parity During Transition

**User Story:** As a user, I want message inbox and thread behavior to remain stable during migration, so communication remains reliable.

#### Acceptance Criteria

1. WHILE compatibility mode is active, THE System SHALL preserve inbox listing, unread-state behavior, and thread navigation parity.
2. WHEN thread ownership/participation is evaluated, THE System SHALL enforce participant access consistently with listing-centric rules.
3. IF message delivery or thread retrieval diverges across legacy and target paths, THEN THE System SHALL record divergence and block cutover.
4. WHEN pre-cutover validation runs, THE System SHALL confirm parity for launch-critical messaging and watchlist interaction flows.

### Requirement 7: Testing and Validation Requirements

**User Story:** As a quality owner, I want dedicated messaging/watchlist migration tests, so architecture refactor regressions are prevented.

#### Acceptance Criteria

1. THE System SHALL include automated tests for thread identity, uniqueness, auto-save semantics, and watchlist/thread decoupling.
2. THE System SHALL include migration tests that verify deterministic backfill from legacy coupling to independent target records.
3. THE System SHALL include integration tests for inbox/thread/watchlist user journeys across compatibility and cutover stages.
4. IF launch-critical messaging parity tests fail, THEN THE System SHALL block checkpoint advancement.

### Requirement 8: Scope Boundaries and Non-Goals

**User Story:** As a product owner, I want this spec focused on messaging/watchlist architecture alignment, so migration risk remains contained.

#### Acceptance Criteria

1. THE System SHALL limit scope to listing-centric messaging semantics and watchlist/thread decoupling required for architecture alignment.
2. THE System SHALL not include deferred capabilities such as payments, escrow, auctions, bidding, or logistics.
3. THE System SHALL not introduce unrelated discovery, profile, or ranking features in this spec.
4. IF requested work is outside messaging/watchlist architecture migration scope, THEN THE System SHALL defer it.
