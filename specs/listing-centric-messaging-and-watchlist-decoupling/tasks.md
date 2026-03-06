# Implementation Plan

- [ ] 1. Establish messaging/watchlist migration scaffolding
- [ ] 1.1 Register this spec with predecessor migration control gates
  - Add parity, integrity, and rollback gate checks for messaging/watchlist transitions
  - _Requirements: 1.1, 1.3, 1.4_
- [ ] 1.2 Add compatibility repository/coordinator interfaces
  - Centralize thread/watchlist transition behavior behind dedicated adapters
  - _Requirements: 1.2, 6.1, 6.3_

- [ ] 2. Implement listing-centric thread identity model
- [ ] 2.1 Enforce thread schema linkage to listing and initiator
  - Ensure owner is derived from listing ownership rather than explicit second participant FK
  - _Requirements: 2.1, 2.2, 2.3, 2.4_
- [ ] 2.2 Enforce unique `(listing_id, created_by_user_id)` thread constraint
  - Resolve duplicate initiation to existing thread deterministically
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 3. Implement auto-save semantics on message initiation
- [ ] 3.1 Coordinate thread creation and watchlist save behavior
  - Auto-create watchlist save when absent and avoid duplicate saves
  - _Requirements: 4.1, 4.2_
- [ ] 3.2 Enforce atomic user-visible outcome for initiation + autosave
  - Fail initiation safely if autosave requirements cannot be satisfied
  - _Requirements: 4.3, 4.4_

- [ ] 4. Implement watchlist/thread decoupling migration
- [ ] 4.1 Remove canonical runtime dependence on direct OneToOne link
  - Correlate by `(user, listing)` in target behavior
  - _Requirements: 5.1, 5.2_
- [ ] 4.2 Backfill legacy coupled records into independent target records
  - Record migration failures and block unsafe cutover
  - _Requirements: 5.3, 5.4, 7.2_

- [ ] 5. Preserve inbox/thread behavior parity through transition
- [ ] 5.1 Route inbox/thread flows through compatibility layer
  - Maintain unread and navigation parity while transitioning
  - _Requirements: 6.1, 6.2_
- [ ] 5.2 Add divergence detection and cutover gates
  - Block cutover on message retrieval/delivery parity regressions
  - _Requirements: 6.3, 6.4, 7.4_

- [ ] 6. Implement cutover and rollback controls
- [ ] 6.1 Promote listing-centric decoupled model to canonical path
  - Execute only after parity and integrity checks pass
  - _Requirements: 1.3, 7.3_
- [ ] 6.2 Keep rollback path and defer destructive cleanup
  - Remove legacy coupling only under predecessor destructive gates
  - _Requirements: 1.4, 8.1_

- [ ] 7. Checkpoint - Run messaging/watchlist migration validation suite
  - Run uniqueness, autosave, parity, and migration integrity tests

- [ ] 8. Final Checkpoint - Confirm scope boundaries
  - Confirm no unrelated discovery/profile/ranking changes and no deferred marketplace feature work
