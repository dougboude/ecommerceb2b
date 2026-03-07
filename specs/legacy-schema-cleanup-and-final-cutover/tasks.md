# Implementation Plan

## Phase 1: Application Migration

- [ ] 1. Verify prerequisites and confirm parity gate readiness
- [ ] 1.1 Run `migration_validate --scope all` and confirm all gates pass
  - Gates required: counts, relationships, identity, listing, permission
  - _Requirements: 1.1, 1.2_
- [ ] 1.2 Confirm system is at CP4 (or advance to CP4 if not yet done)
  - _Requirements: 1.3_

- [ ] 2. Convert listing forms to use unified Listing model
- [ ] 2.1 Create `SupplyListingForm` replacing `SupplyLotForm`
  - Map supply-specific fields: shipping_scope, price_value, price_unit, quantity, unit, expires_at
  - _Requirements: 2.2_
- [ ] 2.2 Create `DemandListingForm` replacing `DemandPostForm`
  - Map demand-specific fields: radius_km, frequency, quantity, unit, expires_at
  - Remove Organization FK requirement (no longer applies to Listing model)
  - _Requirements: 2.2, 4.3_
- [ ] 2.3 Remove `DemandPostForm` and `SupplyLotForm` from `forms.py`
  - _Requirements: 2.1_

- [ ] 3. Convert listing views to use unified Listing model
- [ ] 3.1 Convert `demand_post_list` to query `Listing.objects.filter(type=DEMAND, created_by_user=user)`
  - _Requirements: 2.2, 2.3_
- [ ] 3.2 Convert `demand_post_create` to create `Listing(type=DEMAND)`
  - Remove Organization existence guard (introduced in Feature 4, no longer needed)
  - _Requirements: 2.2, 4.3_
- [ ] 3.3 Convert `demand_post_edit`, `demand_post_toggle`, `demand_post_delete` to operate on `Listing`
  - _Requirements: 2.2_
- [ ] 3.4 Convert `demand_post_detail` to fetch and render `Listing`
  - _Requirements: 2.2_
- [ ] 3.5 Convert `supply_lot_list` to query `Listing.objects.filter(type=SUPPLY, created_by_user=user)`
  - _Requirements: 2.2, 2.3_
- [ ] 3.6 Convert `supply_lot_create` to create `Listing(type=SUPPLY)`
  - _Requirements: 2.2_
- [ ] 3.7 Convert `supply_lot_edit`, `supply_lot_toggle`, `supply_lot_delete` to operate on `Listing`
  - _Requirements: 2.2_
- [ ] 3.8 Convert `supply_lot_detail` to fetch and render `Listing`
  - _Requirements: 2.2_
- [ ] 3.9 Remove all `DemandPost` and `SupplyLot` imports from `views.py`
  - _Requirements: 2.1_

- [ ] 4. Convert listing templates to use unified Listing fields
- [ ] 4.1 Update `demand_post_list.html`, `demand_post_detail.html`, `demand_post_form.html`
  - Reference `Listing` field names (title, description, category, status, etc.)
  - _Requirements: 2.2_
- [ ] 4.2 Update `supply_lot_list.html`, `supply_lot_detail.html`, `supply_lot_form.html`
  - Reference `Listing` field names
  - _Requirements: 2.2_

- [ ] 5. Convert messaging flows to use ListingMessageThread
- [ ] 5.1 Convert `thread_detail` view to query `ListingMessageThread`
  - Derive listing owner from `thread.listing.created_by_user` (replaces explicit `supplier` FK)
  - Derive initiator from `thread.created_by_user` (replaces explicit `buyer` FK)
  - _Requirements: 3.1, 3.4_
- [ ] 5.2 Convert `inbox_view` to query `ListingMessageThread`
  - Update unread detection logic for new participant model
  - _Requirements: 3.4_
- [ ] 5.3 Convert `_get_or_create_thread` helper to create `ListingMessageThread`
  - _Requirements: 3.1_
- [ ] 5.4 Update `ThreadReadState` FK to reference `ListingMessageThread`
  - Write migration to re-point FK and backfill from legacy thread data
  - _Requirements: 3.3_
- [ ] 5.5 Update `thread_detail.html` and `inbox.html` templates for new model fields
  - _Requirements: 3.4_
- [ ] 5.6 Update SSE publish calls to use `ListingMessageThread` IDs
  - _Requirements: 3.3_
- [ ] 5.7 Update notifications to reference `ListingMessageThread`
  - _Requirements: 3.3_

- [ ] 6. Convert watchlist flows to use ListingWatchlistItem
- [ ] 6.1 Convert `watchlist_view` to query `ListingWatchlistItem`
  - _Requirements: 3.2, 3.4_
- [ ] 6.2 Convert `watchlist_star`, `watchlist_archive`, `watchlist_unarchive`, `watchlist_delete` to operate on `ListingWatchlistItem`
  - _Requirements: 3.2_
- [ ] 6.3 Convert `watchlist_message` to use `ListingWatchlistItem` + `ListingMessageThread`
  - _Requirements: 3.2, 3.1_
- [ ] 6.4 Convert `discover_save`, `discover_unsave`, `discover_message`, `suggestion_save`, `suggestion_dismiss`, `suggestion_message` to use `ListingWatchlistItem`
  - _Requirements: 3.2_
- [ ] 6.5 Update permission service watchlist authorization to use `ListingWatchlistItem`
  - _Requirements: 3.2_
- [ ] 6.6 Update watchlist templates for new model fields
  - _Requirements: 3.4_

- [ ] 7. Convert DismissedSuggestion to listing FK
- [ ] 7.1 Add `listing` FK to `DismissedSuggestion` model via additive migration
  - _Requirements: 5.1_
- [ ] 7.2 Backfill `DismissedSuggestion.listing` from legacy supply_lot/demand_post FKs via LegacyToTargetMapping
  - _Requirements: 5.1_
- [ ] 7.3 Update `suggestion_dismiss` view and all dismissal queries to use `listing` FK
  - _Requirements: 2.4_

- [ ] 8. Convert matching and vector search to use Listing model
- [ ] 8.1 Update `matching.py`: `get_suggestions_for_lot`, `get_suggestions_for_post`, `bulk_suggestion_counts` to query `Listing`
  - _Requirements: 2.4_
- [ ] 8.2 Update `watchlisted_supply_lot_ids`, `watchlisted_demand_post_ids` helpers to query `ListingWatchlistItem`
  - _Requirements: 2.4_
- [ ] 8.3 Update vector search index/remove calls to use `Listing` PKs
  - _Requirements: 2.4_

- [ ] 9. Remove User.role and Organization references from production code
- [ ] 9.1 Remove all `user.role` comparisons from `views.py` (dashboard, discover, watchlist role branching)
  - _Requirements: 4.3_
- [ ] 9.2 Remove `Role` enum import from all production files
  - _Requirements: 4.3_
- [ ] 9.3 Remove Organization import and usage from all production files
  - _Requirements: 4.1_
- [ ] 9.4 Update `UserManager.create_superuser` to remove `role` default
  - _Requirements: 4.3_
- [ ] 9.5 Update admin registrations to remove role/organization references
  - _Requirements: 4.3_

- [ ] 10. Phase 1 regression checkpoint
- [ ] 10.1 Run full test suite — all tests must pass before Phase 2 begins
  - _Requirements: 7.1, 7.2, 7.3_
- [ ] 10.2 Run `migration_validate --scope all` — confirm all parity gates still pass
  - _Requirements: 1.1_

## Phase 2: Schema Cleanup

- [ ] 11. Advance to CP5 and apply cleanup migration
- [ ] 11.1 Run `migration_cutover --to CP5`
  - _Requirements: 1.3, 1.4_
- [ ] 11.2 Write cleanup Django migration dropping legacy tables
  - Drop: `MessageThread`, `WatchlistItem` (old), `DemandPost`, `SupplyLot`, `Organization`
  - Remove: `User.role` field
  - Re-point: `ThreadReadState.thread` FK to `ListingMessageThread` (if not done in Phase 1)
  - Drop: `DismissedSuggestion` legacy FKs (supply_lot, demand_post) after backfill confirmed
  - Retain: `MigrationState`, `LegacyToTargetMapping`, `BackfillAuditRecord`, `ParityReport`
  - _Requirements: 5.1, 5.2, 5.3, 4.1, 4.2_
- [ ] 11.3 Apply migration: `manage.py migrate`
  - _Requirements: 5.1_

- [ ] 12. Remove compatibility shim modules
- [ ] 12.1 Delete `marketplace/migration_control/compatibility.py`
  - _Requirements: 6.1, 6.3_
- [ ] 12.2 Delete `marketplace/migration_control/listings.py`
  - _Requirements: 6.3_
- [ ] 12.3 Delete `marketplace/migration_control/backfill.py`
  - _Requirements: 6.3_
- [ ] 12.4 Delete `marketplace/migration_control/identity.py`
  - _Requirements: 6.3_
- [ ] 12.5 Remove dual-write signal handlers from `marketplace/signals.py`
  - _Requirements: 6.1_
- [ ] 12.6 Remove `listing_service` and `identity_adapter` usages from `views.py`
  - _Requirements: 6.2_
- [ ] 12.7 Remove `ListingCompatibilityService` import from all remaining files
  - _Requirements: 6.2_

- [ ] 13. Write regression tests for cleaned-up state
- [ ] 13.1 Test that `User` has no `role` attribute
  - _Requirements: 7.4_
- [ ] 13.2 Test that `Organization` cannot be imported from marketplace.models
  - _Requirements: 7.4_
- [ ] 13.3 Test listing CRUD flows against `Listing` model directly
  - _Requirements: 7.1_
- [ ] 13.4 Test messaging flows against `ListingMessageThread`
  - _Requirements: 7.2_
- [ ] 13.5 Test watchlist flows against `ListingWatchlistItem`
  - _Requirements: 7.3_

- [ ] 14. Final checkpoint — confirm scope boundaries
- [ ] 14.1 Run full test suite — all tests must pass
- [ ] 14.2 Confirm no unrelated feature work was included
  - _Requirements: 8.1, 8.2, 8.3_
