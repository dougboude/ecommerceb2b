# Implementation Plan

## Phase 1 — Flow Audit

- [ ] 1.1 Map current transitions across signup/login/verify/resend pages.
- [ ] 1.2 Identify dead-end or ambiguous auth states.

## Phase 2 — Template/View Alignment

- [ ] 2.1 Normalize auth state CTAs for clear progression.
- [ ] 2.2 Ensure unverified login block path clearly points to resend flow.
- [ ] 2.3 Standardize auth messaging tone and outcome language.

## Phase 3 — Validation

- [ ] 3.1 Add integration tests for signup -> verify -> login progression.
- [ ] 3.2 Add tests for expired/used token routes and recovery CTAs.
- [ ] 3.3 Run full regression suite.

## Phase 4 — Completion

- [ ] 4.1 Update tracking status and session notes.
