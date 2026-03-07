# Legacy Schema Cleanup and Final Cutover — Design Document

## Overview

This spec executes in two sequential phases:

1. **Application Migration Phase** — Convert all production code from legacy models (`DemandPost`, `SupplyLot`, `Organization`, old `WatchlistItem`, old `MessageThread`) to target models (`Listing`, `ListingWatchlistItem`, `ListingMessageThread`). No models are removed yet.
2. **Schema Cleanup Phase** — Advance to CP5, apply destructive Django migrations to drop legacy tables, remove compatibility shims, and finalize the codebase.

The phases must be executed in order. Phase 1 is fully reversible. Phase 2 is not.

## Dependency Alignment

- All six foundation specs must be `EXEC` before this spec begins.
- The migration control framework (Feature 1) gates CP5 behind confirmed parity reports.
- `migration_validate --scope all` must produce all-passing reports before Phase 2 begins.

## Architecture

```
Phase 1: Application Migration
  ┌─────────────────────────────────────────────────────────┐
  │  Views          Forms         Templates     Helpers      │
  │  (listing_*)    (ListingForm) (listing_*)   (matching,   │
  │                                              vector)     │
  │         All query Listing directly (no DemandPost/Lot)  │
  └─────────────────────────────────────────────────────────┘

Phase 2: Schema Cleanup (CP5)
  ┌─────────────────────────────────────────────────────────┐
  │  migration_cutover --to CP5                             │
  │  Django migration drops legacy tables                   │
  │  Remove compatibility shims                             │
  │  Remove User.role, Organization                         │
  └─────────────────────────────────────────────────────────┘
```

## Phase 1: Application Migration

### View Conversion Strategy

The existing listing flows map cleanly to the unified model:

| Legacy View | Target View | Change |
|---|---|---|
| `demand_post_list` | `demand_post_list` (renamed eventually) | Query `Listing.objects.filter(type=DEMAND, created_by_user=user)` |
| `supply_lot_list` | `supply_lot_list` (renamed eventually) | Query `Listing.objects.filter(type=SUPPLY, created_by_user=user)` |
| `demand_post_create` | same | Create `Listing(type=DEMAND, created_by_user=request.user)` |
| `supply_lot_create` | same | Create `Listing(type=SUPPLY, created_by_user=request.user)` |
| `demand_post_edit` | same | Edit `Listing` object |
| `supply_lot_edit` | same | Edit `Listing` object |
| `demand_post_toggle` | same | Toggle `Listing.status` |
| `supply_lot_toggle` | same | Toggle `Listing.status` |
| `demand_post_delete` | same | Soft-delete `Listing.status = DELETED` |
| `supply_lot_delete` | same | Soft-delete `Listing.status = DELETED` |
| `demand_post_detail` | same | Fetch `Listing` by pk |
| `supply_lot_detail` | same | Fetch `Listing` by pk |

**Note:** URL names and view names are NOT changed in this spec (per Requirement 8.4). URL/nav restructuring is deferred to the UI derolification spec.

### Form Conversion Strategy

Replace `DemandPostForm` and `SupplyLotForm` with type-aware `ListingForm` variants:

```python
class ListingForm(forms.ModelForm):
    class Meta:
        model = Listing
        fields = [...]  # shared fields

class SupplyListingForm(ListingForm):
    # supply-specific fields: shipping_scope, price_value, price_unit, quantity, unit

class DemandListingForm(ListingForm):
    # demand-specific fields: radius_km, frequency, quantity, unit
```

The `Organization` FK requirement in `DemandPostForm` is dropped entirely. `demand_post_create` no longer needs the `Organization` existence guard introduced in Feature 4 — `Listing` has no organization FK.

### Messaging Conversion

`ListingMessageThread` (target model, added in Feature 1) replaces the legacy `MessageThread`:

| Legacy Field | Target Field |
|---|---|
| `MessageThread.buyer` | `ListingMessageThread.created_by_user` (the non-owner initiator) |
| `MessageThread.supplier` | derivable as `thread.listing.created_by_user` |
| `MessageThread.watchlist_item` | Not needed — `(listing, user)` pair is the relationship |

The inbox view and thread detail view will query `ListingMessageThread` and derive participant identity from listing ownership.

**ThreadReadState** will be updated to reference `ListingMessageThread` instead of `MessageThread`. The existing `ThreadReadState` model requires a FK swap via migration.

### Watchlist Conversion

`ListingWatchlistItem` replaces the legacy `WatchlistItem`:

| Legacy Field | Target Field |
|---|---|
| `WatchlistItem.supply_lot` | `ListingWatchlistItem.listing` (type=SUPPLY) |
| `WatchlistItem.demand_post` | `ListingWatchlistItem.listing` (type=DEMAND) |
| `WatchlistItem.user` | `ListingWatchlistItem.user` |
| `WatchlistItem.status` | `ListingWatchlistItem.status` |
| `WatchlistItem.source` | `ListingWatchlistItem.source` |

### Matching and Vector Search Conversion

- `matching.py` queries `Listing.objects.filter(type=SUPPLY/DEMAND)` instead of `SupplyLot`/`DemandPost`.
- `vector_search.py` already operates on PKs; the sidecar service is model-agnostic. The index/remove calls use `Listing` PKs directly.
- `bulk_suggestion_counts()` operates on `Listing` querysets instead of separate supply/demand sets.

### Organization and User.role Removal

- All `request.user.organization` references are removed (the guard in `demand_post_create` introduced in Feature 4 is removed since `Listing` has no organization FK).
- All `user.role` comparisons (remaining in dashboard and discover branching) are removed.
- `Role` enum import removed from `views.py` and all other files.
- `Organization` FK removed from `DemandPost` (already being removed with the model itself).

## Phase 2: Schema Cleanup

### CP5 Gate Sequence

```
1. Run: manage.py migration_validate --scope all --fail-on-error
2. All gates pass → run: manage.py migration_cutover --to CP5
3. CP5 advanced → apply cleanup migration
4. Remove shim code
```

### Cleanup Django Migration

A single migration handles all legacy table drops:

```python
# marketplace/migrations/XXXX_drop_legacy_models.py
operations = [
    # Remove FKs first (ThreadReadState references MessageThread)
    migrations.AlterField('ThreadReadState', 'thread', ...),  # re-point to ListingMessageThread
    # Drop legacy tables
    migrations.DeleteModel('MessageThread'),
    migrations.DeleteModel('WatchlistItem'),
    migrations.DeleteModel('DismissedSuggestion'),  # if backed by legacy FKs
    migrations.DeleteModel('DemandPost'),
    migrations.DeleteModel('SupplyLot'),
    migrations.DeleteModel('Organization'),
    # Remove User.role
    migrations.RemoveField('User', 'role'),
]
```

`MigrationState`, `LegacyToTargetMapping`, `BackfillAuditRecord`, and `ParityReport` are **not** dropped — they serve as permanent migration audit records.

### Shim Code Removal

Files to delete entirely after Phase 2:
- `marketplace/migration_control/compatibility.py`
- `marketplace/migration_control/listings.py`
- `marketplace/migration_control/backfill.py` (backfill engine no longer needed)
- `marketplace/migration_control/identity.py` (identity adapter no longer needed)

Files to update (remove dual-write logic):
- `marketplace/signals.py` — remove dual-write signal handlers; retain app-ready signal wiring if needed
- `marketplace/apps.py` — remove signal registration for dual-write

Files to retain:
- `marketplace/migration_control/state.py`
- `marketplace/migration_control/checkpoints.py`
- `marketplace/migration_control/parity.py`
- `marketplace/migration_control/permissions.py`

### DismissedSuggestion Handling

`DismissedSuggestion` currently has `supply_lot` and `demand_post` FKs. Options:
1. Migrate it to a `listing` FK on `Listing` (preferred — preserves dismissal data)
2. Drop and recreate it with the new FK

The preferred approach is a migration that adds `listing` FK to `DismissedSuggestion`, backfills from legacy FKs, then removes the old FKs. This can be bundled into the backfill step in Phase 1.

## Error Handling

| Error Type | Condition | Recovery |
|---|---|---|
| `ParityGateFailure` | Parity reports not all passing at CP4 | Run `migration_validate` and remediate before proceeding |
| `CP5AdvancementBlocked` | CP4 not achieved before CP5 attempt | Advance through CP4 first |
| `LegacyReferenceRemaining` | Production code still imports DemandPost/SupplyLot | Treat as blocking; find and fix all references before applying cleanup migration |
| `MigrationRollbackAttempt` | Attempt to reverse cleanup migration | Not supported; full restore requires a database backup |

## Testing Strategy

### Phase 1 Tests (before schema cleanup)
- Listing CRUD via unified Listing model (create, edit, toggle, delete)
- Listing list views return correct `type`-filtered results
- Listing detail shows correct supply-only / demand-only fields
- Messaging flows via `ListingMessageThread`
- Watchlist flows via `ListingWatchlistItem`
- Permission service continues to function (Feature 4 behavior preserved)

### Phase 2 Tests (after schema cleanup)
- `User.role` field does not exist (AttributeError on access)
- `Organization` model does not exist (ImportError on import)
- `DemandPost`, `SupplyLot` models do not exist
- All previously passing tests continue to pass after legacy model removal

### Regression Guard
- Full test suite must pass after Phase 1 before Phase 2 begins
- Full test suite must pass after Phase 2 completes

## Scope Boundaries

- **In scope:** Application code migration to unified models, legacy model removal, shim removal, schema cleanup migration.
- **Out of scope:** URL restructuring, navigation redesign, UI language changes, new features, profile image, email verification, radius filtering.
