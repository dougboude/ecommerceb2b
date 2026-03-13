# Implementation Plan

## Phase 1 — Audit and Contract Definition

- [ ] 1.1 Audit current feedback messages across discover/listing/watchlist/messaging/profile/auth flows.
- [ ] 1.2 Create a feedback contract matrix (action -> success/error message -> recovery path).
- [ ] 1.3 Audit empty-state pages and mark missing primary CTAs.

## Phase 2 — Template and View Alignment

- [ ] 2.1 Standardize message emission in key views for outcome consistency.
- [ ] 2.2 Add/normalize primary CTA on empty states for discover/watchlist/inbox/list pages/auth recovery pages.
- [ ] 2.3 Normalize confirmation patterns for destructive actions.

## Phase 3 — Validation

- [ ] 3.1 Add tests for feedback presence on representative actions.
- [ ] 3.2 Add tests for empty-state CTA presence and target URLs.
- [ ] 3.3 Add tests for confirm/cancel return path behavior.
- [ ] 3.4 Run full regression suite.

## Phase 4 — Completion

- [ ] 4.1 Update tracking status and session notes.
