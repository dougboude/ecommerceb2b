# Legacy Schema Cleanup and Final Cutover — Design Document

## Overview

This spec executes in two phases:

1. **Final Application Convergence (reversible)**  
   Move all production paths to canonical models/fields:
   - `Listing`
   - listing-centric `MessageThread`
   - listing-centric `WatchlistItem`

2. **Irreversible Cleanup (CP5)**  
   After CP4 gates pass and preflight safety checks complete, advance to CP5 and apply destructive schema cleanup.

## Final Canonical Model Decisions

- `Listing` remains canonical listing entity.
- `MessageThread` remains canonical thread table/name, but only listing-centric fields survive:
  - keep: `listing`, `created_by_user`, `created_at`
  - remove legacy participant/linkage fields: `buyer`, `supplier`, `watchlist_item`
- `WatchlistItem` remains canonical watchlist table/name, but only listing-centric fields survive:
  - keep: `user`, `listing`, `status`, `source`, timestamps
  - remove legacy split FKs: `supply_lot`, `demand_post`
- `ThreadReadState` is retained and points to canonical listing-centric `MessageThread`.

This avoids unnecessary churn/renames while matching roadmap semantics.

## Dependency and Gate Alignment

- Must run after Features 1–6 are `EXEC`.
- CP4 required before CP5.
- Required passing parity scopes before CP5:
  - `counts`, `relationships`, `identity`, `listing`, `permission`, `messaging`, `discover`
- CP5 safety preflight required:
  - verified database backup/snapshot
  - reviewed destructive migration plan

## Architecture Changes

### Application Convergence

- Remove remaining legacy `DemandPost` / `SupplyLot` production-path usage.
- Keep existing route names where practical, but handlers query `Listing`.
- Convert matching/suggestion and vector index orchestration to listing-only paths.
- Convert discover/suggestion/watchlist/thread flows to canonical listing-centric `MessageThread`/`WatchlistItem` usage.

### Compliance Blocking

Add/extend structural compliance scanners used by migration parity:
- No production-path `DemandPost`/`SupplyLot` dependencies.
- No production-path `User.role`/`Organization` dependencies.
- No legacy `MessageThread` fields (`buyer/supplier/watchlist_item`) read/write in production flows.
- No legacy `WatchlistItem` fields (`supply_lot/demand_post`) read/write in production flows.

Any violation fails parity and blocks CP5.

### Command/Module Integrity

- Remove runtime compatibility behavior from production paths.
- Before deleting shim modules, update management commands so they do not import removed modules.
- Kept commands must run with explicit post-cleanup behavior.
- Intentionally retired commands must fail clearly with deprecation guidance.

## Cleanup Migration Strategy

Perform destructive cleanup in a tightly sequenced window:

1. Preflight complete (backup + parity + plan review).
2. Advance to CP5.
3. Apply cleanup migration set:
   - remove `User.role`
   - drop `Organization`
   - drop `DemandPost` / `SupplyLot`
   - remove legacy columns/FKs from `MessageThread` and `WatchlistItem`
   - ensure `ThreadReadState.thread` references canonical listing-centric `MessageThread`
   - finalize `DismissedSuggestion` to listing FK only
4. Run post-migration parity/health/test checks.

`MigrationState`, `LegacyToTargetMapping`, `BackfillAuditRecord`, and `ParityReport` remain as audit artifacts.

## Error Handling

| Error | Condition | Recovery |
|---|---|---|
| `ParityGateFailure` | Any required scope failing | Remediate and rerun validation before CP5 |
| `PreflightSafetyFailure` | Missing backup or plan review | Block CP5 |
| `CleanupMigrationFailure` | Error after CP5 advancement | Restore from preflight backup |
| `LegacyDependencyViolation` | Scanner detects legacy production dependency | Block CP5 until fixed |

## Testing Strategy

### Before CP5

- Full regression suite green.
- Explicit compliance scanner coverage for:
  - listing legacy dependencies
  - role/org dependencies
  - thread/watchlist legacy-field dependencies

### After CP5 + Cleanup Migration

- Full regression suite green.
- Migration/command smoke tests for retained command set.
- Assertions:
  - `User.role` and `Organization` absent
  - no `DemandPost`/`SupplyLot` production dependencies
  - messaging/watchlist flows work on canonical listing-centric schemas

## Scope Boundaries

- In scope: final migration convergence, destructive cleanup, compatibility retirement.
- Out of scope: new product features, marketplace transactions, major IA/URL redesign.
