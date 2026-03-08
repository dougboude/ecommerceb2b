# Manual Test Script — Niche Supply / Professional Demand Platform

## About This Document

This is the living manual QA checklist for the platform. It is updated each time a feature ships.
Use it for exploratory regression testing before merging to main, handing off to a new tester,
or verifying a deployment.

**How to use:**
- Work top to bottom. Each section builds on the previous one.
- Mark each item `[x]` pass, `[-]` skip (with note), or `[!]` fail (record what happened).
- A fresh database is recommended. See Setup below.
- Record your name, date, and build (git commit hash or branch) at the top of your run.
- Items marked `[AUTO]` are high-value future automation candidates.

**Tester:** ___________________________
**Date:** ___________________________
**Branch / Commit:** ___________________________
**Environment:** `localhost:8000`

---

## Setup

### Option A — Full reset (recommended)

Starts the ecosystem, seeds the database, and rebuilds the vector index for
semantic search. One command does everything:

```bash
bash qa/full_reset.sh
```

The embedding sidecar takes 60–90 seconds on first start (model loading).
`full_reset.sh` waits for it automatically before seeding or indexing.
Press **Ctrl-C** when you are done testing to stop all services.

### Option B — DB reset only (ecosystem already running)

If the ecosystem is already up and you just want to re-seed without restarting:

```bash
bash qa/reset_and_seed.sh
.venv/bin/python manage.py rebuild_vector_index
```

### Option C — Start only (keep existing data)

```bash
bash start.sh
```

### Seed Personas

After running `reset_and_seed.sh`, the following accounts are available.
**Password for all accounts: `Seedpass1!`**

| Email | Name | State | Notes |
|---|---|---|---|
| alice@seed.test | Alice Thornton | Verified, has avatar | 3 active supply, 1 paused, 1 expired |
| bob@seed.test | Bob Mercado | Verified, has avatar | 2 active demand, 1 paused, 1 expired, unread message |
| carol@seed.test | Carol Vance | Verified, **no avatar** | 1 supply + 1 demand listing |
| dave@seed.test | Dave Okonkwo | Verified, has avatar | 1 active, 1 fulfilled, 1 withdrawn supply; unread message |
| eve@seed.test | Eve Nakamura | **UNVERIFIED** | Tests login-blocking and resend-verification flows |

Pre-wired relationships:
- Bob has messaged Alice about tomatoes (3 messages; Alice has 1 **unread**)
- Carol has messaged Alice about lavender (2 messages; both have read)
- Bob has messaged Dave about salmon (1 message; Dave has 1 **unread**)
- Bob watches Alice's tomato and lavender listings
- Dave watches Carol's blueberry listing
- Bob has dismissed Alice's sunflower oil listing

Open `http://127.0.0.1:8000` once `start.sh` reports all three services healthy.

Use two different browsers (or one browser + one private window) when testing
messaging between two users.

---

## Section 1 — Account Registration and Email Verification

### 1.1 Sign up — new account `[AUTO]`

- [ ] Navigate to `/signup/`
- [ ] Fill in: Email, Display Name, Country (pick any), Password, Confirm Password
- [ ] Submit
- [ ] **Expected:** Redirected to `/verify-email/` with a message saying a verification email was sent
- [ ] **Expected:** Console backend (default) prints the email — find the verification link in your terminal output

### 1.2 Verify email `[AUTO]`

- [ ] Copy the verification link from the terminal and paste it in the browser
- [ ] **Expected:** Redirected to dashboard `/` with a success message
- [ ] **Expected:** User is now logged in

### 1.3 Sign up — duplicate email

- [ ] Try signing up again with the same email
- [ ] **Expected:** Form shows an error — email already in use

### 1.4 Login blocked before verification

- [ ] Log out
- [ ] Create a second account (new email) — do NOT verify it
- [ ] Attempt to log in with that unverified account
- [ ] **Expected:** Login blocked with a message explaining verification is required and offering a resend link

### 1.5 Resend verification email

- [ ] Click the resend link from 1.4
- [ ] **Expected:** New verification email sent (visible in terminal)
- [ ] Verify via the new link
- [ ] **Expected:** Login succeeds

### 1.6 Verification link reuse safety

- [ ] Complete a successful verification flow using a fresh verification link
- [ ] Immediately open the exact same verification link again (same browser tab or new tab)
- [ ] **Expected:** System returns a safe, friendly "already used" or invalid-link style result
- [ ] **Expected:** No error page/traceback is shown and account state remains correct

### 1.7 Log out and log back in `[AUTO]`

- [ ] Log out via the nav bar
- [ ] Log back in
- [ ] **Expected:** Redirected to dashboard

---

## Section 2 — Profile

### 2.1 View profile

- [ ] Navigate to `/profile/`
- [ ] **Expected:** Your display name, organization (if any), country, member-since date are shown
- [ ] **Expected:** A profile avatar (default silhouette placeholder) is displayed
- [ ] **Expected:** A "Change photo" button/label is visible

### 2.2 Edit profile

- [ ] Click "Edit profile"
- [ ] Change your Display Name
- [ ] Change your theme (try "Warm Editorial")
- [ ] Save
- [ ] **Expected:** Page reloads with the new display name and the new skin applied site-wide
- [ ] Switch back to "Simple Blue" and save

### 2.3 Profile image — upload flow `[AUTO]`

- [ ] Navigate to `/profile/`
- [ ] Click "Change photo"
- [ ] **Expected:** A file picker opens
- [ ] Select any photo from your computer (JPEG or PNG, larger than 256×256)
- [ ] **Expected:** A crop modal appears showing your photo with a square crop box
- [ ] **Expected:** A circular preview of the current crop is visible in the modal
- [ ] Drag and resize the crop box
- [ ] **Expected:** The circular preview updates as you adjust
- [ ] Click "Use this photo"
- [ ] **Expected:** Modal closes, avatar on the profile page updates in place (no full reload)
- [ ] **Expected:** The new avatar is a circle

### 2.4 Profile image — cancel crop

- [ ] Click "Change photo" again
- [ ] When the crop modal opens, click "Cancel"
- [ ] **Expected:** Modal closes without changing the avatar

### 2.5 Profile image — invalid file

- [ ] Click "Change photo"
- [ ] Try uploading a `.gif` or `.txt` file
- [ ] **Expected:** An error message appears (unsupported file type)

### 2.6 Profile image — tiny image rejection

- [ ] If you have access to a very small image (under 256×256 pixels), try uploading it
- [ ] **Expected:** An error message appears (image too small)

### 2.7 Profile image — replacement propagation

- [ ] Upload profile image A and confirm it appears on `/profile/`
- [ ] Upload profile image B immediately after
- [ ] **Expected:** Image B replaces image A on `/profile/`
- [ ] Navigate through normal flows where avatars render (at least one listing detail owner block and one message thread)
- [ ] **Expected:** Only image B is shown in those views
- [ ] **Expected:** No stale display of image A appears during normal navigation/reload

### 2.8 Profile image — transparent PNG rendering

- [ ] Upload a transparent PNG avatar (with visible transparent edges/corners)
- [ ] **Expected:** Avatar renders correctly (not broken, not black-boxed, not distorted)
- [ ] Switch theme to "Warm Editorial" and verify avatar appearance
- [ ] Switch theme to "Simple Blue" and verify avatar appearance
- [ ] **Expected:** Avatar looks acceptable and consistent in both themes

---

## Section 3 — Supply Listings

### 3.1 Create a supply listing `[AUTO]`

- [ ] Navigate to `/available/new/`
- [ ] Fill in: Item (e.g. "Heritage Tomatoes"), Category, Quantity, Unit, Location (Country required)
- [ ] Optionally fill Asking Price, Available Until, Notes
- [ ] Submit
- [ ] **Expected:** Redirected to the listing detail page
- [ ] **Expected:** Listing shows "Active" status badge

### 3.2 View supply listing detail

- [ ] On the detail page, verify all fields you entered are displayed correctly
- [ ] **Expected:** Your avatar (or default placeholder) is displayed alongside your name in a "listing owner" block at the top
- [ ] Click your avatar
- [ ] **Expected:** A lightbox modal opens showing a larger version of the avatar
- [ ] **Expected:** The modal blocks all page interaction while open
- [ ] Click outside the image or the close button
- [ ] **Expected:** Modal closes

### 3.3 Edit a supply listing

- [ ] From the detail page, click "Edit"
- [ ] Change the item name
- [ ] Save
- [ ] **Expected:** Detail page shows the updated name

### 3.4 Pause and unpause a supply listing

- [ ] From the detail page, click "Pause"
- [ ] **Expected:** Status badge changes to "Paused"
- [ ] **Expected:** Edit/Pause buttons are hidden or replaced with "Unpause"
- [ ] Click "Unpause"
- [ ] **Expected:** Status returns to "Active"

### 3.5 Supply listing list page

- [ ] Navigate to `/available/`
- [ ] **Expected:** Your listing appears in the list
- [ ] **Expected:** Status badge shows "Active"

### 3.6 Delete a supply listing

- [ ] Create a second supply listing (for deletion testing)
- [ ] From its detail page, click "Delete" (or "Withdraw")
- [ ] Confirm if prompted
- [ ] **Expected:** Listing no longer appears in `/available/`

### 3.7 Expired supply listing — lazy flip and vector index sync `[AUTO]`

- [ ] Set an "Available Until" date in the past on an active supply listing and save
- [ ] Navigate away, then return to its detail page
- [ ] **Expected:** Status badge shows "Expired"
- [ ] **Expected:** Edit, Pause, and Withdraw buttons are hidden
- [ ] **Expected (lazy DB flip):** Refreshing the detail page a second time still shows "Expired" — the status was written to the DB on first visit, not re-evaluated each time
- [ ] Go to Discover and search for the expired item's keywords
- [ ] **Expected (vector sync):** The expired listing does not appear in results
- [ ] Edit the listing and set a future "Available Until" date, then save
- [ ] **Expected (re-activation):** Listing status returns to Active and reappears in Discover search results

---

## Section 4 — Demand Listings

### 4.1 Create a demand listing `[AUTO]`

- [ ] Navigate to `/wanted/new/`
- [ ] Fill in: Item (e.g. "Organic Oats"), Category, Minimum Quantity, Unit, Frequency, Location
- [ ] Submit
- [ ] **Expected:** Redirected to the demand listing detail page
- [ ] **Expected:** Listing shows "Active" status

### 4.2 View demand listing detail

- [ ] Verify all fields are shown correctly
- [ ] **Expected:** Your avatar and name are shown in the owner block
- [ ] Test the lightbox on the avatar (click → modal opens → dismiss)

### 4.3 Edit a demand listing

- [ ] Click "Edit", change the item name, save
- [ ] **Expected:** Updated name appears on the detail page

### 4.4 Toggle demand listing (pause/unpause)

- [ ] Pause the listing
- [ ] **Expected:** Status badge shows "Paused"
- [ ] Unpause it
- [ ] **Expected:** Status returns to "Active"

### 4.5 Delete a demand listing

- [ ] Create a second demand listing for deletion testing
- [ ] Delete it
- [ ] **Expected:** No longer appears in `/wanted/`

### 4.6 Expired demand listing — lazy flip and vector index sync `[AUTO]`

- [ ] Set an expiry date in the past on an active demand listing and save
- [ ] Navigate away, then return to its detail page
- [ ] **Expected:** Status badge shows "Expired"
- [ ] **Expected (lazy DB flip):** Refreshing the detail page a second time still shows "Expired"
- [ ] Go to Discover and search for the expired item's keywords
- [ ] **Expected (vector sync):** The expired listing does not appear in results
- [ ] Edit the listing and set a future expiry date, then save
- [ ] **Expected (re-activation):** Listing status returns to Active and reappears in Discover search results

---

## Section 5 — Discover

### 5.1 Discover — basic supply search `[AUTO]`

> You need another user account with an active supply listing to make results appear.
> If testing solo, create User A (supply listing) and User B (demand user) in separate browser windows.

- [ ] Log in as User B
- [ ] Navigate to `/discover/`
- [ ] Select direction: "Find Supply"
- [ ] Enter a keyword matching User A's supply listing item
- [ ] Click Search
- [ ] **Expected:** User A's listing appears in results

### 5.2 Discover — basic demand search

- [ ] Select direction: "Find Demand"
- [ ] Enter a keyword matching a demand listing
- [ ] **Expected:** Matching demand listings appear

### 5.3 Discover — sort order

- [ ] Run a search that returns multiple results
- [ ] Change the Sort dropdown to "Newest posted"
- [ ] **Expected:** Results reorder in the browser without a new search request
- [ ] Change to "Best match"
- [ ] **Expected:** Results reorder again

### 5.4 Discover — watchlist a result

- [ ] From a discover result, click "Save" on a listing
- [ ] **Expected:** Button changes to "Saved" or similar
- [ ] Navigate to `/watchlist/`
- [ ] **Expected:** The saved listing appears

### 5.5 Discover — direction persists

- [ ] Run a supply search
- [ ] Navigate away (e.g. to the dashboard)
- [ ] Return to `/discover/`
- [ ] **Expected:** Previous search results are still shown

### 5.6 Discover — clear results

- [ ] On the discover page with results showing, click "Clear"
- [ ] **Expected:** Results are cleared and the search form is reset

### 5.7 Discover — direction isolation (Find Supply vs Find Demand)

- [ ] Start in "Find Supply", run a search, and note the query + result set
- [ ] Switch to "Find Demand" and run a different query
- [ ] **Expected:** Demand results reflect the demand query/direction only (not prior supply results)
- [ ] Navigate away and return to `/discover/`
- [ ] Switch directions back and forth once more
- [ ] **Expected:** Persisted state/results do not bleed incorrectly between directions

---

## Section 6 — Watchlist

### 6.1 Watchlist page `[AUTO]`

- [ ] Navigate to `/watchlist/`
- [ ] **Expected:** Any listings saved via Discover appear here with "Watching" or "Starred" status

### 6.2 Archive a watchlist item

- [ ] On the watchlist page, click "Archive" on a saved listing
- [ ] **Expected:** Item is removed from the active watchlist view

### 6.3 Suggestion counts on listing tiles

- [ ] Navigate to `/available/` or `/wanted/`
- [ ] If any suggestions exist, listing tiles should show amber/green match count badges
- [ ] (This may require having counterpart listings from another user)

---

## Section 7 — Messaging

> Requires two user accounts. Use two browsers or a browser + private window.

### 7.1 Initiate a conversation `[AUTO]`

- [ ] As User B, go to Discover and find User A's supply listing
- [ ] Click "Message" on the listing card
- [ ] **Expected:** Redirected to a new message thread at `/threads/<pk>/`
- [ ] **Expected:** The thread shows the listing details

### 7.2 Send a message

- [ ] In the thread, type a message and click "Send"
- [ ] **Expected:** Message appears in the thread with your name and timestamp
- [ ] **Expected:** Your avatar (or default placeholder) appears next to your message

### 7.3 Receive a message (as User A)

- [ ] Switch to the User A browser
- [ ] Navigate to `/messages/` (inbox)
- [ ] **Expected:** The thread from User B appears with an unread indicator
- [ ] **Expected:** The navbar "Messages" link shows an unread count badge
- [ ] Click the thread
- [ ] **Expected:** Thread opens, message from User B is visible with their avatar
- [ ] **Expected:** Unread badge disappears after viewing

### 7.4 Reply

- [ ] As User A, reply in the thread
- [ ] Switch back to User B
- [ ] **Expected:** Reply appears in User B's thread view (may require reload if SSE is not running)

### 7.5 Real-time delivery (requires SSE service running)

- [ ] Open the thread in both User A and User B browsers simultaneously
- [ ] As User B, send a message
- [ ] **Expected:** Message appears live in User A's browser without a reload
- [ ] **Expected:** User A's inbox unread count updates live

### 7.6 Listing detail — conversations panel (owner view)

- [ ] As User A, navigate to the supply listing that was messaged about
- [ ] **Expected:** A "Conversations" section shows the thread from User B

### 7.7 Self-messaging prevention

- [ ] Log in as a user who owns at least one listing
- [ ] Open one of that user's own listing detail pages
- [ ] **Expected:** UI does not offer a "Message" action to start a conversation with self
- [ ] **Expected:** No self-thread is created from normal owner-facing listing flows

---

## Section 8 — Theming / Skins

### 8.1 Switch skins

- [ ] Navigate to `/profile/edit/`
- [ ] Change theme to "Warm Editorial" and save
- [ ] **Expected:** The entire site re-renders in the warm cream/coral editorial style
- [ ] **Expected:** All page elements (nav, buttons, cards, forms) use the new theme
- [ ] Switch back to "Simple Blue"
- [ ] **Expected:** Clean blue/gray utilitarian style is restored

### 8.2 Unauthenticated skin

- [ ] Log out
- [ ] **Expected:** The site displays in the Simple Blue default skin
- [ ] Log back in
- [ ] **Expected:** Your saved skin preference is restored

---

## Section 9 — Cross-Cutting Checks

### 9.1 Avatars appear on all required surfaces

- [ ] Profile page: your avatar is shown at the top with a "Change photo" control
- [ ] Supply listing detail page: listing owner's avatar is shown in the owner block
- [ ] Demand listing detail page: same
- [ ] Message thread: each message shows the sender's avatar
- [ ] All avatars render as circles

### 9.2 Default avatar fallback

- [ ] Create a fresh user account (do not upload a photo)
- [ ] Log in and visit `/profile/`
- [ ] **Expected:** A neutral silhouette placeholder is shown — no broken image
- [ ] Create a listing with this user
- [ ] View the listing detail as another user
- [ ] **Expected:** Default silhouette is shown in the owner block — no broken image

### 9.3 Navigation

- [ ] Verify the navbar contains: Dashboard, Discover, Watchlist, Messages, Supply, Demand, Profile, Log out
- [ ] No role labels ("Buyer", "Supplier") should appear anywhere in the UI
- [ ] All nav links route to the correct pages

### 9.4 Permission guards `[AUTO]`

- [ ] While logged in as User A, try manually navigating to edit/delete a listing owned by User B
  (e.g. `/available/<user_b_pk>/edit/`)
- [ ] **Expected:** 403 Forbidden or redirect — you cannot mutate another user's listing

### 9.5 Login required

- [ ] Log out
- [ ] Try navigating to `/profile/`, `/available/new/`, `/messages/`
- [ ] **Expected:** Each redirects to `/login/`

### 9.6 CSRF protection

- [ ] All forms (signup, login, message send, profile edit) should include a CSRF token
- [ ] (Verify by inspecting page source — a hidden `csrfmiddlewaretoken` input should be present)

---

## Section 10 — Edge Cases

### 10.1 Listing filter bar

- [ ] Navigate to `/available/` with multiple listings
- [ ] Type in the filter input
- [ ] **Expected:** Tiles that don't match the query are hidden instantly (no page reload)
- [ ] **Expected:** "X / Y" match counter updates
- [ ] Press Escape or click the X button
- [ ] **Expected:** Filter is cleared and all tiles are shown again

### 10.2 Expired listing — no edit actions and lazy flip idempotency

- [ ] View a listing with an expiry date in the past (first visit after expiry)
- [ ] **Expected:** Status shows "Expired"
- [ ] **Expected:** Edit, Pause, and Withdraw buttons are not shown
- [ ] Reload the same detail page
- [ ] **Expected:** Page loads normally — no error, status still "Expired" (DB flip is idempotent)

### 10.3 Long content

- [ ] Create a listing with a very long item name and notes
- [ ] **Expected:** Text wraps gracefully — no layout overflow

### 10.4 Mobile layout

- [ ] Resize the browser to a narrow viewport (≤600px) or use DevTools mobile emulation
- [ ] **Expected:** Layout stacks vertically, no horizontal overflow
- [ ] **Expected:** Forms, cards, and navigation are usable at mobile width

---

## Known Limitations (Out of Scope for Current Build)

The following are intentionally not implemented and do not need to be tested:

- Per-listing images (photos of items being sold/wanted) — future spec
- Removing a profile avatar without replacing it — no remove-only flow
- Email notifications for listing expiry
- CDN / S3 for media files — filesystem only in V1
- Admin UI enhancements — Django admin at `/admin/` exists but is barebones
- Radius-based geographic filtering:
  - What works now: country/location text fields and standard keyword/discover matching.
  - What is not expected yet: true distance-based filtering (e.g. "within 25 miles/km"), map-radius logic, or geospatial sorting by distance.
  - QA note: missing radius behavior alone should not be logged as a regression for this build.

---

## Future Automation Targets

Use these `[AUTO]` items first when converting manual checks into automated suites:

- Account flow: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7
- Listing creation: 3.1 and 4.1
- Lazy expiry flip + vector sync: 3.7 and 4.6
- Discover/search: 5.1 and 5.7
- Watchlist: 6.1
- Messaging: 7.1 and 7.7
- Profile image upload: 2.3, 2.7, 2.8
- Permission boundaries: 9.4

---

## Reporting Failures

When you find a bug, record:

1. **Test case:** e.g. "Section 3.2 — avatar lightbox"
2. **Steps to reproduce:** exactly what you did
3. **Expected result:** what should have happened
4. **Actual result:** what actually happened
5. **Screenshot or error message** if available
6. **Browser and OS**

---

*Last updated: 2026-03-08 — covers Features 1–11 + lazy expiry DB flip and vector index sync (supply and demand detail views)*
