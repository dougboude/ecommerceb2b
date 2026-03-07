# CP5 Destructive Cleanup Runbook

Date: 2026-03-07
Branch: feat/07-legacy-schema-cleanup-and-final-cutover

## Preconditions (verified)
1. Checkpoint at CP4.
2. `migration_validate --scope all --fail-on-error` passing.
3. Pre-cleanup snapshot captured:
   - `ai-docs/backups/db-pre-cp5-20260307-074242.sqlite3`
4. Migration-state evidence captured:
   - `ai-docs/backups/showmigrations-marketplace-20260307-074246.txt`

## Destructive operation order
1. Advance migration control checkpoint to CP5 (`migration_cutover --to CP5`).
2. Apply schema cleanup migration set to remove:
   - `User.role`
   - `Organization`
   - legacy listing tables (`DemandPost`, `SupplyLot`)
   - legacy `MessageThread` fields (`watchlist_item`, `buyer`, `supplier`)
   - legacy `WatchlistItem` fields (`supply_lot`, `demand_post`)
   - legacy `DismissedSuggestion` fields (`supply_lot`, `demand_post`)
3. Remove/retire compatibility runtime shims not needed after cleanup.
4. Run post-cleanup validation:
   - full test suite
   - migration validation scopes
   - command smoke checks

## Recovery model
- CP5 is irreversible in-state; rollback requires restoring the DB snapshot above.

