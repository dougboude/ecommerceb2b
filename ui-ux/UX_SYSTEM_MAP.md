# UX System Map — NicheMarket (Current State)

## 1. APPLICATION PURPOSE

NicheMarket is a private, authenticated B2B discovery marketplace where businesses post either:
- **Supply listings** (what they have), or
- **Demand listings** (what they need).

The core problem it solves is counterpart discovery and connection in niche markets. Users can discover listings, save them to watchlist, and start listing-linked private message threads.

---

## 2. CORE DOMAIN ENTITIES

### Entity: User
- **Purpose:** Account identity and preferences for all platform activity.
- **Key fields:** `email`, `display_name`, `country`, `email_verified`, `timezone`, `distance_unit`, `skin`, `email_on_message`, `organization_name`, `profile_image`.
- **Relationships:** owns many `Listing`; owns many `WatchlistItem`; creates many `MessageThread`; sends many `Message`; has many `ThreadReadState`; has many `DismissedSuggestion`; has many `EmailVerificationToken`.
- **Type:** User object.

### Entity: Listing
- **Purpose:** Unified listing record representing either supply or demand content.
- **Key fields:** `type` (`supply`/`demand`), `title`, `description`, `category`, `status`, `quantity`, `unit`, `price_value`, `price_unit`, `shipping_scope`, `radius_km`, `frequency`, `expires_at`, location fields.
- **Relationships:** belongs to `User` (`created_by_user`); has many `WatchlistItem`; has many `DismissedSuggestion`; has many `MessageThread`.
- **Type:** Content object.

### Entity: WatchlistItem
- **Purpose:** Tracks a user’s saved listings and state (`starred`, `watching`, `archived`).
- **Key fields:** `user`, `listing`, `status`, `source`, timestamps.
- **Relationships:** belongs to `User`; belongs to `Listing`; derived link to thread via `(user, listing)` lookup.
- **Type:** Content workflow object.

### Entity: DismissedSuggestion
- **Purpose:** Prevents previously dismissed suggestions from reappearing.
- **Key fields:** `user`, `listing`, `created_at`.
- **Relationships:** belongs to `User`; belongs to `Listing`.
- **Type:** System/user-preference object.

### Entity: MessageThread
- **Purpose:** Conversation container tied to one listing and one initiating user.
- **Key fields:** `listing`, `created_by_user`, `created_at` (unique per `(listing, created_by_user)`).
- **Relationships:** belongs to `Listing`; belongs to initiator `User`; has many `Message`; has many `ThreadReadState`.
- **Type:** Content interaction object.

### Entity: Message
- **Purpose:** Individual message inside a thread.
- **Key fields:** `thread`, `sender`, `body`, `created_at`.
- **Relationships:** belongs to `MessageThread`; belongs to sender `User`.
- **Type:** Content object.

### Entity: ThreadReadState
- **Purpose:** Per-user read marker for each thread.
- **Key fields:** `thread`, `user`, `last_read_at`.
- **Relationships:** belongs to `MessageThread`; belongs to `User`.
- **Type:** System object.

### Entity: EmailVerificationToken
- **Purpose:** Single-use account verification token lifecycle.
- **Key fields:** `user`, `token`, `expires_at`, `used_at`, `revoked_at`.
- **Relationships:** belongs to `User`.
- **Type:** System/security object.

### Entities: MigrationState, LegacyToTargetMapping, BackfillAuditRecord, ParityReport
- **Purpose:** Internal migration-control and parity infrastructure from refactor program.
- **Type:** System objects (not user-facing UX primitives).

---

## 3. ROUTE MAP

### Root URL config
- `/admin/` -> Django Admin site -> Django admin templates  
  Auth: staff/superuser  
  Purpose: framework admin backend (not product UX).

### Marketplace routes

| Path | View | Template | Auth | Purpose |
|---|---|---|---|---|
| `/` | `dashboard_view` | `marketplace/dashboard.html` | Required | Home dashboard for logged-in users. |
| `/signup/` | `signup_view` | `registration/signup.html` | Optional (redirects if authed) | Account creation. |
| `/login/` | `MarketplaceLoginView` | `registration/login.html` | Optional | Login page; blocks unverified users. |
| `/logout/` | `MarketplaceLogoutView` | `registration/logged_out.html` (default) | Session/logout context | Logs out current user. |
| `/verify-email/` | `verify_email` | `registration/email_verify.html` | Optional | “Check your email” page. |
| `/verify-email/<uuid:token>/` | `verify_email_confirm` | `email_verify_used.html` / `email_verify_expired.html` or redirect | Optional | Token-based account activation. |
| `/resend-verification/` | `resend_verification` | `registration/resend_verification.html` | Optional | Request new verification email. |
| `/profile/` | `profile_view` | `marketplace/profile.html` | Required | Profile summary + avatar + recent listings. |
| `/profile/edit/` | `profile_edit` | `marketplace/profile_edit.html` | Required | Edit profile/preferences. |
| `/profile/upload-avatar/` | `upload_profile_image` | None (JSON) | Required + POST | Avatar upload endpoint. |
| `/wanted/` | `demand_post_list` | `marketplace/demand_post_list.html` | Required | List own demand listings. |
| `/wanted/new/` | `demand_post_create` | `marketplace/demand_post_form.html` | Required | Create demand listing. |
| `/wanted/<int:pk>/` | `demand_post_detail` | `marketplace/demand_post_detail.html` | Required | Demand listing detail + suggestions + conversations. |
| `/wanted/<int:pk>/edit/` | `demand_post_edit` | `marketplace/demand_post_form.html` | Required | Edit demand listing. |
| `/wanted/<int:pk>/toggle/` | `demand_post_toggle` | None (redirect) | Required + POST | Pause/resume/reactivate demand listing. |
| `/wanted/<int:pk>/delete/` | `demand_post_delete` | `marketplace/listing_delete_confirm.html` (GET) | Required | Confirm soft-delete of demand listing. |
| `/available/` | `supply_lot_list` | `marketplace/supply_lot_list.html` | Required | List own supply listings. |
| `/available/new/` | `supply_lot_create` | `marketplace/supply_lot_form.html` | Required | Create supply listing. |
| `/available/<int:pk>/` | `supply_lot_detail` | `marketplace/supply_lot_detail.html` | Required | Supply listing detail + suggestions + conversations. |
| `/available/<int:pk>/edit/` | `supply_lot_edit` | `marketplace/supply_lot_form.html` | Required | Edit supply listing. |
| `/available/<int:pk>/toggle/` | `supply_lot_toggle` | None (redirect) | Required + POST | Withdraw/reactivate supply listing. |
| `/available/<int:pk>/delete/` | `supply_lot_delete` | `marketplace/listing_delete_confirm.html` (GET) | Required | Confirm soft-delete of supply listing. |
| `/discover/` | `discover_view` | `marketplace/discover.html` | Required | Search counterpart listings. |
| `/discover/clear/` | `discover_clear` | None (redirect) | Required | Clear discover session state. |
| `/discover/save/` | `discover_save` | None (redirect) | Required + POST | Save discover result to watchlist. |
| `/discover/unsave/` | `discover_unsave` | None (redirect) | Required + POST | Remove discover result from watchlist. |
| `/discover/message/` | `discover_message` | None (redirect) | Required + POST | Start thread from discover result. |
| `/watchlist/` | `watchlist_view` | `marketplace/watchlist.html` | Required | Watchlist and archived sections. |
| `/watchlist/<int:pk>/star/` | `watchlist_star` | `_watchlist_card.html` (HTMX) or redirect | Required + POST | Toggle starred/watch state. |
| `/watchlist/<int:pk>/archive/` | `watchlist_archive` | None (redirect) | Required + POST | Archive watchlist item. |
| `/watchlist/<int:pk>/unarchive/` | `watchlist_unarchive` | None (redirect) | Required + POST | Restore archived item. |
| `/watchlist/<int:pk>/delete/` | `watchlist_delete` | None (redirect) | Required + POST | Remove watchlist item. |
| `/watchlist/<int:pk>/message/` | `watchlist_message` | None (redirect) | Required + POST | Open/create thread from watchlist item. |
| `/suggestions/save/` | `suggestion_save` | None (redirect) | Required + POST | Save suggested listing to watchlist. |
| `/suggestions/dismiss/` | `suggestion_dismiss` | None (redirect) | Required + POST | Dismiss suggestion. |
| `/suggestions/message/` | `suggestion_message` | None (redirect) | Required + POST | Start thread from suggestion. |
| `/messages/` | `inbox_view` | `marketplace/inbox.html` | Required | Inbox listing all active threads. |
| `/threads/<int:pk>/` | `thread_detail` | `marketplace/thread_detail.html` | Required | Message thread detail + send form. |

---

## 4. PAGE INVENTORY

### Auth / Account Pages
- **Signup**
  - Purpose: Register account.
  - Components: Signup form, login link.
  - Actions: Submit signup.
- **Login**
  - Purpose: Authenticate user.
  - Components: Login form, signup link, unverified error path.
  - Actions: Submit login.
- **Verify Email (check inbox)**
  - Purpose: Post-signup waiting state.
  - Components: guidance text, resend link, login link.
  - Actions: go to resend or login.
- **Verify Link Expired**
  - Purpose: token-expired state.
  - Components: error copy + resend CTA.
  - Actions: resend verification.
- **Already Verified**
  - Purpose: repeat token usage state.
  - Components: status copy + login CTA.
  - Actions: login.
- **Logged Out**
  - Purpose: logout confirmation.
  - Components: status copy + login CTA.
  - Actions: login.

### Core Product Pages
- **Dashboard**
  - Purpose: quick overview of own demand/supply listings, suggestions, watchlist count.
  - Components: listing tiles, suggestion cards, watchlist summary, discover CTA.
  - Actions: open listing, create listing, save/message/dismiss suggestion.
- **Discover**
  - Purpose: search counterpart listings.
  - Components: query/direction/search-mode/sort filters, result cards, save/unsave/message actions.
  - Actions: search, clear, save/unsave listing, message listing owner.
- **Watchlist**
  - Purpose: track saved listings and conversation entry points.
  - Components: watching cards, archived section, inline star/archive/remove/message actions.
  - Actions: star/unstar, archive/unarchive, delete, open conversation.
- **Inbox**
  - Purpose: overview of active conversations.
  - Components: thread cards, unread badges, empty-state guidance.
  - Actions: open thread.
- **Thread Detail**
  - Purpose: run conversation on one listing.
  - Components: counterparty, listing snapshot, message timeline, send form, back-to-messages.
  - Actions: send message (unless listing deleted), return to inbox.
- **Profile**
  - Purpose: identity summary and avatar management.
  - Components: avatar upload/crop modal, profile fields, quick links to own listings.
  - Actions: upload avatar, go to edit profile, open listing.
- **Profile Edit**
  - Purpose: edit user preferences/profile.
  - Components: profile form.
  - Actions: save.

### Listing Management Pages
- **Demand Listing List**
  - Purpose: manage own demand listings.
  - Components: create CTA, filter bar, listing tiles, pagination.
  - Actions: create, filter, open detail.
- **Supply Listing List**
  - Purpose: manage own supply listings.
  - Components: create CTA, filter bar, listing tiles, pagination.
  - Actions: create, filter, open detail.
- **Demand Listing Form (create/edit)**
  - Purpose: create or edit demand listing.
  - Components: form fields + submit/cancel.
  - Actions: submit, cancel.
- **Supply Listing Form (create/edit)**
  - Purpose: create or edit supply listing.
  - Components: form fields + submit/cancel.
  - Actions: submit, cancel.
- **Demand Listing Detail**
  - Purpose: listing detail, owner actions, suggestions, listing conversations.
  - Components: metadata, status, owner avatar, suggestion cards, conversations panel, owner action buttons.
  - Actions: pause/resume/reactivate, edit, delete, save/message/dismiss suggestions, open thread.
- **Supply Listing Detail**
  - Purpose: mirror of demand detail for supply listings.
  - Components/Actions: equivalent to demand detail with withdraw/reactivate semantics.
- **Delete Confirmation**
  - Purpose: confirm listing deletion.
  - Components: warning copy + confirm/cancel.
  - Actions: confirm delete, cancel.

---

## 5. NAVIGATION STRUCTURE

### Top-Level Navigation (authenticated)
- Dashboard
- Discover
- Watchlist
- Messages (with unread badge)
- Your Listings: Supply, Demand
- Profile
- Log out

### Top-Level Navigation (unauthenticated)
- Log in
- Sign up

### Secondary / Page-Level Navigation
- Dashboard: create demand/supply listing buttons; Discover CTA.
- Discover: in-form search controls + Clear.
- Listing lists: in-page filter bar + pagination controls.
- Listing details: Back to list, edit/toggle/delete owner actions.
- Profile: Edit profile + Back to dashboard.
- Thread detail: Back to messages.
- Watchlist: Discover more CTA.

### Contextual Navigation Inside Pages
- Suggestion cards: Save / Message / Dismiss.
- Discover result cards: Save/Unsave / Message.
- Watchlist cards: Star/Unstar / Archive / Restore / Remove / Message or Open conversation.
- Listing conversations panel: direct links into related threads.

---

## 6. USER ACTION MAP

### Account
- sign up
- verify email via token link
- resend verification email
- log in
- log out

### Profile
- view profile
- edit profile settings
- upload/replace avatar

### Listings
- create demand listing
- create supply listing
- view demand/supply listing list
- filter listing list client-side
- view demand/supply listing detail
- edit listing
- toggle listing status (pause/resume/withdraw/reactivate)
- delete listing (soft-delete via status)

### Discovery and Matching
- search discover (semantic or keyword mode)
- change discover direction (find supply/find demand)
- sort discover results
- clear discover search
- save discover result to watchlist
- unsave discover result
- start conversation from discover
- save suggestion
- dismiss suggestion
- start conversation from suggestion

### Watchlist
- view active watchlist items
- view archived watchlist items
- star/unstar watchlist item
- archive/unarchive watchlist item
- remove watchlist item
- start/open conversation from watchlist item

### Messaging
- view inbox
- open thread
- send message in thread
- view read/unread state indicators

---

## 7. PAGE TRANSITION MAP

### Primary transitions
- Signup -> Verify Email (check inbox)
- Verify Email link -> Dashboard
- Login -> Dashboard
- Dashboard -> Demand Listing Detail
- Dashboard -> Supply Listing Detail
- Dashboard -> Demand Listing Create
- Dashboard -> Supply Listing Create
- Dashboard -> Discover
- Dashboard -> Watchlist
- Dashboard (suggestion message) -> Thread Detail
- Dashboard (suggestion save/dismiss) -> Dashboard
- Discover -> Listing Detail
- Discover (message) -> Thread Detail
- Discover (save/unsave) -> Discover (state restored)
- Discover (clear) -> Discover (fresh state)
- Watchlist -> Listing Detail
- Watchlist (message/open conversation) -> Thread Detail
- Watchlist (archive/delete/unarchive/star) -> Watchlist
- Inbox -> Thread Detail
- Thread Detail -> Inbox
- Profile -> Profile Edit
- Profile -> Listing Detail
- Profile -> Dashboard
- Demand/Supply List -> Demand/Supply Detail
- Demand/Supply List -> Demand/Supply Create
- Demand/Supply Detail -> Edit Form
- Demand/Supply Detail -> Delete Confirm
- Delete Confirm -> Demand/Supply List (on delete) or back to detail (on cancel)

### Verification edge transitions
- Verify Email page -> Resend Verification
- Verify Email page -> Login
- Expired verification page -> Resend Verification
- Already verified page -> Login

---

## 8. CORE USER LOOPS

### Loop A: Publish -> Match -> Connect
1. User creates a listing (supply or demand).
2. Dashboard/listing detail surfaces suggestions.
3. User saves or messages counterpart listing.
4. Conversation begins in thread.

### Loop B: Search-Led Discovery
1. User opens Discover.
2. Runs search (find supply or find demand).
3. Saves result to watchlist or starts message thread.
4. Continues in watchlist/inbox.

### Loop C: Watchlist Follow-Up
1. User saves listings from Discover/Suggestions.
2. Returns to Watchlist to prioritize (star/archive).
3. Starts or reopens conversation from item.
4. Iterates until archived/removed.

### Loop D: Conversation Management
1. User receives unread activity (navbar/inbox/watchlist indicators).
2. Opens thread from inbox/listing/watchlist.
3. Sends/replies and returns to inbox.
4. Repeat across active threads.

### Loop E: Profile and Identity Maintenance
1. User edits profile/preferences and avatar.
2. Returns to dashboard/listings/discover with updated identity/theme.

---

## 9. DEAD END DETECTION

### Page: Logged Out
- **Why it appears dead-end:** Minimal page with a single “Log back in” action; no discovery or product context links.
- **Current actions:** Log in.

### Page: Already Verified
- **Why it appears dead-end:** Single-state message with only login CTA; no fallback navigation to signup/resend/help.
- **Current actions:** Go to login.

### Page: Verification Link Expired
- **Why it appears dead-end:** One-path recovery page focused only on resend; no alternate auth/help paths.
- **Current actions:** Request new verification email.

### Page: Empty Watchlist
- **Why it appears near-dead-end:** Only one CTA (“Discover more”); no guidance toward listing creation or dashboard.
- **Current actions:** Discover more.

### Page: Empty Inbox
- **Why it appears near-dead-end:** Guidance text mentions Discover/Watchlist, but no direct buttons on page.
- **Current actions:** manual navigation via navbar/links only.

---

## 10. UX FRICTION POINTS (STRUCTURAL OBSERVATIONS)

1. **Many action endpoints are POST+redirect only**  
   Save/unsave/message/archive/toggle flows are distributed across many narrow routes; user journey logic is split between page templates and hidden POST endpoints.

2. **Dual listing terminology and route families increase cognitive load**  
   Users manage similar operations across `/wanted/*` and `/available/*` with mostly parallel UI, which duplicates navigation and mental models.

3. **Discover is form-heavy and stateful in session**  
   Query state persistence (`discover_keep_results` + multiple session keys) improves continuity but adds hidden behavior that can feel unpredictable when returning to page.

4. **Navigation highlighting appears partially mismatched to current paths**  
   `nav_section` mapping checks `"/demands"` and `"/supply"` while primary routes are `"/wanted"` and `"/available"`, likely causing inconsistent active-nav feedback.

5. **Contextual actions are scattered across multiple surfaces**  
   Save/message/dismiss appear in dashboard suggestions, discover results, listing detail suggestions, and watchlist cards with different interaction patterns.

6. **Conversation entry points are numerous and asymmetric**  
   Threads can start from Discover, Suggestions, and Watchlist; returning path is standardized (“Back to messages”), which can detach users from originating context.

7. **Deletion and status transitions are split across detail + confirm pages**  
   This is safe but increases click-depth and may fragment flow when users manage many listings.

8. **Empty-state routing is uneven**  
   Some empty states include strong CTAs (watchlist), others rely mostly on text and navbar discovery (inbox, verification variants).

9. **System complexity leaks into UX through status variants**  
   Listing actions vary by status and type (pause/resume/withdraw/reactivate/expired/deleted), which can create inconsistent button sets across similar pages.

10. **Auth/verification branch creates early-session detours**  
   Signup -> check-email -> token -> dashboard introduces multiple intermediate pages that are operationally correct but can feel like a fragmented onboarding path.

