# Implementation Plan

## Phase 1: Final Application Convergence (Reversible)

- [x] 1. Verify prerequisite readiness
- [x] 1.1 Confirm Features 1–6 are `EXEC`
  - _Requirements: 1_
- [x] 1.2 Run `migration_validate --scope all --fail-on-error`
  - Required scopes must pass: `counts`, `relationships`, `identity`, `listing`, `permission`, `messaging`, `discover`
  - _Requirements: 1, 7_
- [x] 1.3 Confirm system checkpoint is CP4
  - _Requirements: 1_

- [x] 2. Converge listing flows to `Listing` only
- [x] 2.1 Remove production-path `DemandPost`/`SupplyLot` imports and queries from views/forms/helpers
  - _Requirements: 2_
- [x] 2.2 Ensure listing CRUD/list/detail/toggle/delete flows run on `Listing` filtered by `type`
  - _Requirements: 2_
- [x] 2.3 Converge matching/suggestion/vector integrations to `Listing`
  - _Requirements: 2_

- [x] 3. Converge messaging/watchlist to canonical listing-centric schemas
- [x] 3.1 Ensure thread flows use `MessageThread(listing, created_by_user)` semantics only
  - Remove production usage of `buyer/supplier/watchlist_item`
  - _Requirements: 3_
- [x] 3.2 Ensure watchlist flows use `WatchlistItem(user, listing)` semantics only
  - Remove production usage of `supply_lot/demand_post`
  - _Requirements: 3_
- [x] 3.3 Ensure `ThreadReadState` references canonical listing-centric `MessageThread`
  - _Requirements: 5_
- [x] 3.4 Ensure discover/suggestion save-dismiss-message flows use canonical watchlist/thread linkage
  - _Requirements: 3_

- [x] 4. Remove role/org production dependencies
- [x] 4.1 Remove production references to `User.role` / `Role`
  - _Requirements: 4_
- [x] 4.2 Remove production references to `Organization`
  - _Requirements: 4_
- [x] 4.3 Keep `User.organization_name` as the only org identity field
  - _Requirements: 4_

- [x] 5. Add compliance blockers for cleanup
- [x] 5.1 Add scanner/parity coverage for legacy listing model dependencies in scoped production paths
  - _Requirements: 2, 7_
- [x] 5.2 Add scanner/parity coverage for legacy thread/watchlist field dependencies
  - _Requirements: 3, 7_
- [x] 5.3 Add scanner/parity coverage for role/org dependencies
  - _Requirements: 4, 7_

- [x] 6. Command/module integrity before destructive cleanup
- [x] 6.1 Update retained management commands so they do not import modules planned for removal
  - _Requirements: 6_
- [x] 6.2 Mark intentionally retired commands with explicit deprecation behavior/messages
  - No commands retired in Phase 1; retained command set audited and kept active.
  - _Requirements: 6_

- [x] 7. Phase 1 checkpoint
- [x] 7.1 Run full test suite
  - _Requirements: 7_
- [x] 7.2 Run `migration_validate --scope all --fail-on-error` again
  - _Requirements: 1, 7_

## Phase 2: Irreversible Cleanup (CP5)

- [x] 8. Execute preflight safety controls
- [x] 8.1 Capture and verify pre-cleanup database backup/snapshot
  - _Requirements: 5_
- [x] 8.2 Review/approve destructive migration plan and execution order
  - _Requirements: 5_

- [x] 9. Advance to CP5
- [x] 9.1 Run `migration_cutover --to CP5`
  - _Requirements: 1, 5_

- [x] 10. Apply cleanup migrations
- [x] 10.1 Remove `User.role`
  - _Requirements: 4, 5_
- [x] 10.2 Drop `Organization`
  - _Requirements: 4, 5_
- [x] 10.3 Drop legacy listing models/tables (`DemandPost`, `SupplyLot`)
  - _Requirements: 2, 5_
- [x] 10.4 Remove legacy linkage fields from `MessageThread` (`buyer`, `supplier`, `watchlist_item`)
  - _Requirements: 3, 5_
- [x] 10.5 Remove legacy split fields from `WatchlistItem` (`supply_lot`, `demand_post`) and keep listing-centric schema only
  - _Requirements: 3, 5_
- [x] 10.6 Finalize `DismissedSuggestion` listing FK-only schema
  - _Requirements: 2, 5_
- [x] 10.7 Apply migrations (`manage.py migrate`)
  - _Requirements: 5_

- [x] 11. Remove compatibility runtime shims
- [x] 11.1 Remove dual-write/dual-read signal behavior
  - _Requirements: 6_
- [x] 11.2 Remove compatibility adapters/repositories no longer used in production
  - _Requirements: 6_
- [x] 11.3 Remove or archive shim modules after command integrity is confirmed
  - _Requirements: 6_

- [x] 12. Post-cleanup validation
- [x] 12.1 Run full test suite
  - _Requirements: 7_
- [x] 12.2 Run migration/command smoke checks for retained command set
  - _Requirements: 6, 7_
- [x] 12.3 Validate absence of legacy role/org/listing constructs in production paths
  - _Requirements: 2, 4, 7_

- [x] 13. Final scope checkpoint
- [x] 13.1 Confirm no unrelated feature work was introduced
  - _Requirements: 8_
