# Spec Execution Order

This file is the canonical execution order for specs.

Rules:
- Keep spec folder names stable (no numeric prefixes in folder names).
- Update this file whenever a new spec is added, reordered, split, or merged.
- A spec is executable only when all listed dependencies are complete.

## Status Key

- `REQ` = requirements complete
- `DES` = design complete
- `TASK` = tasks complete
- `EXEC` = implementation in progress or complete

## Ordered Roadmap

1. **migration-safety-and-compatibility-rails**
   - Phase: FOUNDATION
   - Depends on: none
   - Status: `REQ, DES, TASK, EXEC`
   - Path: `specs/migration-safety-and-compatibility-rails/`

2. **role-agnostic-user-and-org-flattening**
   - Phase: FOUNDATION
   - Depends on: `migration-safety-and-compatibility-rails`
   - Status: `REQ, DES, TASK, EXEC`
   - Path: `specs/role-agnostic-user-and-org-flattening/`

3. **unified-listing-model-and-status-contract**
   - Phase: FOUNDATION
   - Depends on: `migration-safety-and-compatibility-rails`, `role-agnostic-user-and-org-flattening`
   - Status: `REQ, DES, TASK, EXEC`
   - Path: `specs/unified-listing-model-and-status-contract/`

4. **ownership-based-permission-policy**
   - Phase: FOUNDATION
   - Depends on: `migration-safety-and-compatibility-rails`, `role-agnostic-user-and-org-flattening`, `unified-listing-model-and-status-contract`
   - Status: `REQ, DES, TASK, EXEC`
   - Path: `specs/ownership-based-permission-policy/`

5. **listing-centric-messaging-and-watchlist-decoupling**
   - Phase: FOUNDATION
   - Depends on: `migration-safety-and-compatibility-rails`, `unified-listing-model-and-status-contract`, `ownership-based-permission-policy`
   - Status: `REQ, DES, TASK, EXEC`
   - Path: `specs/listing-centric-messaging-and-watchlist-decoupling/`

6. **discover-direction-and-visibility-contract**
   - Phase: FOUNDATION
   - Depends on: `migration-safety-and-compatibility-rails`, `unified-listing-model-and-status-contract`
   - Status: `REQ, DES, TASK, EXEC`
   - Path: `specs/discover-direction-and-visibility-contract/`

7. **legacy-schema-cleanup-and-final-cutover**
   - Phase: FOUNDATION COMPLETION
   - Depends on: all six foundation specs (`migration-safety-and-compatibility-rails`, `role-agnostic-user-and-org-flattening`, `unified-listing-model-and-status-contract`, `ownership-based-permission-policy`, `listing-centric-messaging-and-watchlist-decoupling`, `discover-direction-and-visibility-contract`)
   - Status: `REQ, DES, TASK, EXEC`
   - Path: `specs/legacy-schema-cleanup-and-final-cutover/`

8. **ui-language-and-navigation-derolification**
   - Phase: LAUNCH READINESS
   - Depends on: `legacy-schema-cleanup-and-final-cutover` (CP5 required); all six foundation specs
   - Status: `REQ, DES, TASK, EXEC`
   - Path: `specs/ui-language-and-navigation-derolification/`

9. **email-verification-and-account-activation**
   - Phase: LAUNCH READINESS
   - Depends on: all foundation specs (CP5 required); `ui-language-and-navigation-derolification`
   - Status: `REQ, DES, TASK, EXEC`
   - Path: `specs/email-verification-and-account-activation/`

10. **listing-expiry-lazy-filtering**
   - Phase: LAUNCH READINESS
   - Depends on: all foundation specs (CP5 required)
   - Status: `EXEC`
   - Path: n/a (executed directly, no spec docs — see §5.5 in PRODUCT_ROADMAP.md)

11. **profile-image-upload**
   - Phase: LAUNCH READINESS
   - Depends on: all foundation specs (CP5 required); Features 8–9 (`EXEC`)
   - Status: `REQ, DES, TASK, EXEC`
   - Path: `specs/profile-image-upload/`

12. **admin-console**
   - Phase: POST-LAUNCH
   - Depends on: `legacy-schema-cleanup-and-final-cutover`, `email-verification-and-account-activation`, `profile-image-upload`
   - Status: `REQ, DES, TASK`
   - Path: `specs/admin-console/`

13. **postgres-database-migration**
   - Phase: INFRASTRUCTURE
   - Depends on: Features 1–10 (`EXEC`) — does not require `admin-console`
   - Status: `REQ, DES, TASK, EXEC`
   - Path: `specs/postgres-database-migration/`

14. **embedding-sidecar-tcp-transport**
   - Phase: INFRASTRUCTURE
   - Depends on: Feature 13 (`EXEC`)
   - Status: `EXEC`
   - Path: n/a (no spec docs — transport swap only, no behavior change)

15. **messaging-workspace-layout-and-navigation**
   - Phase: UI/UX RE-ARCHITECTURE
   - Depends on: `listing-centric-messaging-and-watchlist-decoupling`, `messaging-workspace-conversation-context`, `navigation-ia-unification`
   - Status: `REQ, DES, TASK`
   - Path: `specs/messaging-workspace-layout-and-navigation/`

16. **messaging-conversation-list-ia**
   - Phase: UI/UX RE-ARCHITECTURE
   - Depends on: `messaging-workspace-layout-and-navigation`
   - Status: `REQ, DES, TASK`
   - Path: `specs/messaging-conversation-list-ia/`

17. **messaging-thread-pane-redesign**
   - Phase: UI/UX RE-ARCHITECTURE
   - Depends on: `messaging-workspace-layout-and-navigation`
   - Status: `REQ, DES, TASK`
   - Path: `specs/messaging-thread-pane-redesign/`

18. **messaging-sse-event-contract-expansion**
   - Phase: UI/UX RE-ARCHITECTURE
   - Depends on: `messaging-conversation-list-ia`, `messaging-thread-pane-redesign`
   - Status: `REQ, DES, TASK`
   - Path: `specs/messaging-sse-event-contract-expansion/`

19. **messaging-realtime-workspace-orchestration**
   - Phase: UI/UX RE-ARCHITECTURE
   - Depends on: `messaging-sse-event-contract-expansion`, `messaging-workspace-layout-and-navigation`, `messaging-conversation-list-ia`
   - Status: `REQ, DES, TASK`
   - Path: `specs/messaging-realtime-workspace-orchestration/`

20. **messaging-listing-grouped-conversations**
   - Phase: UI/UX RE-ARCHITECTURE
   - Depends on: `messaging-conversation-list-ia`, `messaging-realtime-workspace-orchestration`
   - Status: `REQ, DES, TASK`
   - Path: `specs/messaging-listing-grouped-conversations/`

## Messaging Series Guide

- Series map: `specs/MESSAGING_WORKSPACE_REARCHITECTURE_SPEC_SERIES.md`
- Feature plan: `specs/MESSAGING_WORKSPACE_REARCHITECTURE_FEATURE_PLAN.md`
- Architectural source of truth: `specs/messaging_feature_guide.md`

## Maintenance Workflow

When creating a new spec:
1. Add it to this file in dependency-safe order.
2. Set initial status to `REQ` once requirements are approved.
3. Add `DES`, `TASK`, and `EXEC` as milestones are completed.
4. If dependencies change, update both this file and each spec's `Dependencies` section.
