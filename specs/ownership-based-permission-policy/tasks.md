# Implementation Plan

- [ ] 1. Establish centralized permission-policy framework
- [ ] 1.1 Integrate permission policy rollout with predecessor migration controls
  - Register authorization parity gates and rollback hooks
  - _Requirements: 1.1, 1.3, 1.4_
- [ ] 1.2 Implement central permission service entry points
  - Route listing/thread/watchlist authorization decisions through one policy layer
  - _Requirements: 6.1, 6.3_

- [ ] 2. Implement ownership and participation rule engine
- [ ] 2.1 Implement listing ownership authorization rules
  - Allow owner-only listing mutations and deterministic non-owner denials
  - _Requirements: 3.1, 3.2, 3.3, 3.4_
- [ ] 2.2 Implement messaging eligibility rules
  - Enforce self-message blocking and participant-only thread access
  - _Requirements: 4.1, 4.2, 4.3_
- [ ] 2.3 Implement watchlist ownership rules
  - Enforce user-only watchlist mutation rights
  - _Requirements: 5.1, 5.2, 5.3_

- [ ] 3. Remove role-based authorization dependencies
- [ ] 3.1 Refactor launch-critical endpoints to stop using role checks
  - Replace role branches with ownership/participant policy calls
  - _Requirements: 2.1, 2.2, 2.3_
- [ ] 3.2 Add compliance scanner for residual role-based auth branching
  - Block cutover when role-dependent checks remain
  - _Requirements: 2.2, 2.4, 7.3_

- [ ] 4. Add auditable denial and parity instrumentation
- [ ] 4.1 Emit structured denial records for policy decisions
  - Include deterministic reason codes for troubleshooting and parity analysis
  - _Requirements: 6.2, 6.4_
- [ ] 4.2 Implement legacy-vs-target permission parity checks
  - Compare outcomes during compatibility mode and flag drift
  - _Requirements: 1.2, 5.4, 7.3_

- [ ] 5. Implement policy cutover and rollback controls
- [ ] 5.1 Promote ownership policy to canonical authorization source
  - Gate promotion on parity and compliance success
  - _Requirements: 1.3, 2.4, 7.4_
- [ ] 5.2 Remove legacy role-based checks under cleanup gating
  - Only after predecessor destructive-change controls allow removal
  - _Requirements: 1.4, 8.1_

- [ ] 6. Checkpoint - Run permission policy validation suite
  - Verify owner/participant/watchlist auth outcomes and parity results

- [ ] 7. Final Checkpoint - Confirm scope boundaries
  - Confirm no unrelated feature work and no deferred marketplace capability work included
