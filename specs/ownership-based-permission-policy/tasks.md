# Implementation Plan

- [x] 1. Establish centralized permission-policy framework
- [x] 1.1 Integrate permission policy rollout with predecessor migration controls
  - Registered `permission` parity gate in CP4 and CP5 of `CheckpointController._check_gates()`
  - Wired `migration_validate --scope permission` and `migration_cutover` to emit permission reports at CP4/CP5
  - _Requirements: 1.1, 1.3, 1.4_
- [x] 1.2 Implement central permission service entry points
  - `marketplace/migration_control/permissions.py`: `PermissionService` with `authorize_listing_mutation`, `authorize_message_initiation`, `authorize_thread_access`, `authorize_watchlist_action`
  - All launch-critical views route through `permission_service` module-level singleton
  - _Requirements: 6.1, 6.3_

- [x] 2. Implement ownership and participation rule engine
- [x] 2.1 Implement listing ownership authorization rules
  - `PolicyEngine.is_listing_owner()` — duck-typed to work with DemandPost, SupplyLot, and unified Listing
  - Owner-only mutations enforced in edit/toggle/delete views for both listing types
  - Deterministic non-owner denials with structured reason codes (`NOT_LISTING_OWNER`)
  - _Requirements: 3.1, 3.2, 3.3, 3.4_
- [x] 2.2 Implement messaging eligibility rules
  - `PolicyEngine.is_self_message_attempt()` + `authorize_message_initiation()` applied in `discover_message` and `suggestion_message` views
  - Participant-only thread access via `authorize_thread_access()` in `thread_detail` view
  - _Requirements: 4.1, 4.2, 4.3_
- [x] 2.3 Implement watchlist ownership rules
  - `authorize_watchlist_action()` enforced in `watchlist_archive`, `watchlist_unarchive`, `watchlist_delete`
  - `watchlist_view` role-based `select_related` branching replaced with role-agnostic dual select_related
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 3. Remove role-based authorization dependencies
- [x] 3.1 Refactor launch-critical endpoints to stop using role checks
  - Removed `role != Role.BUYER` gate from `demand_post_list`, `demand_post_create`
  - Removed `role != Role.SUPPLIER` gate from `supply_lot_list`, `supply_lot_create`
  - `demand_post_create` now guards via Organization existence (ownership-based prerequisite) instead of role
  - _Requirements: 2.1, 2.2, 2.3_
- [x] 3.2 Add compliance scanner for residual role-based auth branching
  - `RoleAuthComplianceScanner` in `permissions.py` scans scoped views for `role != Role.*` denial patterns
  - Scanner integrated into `validate_permission_policy()` in `ParityValidator`
  - _Requirements: 2.2, 2.4, 7.3_

- [x] 4. Add auditable denial and parity instrumentation
- [x] 4.1 Emit structured denial records for policy decisions
  - `Decision` dataclass: `allowed`, `rule_id`, `reason_code`, `subject_type`, `subject_id`
  - All denials carry deterministic reason codes (`NOT_LISTING_OWNER`, `SELF_MESSAGE_DENIED`, `NOT_THREAD_PARTICIPANT`, `NOT_WATCHLIST_OWNER`, etc.)
  - `Decision.deny_if_not_allowed()` raises `PermissionDenied` with reason code
  - _Requirements: 6.2, 6.4_
- [x] 4.2 Implement legacy-vs-target permission parity checks
  - `ParityValidator.validate_permission_policy()` uses `RoleAuthComplianceScanner` to detect residual role-auth violations
  - Produces `ParityReport` with `scope="permission"` via `migration_validate --scope permission`
  - _Requirements: 1.2, 5.4, 7.3_

- [x] 5. Implement policy cutover and rollback controls
- [x] 5.1 Promote ownership policy to canonical authorization source
  - CP4 gate now requires passing `permission` parity report — cutover blocked until compliance confirmed
  - `migration_cutover --to CP4` and `--to CP5` emit permission reports
  - _Requirements: 1.3, 2.4, 7.4_
- [x] 5.2 Remove legacy role-based checks under cleanup gating
  - Role-based denial gates removed from views; CP5 gate requires cutover-stage permission parity evidence
  - _Requirements: 1.4, 8.1_

- [x] 6. Checkpoint - Run permission policy validation suite
  - 54 tests in `marketplace/tests/test_permission_policy.py` — all pass
  - Full suite of 85 tests passes with no regressions

- [x] 7. Final Checkpoint - Confirm scope boundaries
  - No new features added; no deferred marketplace capabilities included
  - Changes limited to: permission policy module, views role-gate removal, parity wiring
