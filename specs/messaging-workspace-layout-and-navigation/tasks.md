# Implementation Plan

## Phase 1 — Workspace Shell

- [ ] 1.1 Define workspace rendering contract (desktop vs mobile).
- [ ] 1.2 Establish selected-thread state and empty-thread behavior.
- [ ] 1.3 Align Messages nav entry with workspace root behavior.
- [ ] 1.4 Add thread-fragment Django view endpoint (returns partial thread HTML when called via `HX-Request`; used by `hx-get` on conversation row selection).
- [ ] 1.5 Add split-pane workspace layout classes to both skin files (`skin-simple-blue.css` and `skin-warm-editorial.css`) to satisfy skin-contract parity.

## Phase 2 — Responsive Navigation

- [ ] 2.1 Implement mobile list-to-thread navigation pattern.
- [ ] 2.2 Implement consistent back-to-list behavior on small screens.
- [ ] 2.3 Verify route/query state coherence across viewports.

## Phase 3 — Validation

- [ ] 3.1 Add template/view tests for desktop split contract.
- [ ] 3.2 Add template/view tests for mobile list/thread flow.
- [ ] 3.3 Add regression checks for existing message entry routes.
