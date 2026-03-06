# Implementation Plan

- [ ] 1. Establish identity migration scaffolding under migration safety rails
- [ ] 1.1 Wire this spec into migration control-plane checkpoints
  - Register identity-specific checkpoint gates with predecessor migration controls
  - Ensure cutover/cleanup operations are blocked until required predecessor gates pass
  - _Requirements: 1.1, 1.2, 1.3, 1.4_
- [ ] 1.2 Add identity compatibility adapters
  - Create centralized dual-read/dual-write adapters for user and organization identity reads/writes
  - Route launch-critical auth/profile identity access through adapters
  - _Requirements: 2.2, 4.1, 4.2, 6.2_

- [ ] 2. Implement target user schema for org flattening
- [ ] 2.1 Add `organization_name` to target user schema with explicit constraints
  - Enforce optional field semantics and deterministic normalization of empty values
  - Apply explicit max-length validation
  - _Requirements: 3.1, 5.1, 5.2, 5.4_
- [ ] 2.2 Implement deterministic org-name backfill
  - Map legacy organization values into `User.organization_name`
  - Log conflict resolution outcomes for ambiguous legacy records
  - _Requirements: 3.2, 3.3, 7.1_
- [ ] 2.3 Add runtime read preference for flattened organization data
  - Prefer `User.organization_name` on target paths with compatibility fallback per migration controls
  - _Requirements: 3.1, 4.3, 6.1_

- [ ] 3. Remove role-based identity dependencies
- [ ] 3.1 Refactor identity/auth/profile paths to eliminate `User.role` branching
  - Replace role-derived behavior with action/ownership-neutral behavior where required
  - Add compliance checks that flag remaining role-based identity branching
  - _Requirements: 2.1, 2.3, 2.4, 7.3_
- [ ] 3.2 Remove runtime dependencies on `Organization.type`
  - Ensure profile and identity display paths no longer depend on organization-type semantics
  - _Requirements: 3.4, 6.2, 6.3_

- [ ] 4. Preserve behavior parity through compatibility and cutover
- [ ] 4.1 Validate launch-critical identity behavior parity
  - Test signup, login, logout, profile view, and profile edit outcomes across compatibility states
  - _Requirements: 4.1, 4.2, 4.4, 7.2_
- [ ] 4.2 Implement identity cutover and rollback hooks
  - Switch canonical identity reads/writes to target path only after parity gates pass
  - Add rollback execution path per predecessor checkpoint model
  - _Requirements: 2.4, 6.4, 7.4_

- [ ] 5. Checkpoint - Run identity migration validations
  - Run schema, backfill, and parity test suites for this spec
  - Confirm compliance scan reports no remaining role-based identity dependencies

- [ ] 6. Final Checkpoint - Confirm cleanup readiness
  - Verify legacy role/org structures are only marked removable under predecessor destructive gates
  - Verify this spec remains within scope and excludes deferred marketplace capabilities
