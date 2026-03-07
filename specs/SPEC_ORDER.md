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
   - Status: `REQ, DES, TASK`
   - Path: `specs/listing-centric-messaging-and-watchlist-decoupling/`

6. **discover-direction-and-visibility-contract**
   - Phase: FOUNDATION
   - Depends on: `migration-safety-and-compatibility-rails`, `unified-listing-model-and-status-contract`
   - Status: `REQ, DES, TASK`
   - Path: `specs/discover-direction-and-visibility-contract/`

## Maintenance Workflow

When creating a new spec:
1. Add it to this file in dependency-safe order.
2. Set initial status to `REQ` once requirements are approved.
3. Add `DES`, `TASK`, and `EXEC` as milestones are completed.
4. If dependencies change, update both this file and each spec's `Dependencies` section.
