# Session Status — Resume Point (Canonical)

**Last updated:** 2026-03-06

This is the **single canonical handoff file** for all AI sessions.
If you did work in this repo, update this file at the end of the session.
Do not create new per-version status files.

## What was completed
- V3 discovery/watchlist milestone implemented and pushed to `origin/main`.
- Embedding service extracted to `services/embedding/` (FastAPI + UDS).
- Vector search client updated to use sidecar service.
- Watchlist + discover flows implemented; suggestions computed on the fly.
- Skinnable CSS system introduced with two skins.
- V3 spec and session docs added; CLAUDE instructions updated to include V3.
- Semantic search documentation added; debug flags for raw distances/cutoff bypass added to sidecar `/search`.
- Discover page now shows a tip when a 1–2 word semantic search returns no results.
- Login/logout skin continuity fixed: unauthenticated skin now respects a validated `marketplace_skin` cookie.
- Skin cookie is now updated on login, signup, and profile theme changes.
- Added focused tests for skin context resolution (`marketplace/tests/test_skin_context.py`).
- Default skin changed to `simple-blue` for unauthenticated fallback and new users.
- Added migration `marketplace/migrations/0005_alter_user_skin.py` to set `User.skin` default to `simple-blue`.
- Skin defaults centralized in `marketplace/skin_config.py` (`DEFAULT_SKIN_SLUG`) to avoid multi-file default drift.
- Removed DB-level default for `User.skin` via `marketplace/migrations/0006_remove_user_skin_default.py`.
- Application-level default assignment retained (`DEFAULT_SKIN_SLUG`) in signup and user-manager creation paths.
- Discover page now supports user-selectable sorting: `Best match` (default), `Newest posted`, and role-aware `Ending soon`.
- Discover sort choice persists in session during the existing keep-results flow and is cleared by discover clear action.
- Added unit tests for discover sorting logic (`marketplace/tests/test_discover_sorting.py`).
- Discover `Sort by` now reorders already-loaded result cards in-browser on select change (no new search request).
- SSE client behavior refined: when viewing a thread, incoming events for that same thread no longer show a "new" nav badge; events for other threads still do.
- SSE troubleshooting resolved: real-time delivery verified end-to-end; prior failure was test setup (both browsers logged in as the same user, so only `/stream/2` connections existed).
- Thread SSE rendering now inserts incoming messages by timestamp (`data-message-ts`) for canonical live ordering, instead of always appending.
- Embedding sidecar `run.sh` updated to auto-resolve project venv (`../../.venv/bin/uvicorn`), works from any working directory.
- Embedding sidecar `README.md` added with full setup, API reference, and troubleshooting guide.
- Discover page: added "Hide listings I'm watching" checkbox — filters out watchlisted results client-side, persists in session.
- Listing filter bar added to Supply Lot and Demand Post list pages — instant typeahead filtering with X clear button, Escape key support, and "X / Y" match counter. Implemented as reusable `_listing_filter.html` include, styled in both skins. Uses `.tile-filtered` CSS class (not `hidden` attribute) to override `.tile { display: block }`.
- Listing tiles now show suggestion counts: amber "N new" badge for unsaved matches, green "N saved" badge for watchlisted matches. Computed via `bulk_suggestion_counts()` in `matching.py` — single pass over counterparts, one DB round-trip per set (dismissed, watchlisted).
- Listing filter bar redesigned: status toggle pills replaced with inline checkboxes next to the search input. Single compact row (`listing-filter-bar`) — search input, status checkboxes, and match counter all inline. Checkboxes only shown when multiple statuses exist. Styled in both skins.
- Documentation updated: `CLAUDE.md` (embedding service section, skin contract), `v3-discovery-watchlist-spec.md` (§8 sidecar architecture), `v3-session-status.md` (Session 2 entry), `v1-implementation-decisions.md` (deployment assumptions).
- **Messaging inbox & unread notifications overhaul:**
  - New `ThreadReadState` model (per-user-per-thread read tracking via `last_read_at` timestamp)
  - Migration `marketplace/migrations/0007_threadreadstate.py` created and applied
  - Central inbox view at `/messages/` — all conversations sorted by most recent, with unread indicators
  - Navbar "Messages" link with unread count badge (e.g. "Messages 3")
  - `unread_thread_count` context processor registered in settings — runs on every request for authenticated users
  - `send_new_message_notification()` added to `notifications.py` — sends email when a message is posted
  - Thread detail view now marks ThreadReadState on visit and sends email notification on message send
  - "Message" button added to suggestion cards (dashboard, demand post detail, supply lot detail)
  - `suggestion_message` view creates WatchlistItem + MessageThread in one step, redirects to thread
  - "Conversations" section on listing detail pages — owners see who has messaged about their listing
  - Thread detail back-link changed from "Back to watchlist" → "Back to messages"
  - `nav_section` context processor updated: `/messages` → "messages", `/threads` → "messages"
  - `ThreadReadState` registered in Django admin with `raw_id_fields`
  - `.nav-badge`, `.thread-unread`, `.thread-preview` CSS classes added to both skin files
  - Skin contract in CLAUDE.md updated with new Inbox/Messages classes
- **Real-time messaging via SSE sidecar:**
  - SSE relay service at `services/sse/` (FastAPI, TCP on port 8001)
  - Django-side client `marketplace/sse_client.py` with `publish_new_message()`, `generate_stream_token()`
  - Browser EventSource client `static/js/sse-client.js` — updates thread view, inbox, and navbar badge live
  - `sse_stream` context processor provides `{{ sse_stream_url }}` to templates
  - `get_unread_thread_count()` extracted as reusable helper in `context_processors.py`
  - Template updates: `_navbar.html` (id attrs), `thread_detail.html` (SSE data attrs), `inbox.html` (page marker + thread ids), `base.html` (SSE script loading)
  - CLAUDE.md updated with SSE sidecar documentation section
- Updated `ai-docs/PRODUCT_ROADMAP.md` with clarifications: demand quantity/unit, price per unit semantics, derived optional lat/lng + radius fallback, search direction openness, and listing-centric messaging multiple threads per listing.
- Created specsmd docs for foundational migration planning:
  - `specs/migration-safety-and-compatibility-rails/{requirements.md,design.md,tasks.md}`
  - `specs/role-agnostic-user-and-org-flattening/requirements.md`
  - `specs/unified-listing-model-and-status-contract/requirements.md`
  - `specs/ownership-based-permission-policy/requirements.md`
  - `specs/listing-centric-messaging-and-watchlist-decoupling/requirements.md`
  - `specs/discover-direction-and-visibility-contract/requirements.md`
- Added design docs for foundational follow-on specs:
  - `specs/role-agnostic-user-and-org-flattening/design.md`
  - `specs/unified-listing-model-and-status-contract/design.md`
  - `specs/ownership-based-permission-policy/design.md`
  - `specs/listing-centric-messaging-and-watchlist-decoupling/design.md`
  - `specs/discover-direction-and-visibility-contract/design.md`
- Added ordered execution index: `specs/SPEC_ORDER.md` (dependency-safe sequencing + status tracking for specs)
- Added tasks docs for all foundational specs with completed requirements+design:
  - `specs/role-agnostic-user-and-org-flattening/tasks.md`
  - `specs/unified-listing-model-and-status-contract/tasks.md`
  - `specs/ownership-based-permission-policy/tasks.md`
  - `specs/listing-centric-messaging-and-watchlist-decoupling/tasks.md`
  - `specs/discover-direction-and-visibility-contract/tasks.md`
- Updated `specs/SPEC_ORDER.md` statuses to `REQ, DES, TASK` for all foundational follow-on specs
- Feature 1 (`migration-safety-and-compatibility-rails`) implementation executed on branch `feat/01-migration-safety-and-compatibility-rails`:
  - Added migration control persistence models (`MigrationState`, `LegacyToTargetMapping`, `BackfillAuditRecord`, `ParityReport`) and migration `0009`.
  - Added additive target schemas and migration `0010`: `User.organization_name`, unified `Listing`, `ListingWatchlistItem`, `ListingMessageThread`.
  - Added migration control-plane modules (`marketplace/migration_control/`): config toggles, state manager, checkpoint controller, backfill engine, compatibility repository, parity validator.
  - Added dual-write sync signals (`marketplace/signals.py`) wired via `MarketplaceConfig.ready()`.
  - Added management commands: `migration_set_state`, `migration_backfill`, `migration_validate`, `migration_checkpoint`, `migration_cutover`.
  - Added migration regression tests in `marketplace/tests/test_migration_control.py` (state transitions, additive safety, idempotent backfill, compatibility dual-write, cutover/rollback drill, non-goal enforcement).
  - Updated `specs/migration-safety-and-compatibility-rails/tasks.md` to mark all tasks complete and `specs/SPEC_ORDER.md` to `REQ, DES, TASK, EXEC` for Feature 1.

## Current State
- Branch: `main` (uncommitted changes from this session)
- Status: SSE real-time messaging verified with distinct buyer/supplier sessions; live thread ordering and in-thread badge suppression behavior implemented
- Per-version status files removed; this is the only status tracker

## What's Next (if continuing)
- Manual testing: optionally verify out-of-order timestamp simulation still renders in canonical order
- Run `manage.py check` and `manage.py test marketplace` to verify no regressions
- Consider adding tests for SSE client token generation and publish logic
- Commit current session's changes
