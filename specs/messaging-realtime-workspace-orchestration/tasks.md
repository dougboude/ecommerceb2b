# Implementation Plan

## Phase 1 — Client Update Engine

- [ ] 1.1 Implement row lookup/update path for existing rows.
- [ ] 1.2 Implement missing-row creation path.
- [ ] 1.3 Implement empty-state replacement behavior.

## Phase 2 — Group and Ordering Engine

- [ ] 2.1 Implement missing-group creation path.
- [ ] 2.2 Implement deterministic reorder logic for rows/groups.
- [ ] 2.3 Add deduplication/idempotency guards for burst events.

## Phase 3 — Validation

- [ ] 3.1 Add JavaScript/unit tests for create/update/reorder flows.
- [ ] 3.2 Add integration tests for absent-row and absent-group scenarios.
- [ ] 3.3 Add regression tests for nav unread and thread-page updates.
