# Implementation Plan

## Pre-Execution Checklist

- [ ] 0.1 Confirm `requirements.md` and `design.md` are approved.
- [ ] 0.2 Confirm this feature is sequenced per `docs/SPEC_ORDER.md`.
- [ ] 0.3 Confirm branch cut from latest `main`.

---

## Phase 1 — Navigation Contract Baseline

### Group 1 — Central Route-to-Section Mapping

- [ ] 1.1 Update `marketplace/context_processors.py` `nav_section()` mapping to current canonical route families.
  - Ensure mappings include `/`, `/discover`, `/watchlist`, `/messages`, `/threads`, `/profile`, `/available`, `/wanted`.
  - Remove or de-prioritize obsolete prefixes that do not reflect current routes.
  - _Requirements: 2, 3_

- [ ] 1.2 Add explicit fallback behavior for unknown paths.
  - Ensure unknown paths do not produce misleading active-state highlights.
  - _Requirements: 2_

### Group 2 — Global Nav Canonical Labels and Destinations

- [ ] 2.1 Normalize authenticated global nav in `templates/includes/_navbar.html`.
  - Confirm canonical destinations and labels: Discover, Messages, Watchlist, Supply, Demand, Profile, Log out.
  - _Requirements: 1, 6_

- [ ] 2.2 Normalize unauthenticated nav contract in `_navbar.html`.
  - Keep unauthenticated access links clear and minimal (`Log in`, `Sign up`).
  - _Requirements: 1_

---

## Phase 2 — Contextual Navigation and Dead-End Removal

### Group 3 — Empty-State CTA Standardization

- [ ] 3.1 Audit major user-facing empty states and add a clear primary CTA where missing.
  - Pages to review at minimum: inbox, watchlist, supply list, demand list, discover no-results, auth verification states.
  - _Requirements: 4_

- [ ] 3.2 Ensure CTA destination targets the immediate next likely task.
  - Examples: Watchlist empty -> Discover, listing empty -> create listing flow, inbox empty -> discover/watchlist messaging path.
  - _Requirements: 4_

### Group 4 — Contextual Return Path Consistency

- [ ] 4.1 Validate and normalize “back” actions in key flows.
  - Listing detail -> list
  - Thread detail -> messages
  - Form cancel -> appropriate list/detail parent
  - Delete confirm cancel -> detail
  - _Requirements: 5_

- [ ] 4.2 Ensure contextual action flow remains coherent between discover/listings/watchlist/messages.
  - Verify no orphan action routes the user to unrelated pages after completion.
  - _Requirements: 5, 7_

---

## Phase 3 — Validation and Regression Safety

### Group 5 — Automated Test Coverage

- [ ] 5.1 Add tests for nav active-state mapping.
  - Cover canonical route families and nested/detail paths.
  - Ensure `/threads/*` maps to `messages`; `/available/*` and `/wanted/*` map to listings section.
  - _Requirements: 2, 3_

- [ ] 5.2 Add tests for unknown-path behavior.
  - Assert no incorrect nav active-state is rendered.
  - _Requirements: 2_

- [ ] 5.3 Add tests (or template assertions) for empty-state primary CTA presence on major pages.
  - _Requirements: 4_

- [ ] 5.4 Add integration checks for contextual transitions.
  - Verify expected back/return targets in listing, thread, and form flows.
  - _Requirements: 5_

### Group 6 — Manual UX Smoke Pass

- [ ] 6.1 Run manual smoke checks across major journeys:
  - Auth entry -> dashboard/discover path
  - Discover -> listing detail -> message thread
  - Watchlist -> listing/thread
  - Supply/Demand list -> detail/edit/delete-confirm
  - _Requirements: 1–6_

- [ ] 6.2 Confirm no permission or business-logic regressions.
  - Listing mutation permissions unchanged
  - Messaging access permissions unchanged
  - _Requirements: 7_

---

## Phase 4 — Completion and Handoff

- [ ] 7.1 Update feature status tracking once implemented (`REQ, DES, TASK, EXEC` as appropriate).
- [ ] 7.2 Update `ai-docs/SESSION_STATUS.md` with implemented navigation/IA changes and validation evidence.
- [ ] 7.3 Record any deferred IA follow-ups (for example future combined listings hub) as separate backlog items, not in-scope changes.

