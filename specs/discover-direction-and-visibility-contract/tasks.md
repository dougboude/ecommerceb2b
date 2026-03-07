# Implementation Plan

- [x] 1. Establish discover migration scaffolding
- [x] 1.1 Register discover cutover gates with predecessor migration controls
  - Add discover parity and rollback gate checks
  - _Requirements: 1.1, 1.3, 1.4_
- [x] 1.2 Add discover compatibility validation harness
  - Enable legacy-vs-target discover behavior comparisons during transition
  - _Requirements: 1.2, 7.3_

- [x] 2. Implement explicit direction state management
- [x] 2.1 Add discover direction selection contract
  - Support `Find Supply` and `Find Demand` as explicit authenticated-user choices
  - _Requirements: 2.1, 2.2_
- [x] 2.2 Persist direction with discover session state
  - Store and reuse direction across discover workflow actions
  - _Requirements: 2.3, 4.1, 4.2_
- [x] 2.3 Implement clear/reset behavior for direction state
  - Clear persisted direction and linked discover state on Clear Search
  - _Requirements: 4.3, 4.4_

- [x] 3. Implement direction-aware query behavior
- [x] 3.1 Enforce counterpart type filtering from direction selection
  - Query `SUPPLY` for Find Supply and `DEMAND` for Find Demand
  - _Requirements: 3.1, 3.2_
- [x] 3.2 Keep shared search infrastructure across directions
  - Use same keyword/semantic pipeline with direction-specific type filter only
  - _Requirements: 3.3, 3.4_

- [x] 4. Implement visibility contract enforcement
- [x] 4.1 Enforce active-listing discoverability for authenticated users
  - Ensure active counterpart listings are discoverable under selected direction and filters
  - _Requirements: 5.1_
- [x] 4.2 Prevent suggestions from acting as access gates
  - Ensure no-valid-suggestion state does not suppress valid active listings
  - _Requirements: 5.2, 5.4_
- [x] 4.3 Enforce non-active status exclusion
  - Exclude paused/expired/deleted listings according to status contract
  - _Requirements: 5.3_

- [x] 5. Remove role-inferred discover assumptions
- [x] 5.1 Refactor discover paths to eliminate role-based direction inference
  - Block cutover if residual role-inferred branching remains
  - _Requirements: 6.1, 6.2, 6.4_
- [x] 5.2 Preserve discover parity during compatibility window
  - Validate no launch-critical discover regressions during staged rollout
  - _Requirements: 6.3, 7.4_

- [x] 6. Checkpoint - Run discover validation suite
  - Run direction-state, query-filter, visibility, and parity test suites

- [x] 7. Final Checkpoint - Confirm scope boundaries
  - Confirm no unrelated ranking/ML expansion and no deferred marketplace feature work included
