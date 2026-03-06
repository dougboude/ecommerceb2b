# Implementation Plan

- [x] 1. Establish listing-unification migration scaffolding
- [x] 1.1 Register listing spec gates with predecessor migration controls
  - Define listing-specific checkpoint validations and rollback triggers
  - _Requirements: 1.1, 1.3, 1.4_
- [x] 1.2 Add listing compatibility repository interfaces
  - Centralize listing reads/writes through compatibility adapter layer
  - _Requirements: 1.2, 4.2, 6.2_

- [x] 2. Implement unified `Listing` target schema
- [x] 2.1 Add base listing fields and type enum contract
  - Introduce canonical `type` with `SUPPLY|DEMAND`
  - Preserve shared base field semantics for both listing types
  - _Requirements: 2.1, 2.2_
- [x] 2.2 Add nullable type-specific columns in single-table design
  - Enforce null storage for non-applicable type fields
  - _Requirements: 2.3, 2.4_
- [x] 2.3 Implement type-specific field validation rules
  - Enforce supply-only and demand-only field validity constraints
  - _Requirements: 3.1, 3.2_
- [x] 2.4 Implement status contract validation
  - Enforce `FULFILLED` only for demand and `WITHDRAWN` only for supply
  - _Requirements: 3.3, 3.4_

- [x] 3. Implement deterministic legacy listing backfill
- [x] 3.1 Map `DemandPost` and `SupplyLot` records into unified listing rows
  - Preserve ownership, category, status, timestamps, and location/price semantics
  - _Requirements: 5.1, 5.2_
- [x] 3.2 Add mapping/audit persistence for backfill traceability
  - Record per-record failures and block unsafe cutover when needed
  - _Requirements: 5.3, 5.4_
- [x]* 3.3 Add idempotent replay support tests for backfill
  - Verify deterministic outcomes over repeated runs
  - _Requirements: 5.1, 7.2_

- [x] 4. Preserve listing behavior parity through transition
- [x] 4.1 Route listing CRUD paths through compatibility repository
  - Maintain consistent user-visible outcomes during dual-path operation
  - _Requirements: 4.1, 4.2, 4.3_
- [x] 4.2 Add listing parity validation for cutover readiness
  - Verify create/edit/detail/toggle/delete and discover retrieval parity
  - _Requirements: 4.4, 7.3, 7.4_

- [x] 5. Implement listing cutover and rollback sequence
- [x] 5.1 Switch canonical listing reads to unified model
  - Perform switch only after parity gates pass
  - _Requirements: 6.1, 6.2_
- [x] 5.2 Disable legacy listing writes and enable rollback window behavior
  - Ensure rollback path is available until cleanup gate approval
  - _Requirements: 6.2, 6.3_
- [x] 5.3 Mark legacy listing schema for cleanup under predecessor controls
  - _Requirements: 1.4, 6.4_

- [x] 6. Checkpoint - Run listing-unification validation suite
  - Run schema, mapping, validation, parity, and rollback tests

- [x] 7. Final Checkpoint - Confirm scope and readiness
  - Verify no unrelated feature expansion and no deferred marketplace features included
