# NicheMarket — Product Brief for External Review

**Audience:** Consultants, product reviewers, and anyone evaluating the current state of the
product to suggest features, improvements, or enhancements.

**This document is not technical documentation.** It describes what the product does from a
user and product perspective. For architecture, data models, and how to run the stack, see
[README.md](README.md).

**Current build status:** Feature-complete for the intended V1 + V3 scope. All core workflows
are implemented and working. This is a development build — not publicly deployed.

---

## What NicheMarket Is

A private, authenticated web platform that connects buyers who need hard-to-find niche goods
with suppliers who have them. Think specialty food ingredients, surplus equipment, botanical
products, unusual raw materials — anything where supply and demand are real but the audience
is too small and too specialized for general-purpose marketplaces.

**It is not a public storefront.** All content is behind a login. Buyers and suppliers only
see each other's listings when the system identifies a match or when they find each other
through search.

**It does not process payments.** NicheMarket facilitates the introduction. Transactions
happen outside the platform.

---

## Roles

Every account is permanently assigned one of two roles at signup. There is no way to switch
roles after registration.

### Buyer
Represents an organization (restaurant, manufacturer, research lab, retailer, etc.) sourcing
specific goods. At signup, buyers must provide an organization name. One account = one
organization.

### Supplier
An individual or business offering goods for sale, often in limited quantity or for a
limited time. No organization entity required.

---

## Registration & Onboarding

- Registration is currently **open** — anyone with an email address can sign up. There is no
  invite code, waitlist, or admin approval step.
- Required at signup: email, display name, password, role (buyer/supplier), country.
- Buyers additionally provide: organization name, organization type (optional, free text).
- Email verification exists in the data model but **no verification flow is currently
  implemented** — users can log in immediately after signup.
- After signing up, the user lands on the dashboard. No guided onboarding or setup wizard
  exists; the experience on a fresh account is a sparse dashboard with empty states.

---

## Wanted Listings (Buyers)

Buyers post what they need. A wanted listing captures:

| Field | Notes |
|-------|-------|
| Item description | Free text, up to 500 characters |
| Category | Food (fresh), Food (shelf-stable), Botanical, Animal product, Material, Equipment, Other |
| Quantity | Numeric value + unit (kg, lb, units, etc.) — labelled "minimum quantity" |
| Frequency | One-time, Recurring, or Seasonal |
| Location | Country (required), city/town, state/province, postal code |
| Search radius | Miles or km (based on user preference); leave blank for worldwide |
| Include shipped items | Checkbox — extends matching to suppliers who can ship, beyond the radius |
| Notes | Free text for additional context |
| Expiry date | Optional — listing can be set to expire at a future date |

### Wanted Listing Lifecycle
- **Active** → visible to suppliers in search and suggestions
- **Paused** → hidden from search and suggestions; manually toggled by the owner
- **Fulfilled** → owner manually marks need as met; same effect as paused
- **Expired** → reached the expiry date (status exists in the data model; automated
  expiry processing is not yet running as a scheduled task)
- **Deleted** → soft-deleted; removed from all views but not purged from the database

Paused and fulfilled listings can be reactivated (toggled back to active). Deleted listings
cannot be restored from the UI.

---

## Available Listings (Suppliers)

Suppliers post what they have. An available listing captures:

| Field | Notes |
|-------|-------|
| Item description | Free text, up to 500 characters |
| Category | Same set as wanted listings |
| Quantity | Numeric value + unit |
| Available until | Date picker — listing expires at end of this day |
| Location | Country (required), city/town, state/province, postal code |
| Shipping scope | Local pickup only / Anywhere in my country / US, Canada & Mexico / Worldwide |
| Asking price | Whole number (no decimal); price unit (per kg, per unit, etc.) — both optional |
| Notes | Free text |

### Available Listing Lifecycle
- **Active** → visible to buyers in search and suggestions
- **Withdrawn** → owner pulls the listing; toggles back to active
- **Expired** → `available_until` date has passed (same caveat as above — automated
  processing not yet running)
- **Deleted** → soft-deleted

---

## Discover (Search)

The Discover page is the main active search tool. Both buyers and suppliers can use it to
find counterpart listings without waiting for suggestions.

**What buyers search:** Available listings from other suppliers
**What suppliers search:** Wanted listings from other buyers

### Search Modes
- **Similar meaning (semantic search):** Uses a multilingual sentence-embedding model
  (`paraphrase-multilingual-MiniLM-L12-v2`). Searching "heritage grain" will surface
  listings for "heirloom wheat cultivars" because the model understands semantic similarity,
  not just word overlap. Supports 50+ languages. Embeddings are generated when a listing
  is saved and stored persistently in ChromaDB; only the search query itself is embedded
  at query time.
- **Contains these words (keyword search):** Standard AND word matching against the item
  description field. Used as a fallback if the user prefers exact terms, or if the
  embedding sidecar is unavailable.

> **Note for reviewers:** Discover search (above) and the Suggestions engine are two
> separate systems. Discover uses the vector index. Suggestions use a keyword overlap
> algorithm. This distinction has product implications — see the Suggestions section.

### Filters
- Category (dropdown)
- Country (dropdown; defaults to the user's registered country)
- Radius (25 / 50 / 100 / any — **note: this field is captured in the UI but radius
  filtering is not currently applied to search results; it is a known gap**)

### Sort Options
- Best match (default — semantic relevance score)
- Newest posted
- Ending soon (role-aware: for buyers this sorts by supplier's `available_until`; for
  suppliers this sorts by buyer's `expires_at`)

### Other Discover Behaviours
- A hint is shown when a 1–2 word semantic query returns no results, suggesting the user
  try more descriptive terms.
- "Hide listings I'm watching" checkbox — filters out results already on the user's
  watchlist, client-side, no extra server request.
- Search parameters and results are retained in session when the user saves or unsaves a
  listing, so they return to their results rather than a blank form.
- Clicking "Clear search" resets the form and session state.

---

## Suggestions

The system automatically surfaces potential matches as suggestions, shown on:
- The dashboard (up to 5 suggestions per active listing, deduplicated, capped at 5 total)
- Each listing's detail page (up to 5 suggestions for that specific listing)

**How matching works:**
- Suggestions are computed on every page load (not cached).
- The matching algorithm is **keyword-based, not semantic.** It tokenizes the item
  description of both listings, strips stopwords and short words, then checks for token
  overlap or substring containment. This is a different engine from Discover search —
  the vector index and embedding model are not involved.
- Practical implication: "heritage grain" would not suggest a listing for "heirloom wheat
  cultivars" via suggestions, even though Discover search would find it.
- Location compatibility is also checked: the buyer's radius, shipping preference, and the
  supplier's shipping scope must be mutually compatible for a match to appear.
- Dismissed suggestions are excluded permanently (stored per user per listing).
- Watchlisted listings are still shown in suggestions but with a "Saved" indicator.

**Suggestion actions:**
- **Save** — adds to watchlist
- **Message** — saves to watchlist and immediately opens a new conversation thread
- **Dismiss** — hides this suggestion permanently; it will not reappear

---

## Watchlist

The watchlist is the user's hub for every listing they are tracking. A listing gets onto
the watchlist via three paths:
1. Saved from a suggestion card
2. Saved from a Discover search result
3. Created automatically when a conversation is started

Each watchlist item has three states:
- **Watching** — on the radar (default)
- **Starred** — high priority; displayed at the top, visually distinct
- **Archived** — no longer pursuing; conversation thread remains accessible

**Per-item information shown on the watchlist:**
- The listing title and counterparty's display name
- Listing status badge (active, paused, expired, etc.)
- Whether a conversation exists, and if so, the unread message count on the card
- Star, archive/restore, and remove actions

When a listing is deactivated (paused, withdrawn, fulfilled, deleted), watchlist items
pointing to it are automatically archived. If the listing is later reactivated, the items
are restored to "Watching".

---

## Private Messaging

Conversations are private, one-to-one, and tied to a specific listing. There is no public
comment section or shared forum.

**Key constraints:**
- One thread per (user, listing) pair. You cannot have two separate conversations about
  the same listing with the same counterparty.
- Starting a conversation always saves the listing to your watchlist first.
- If the underlying listing has been deleted, the thread is read-only — no new messages can
  be sent.

**Inbox:**
- All conversations in a single list, sorted by most recent message.
- Unread threads are visually highlighted.
- Message preview (first 120 characters of the last message) shown inline.

**Unread indicators:**
- Navbar badge showing total unread count across all threads.
- Per-thread unread count on watchlist cards.
- Both update in real-time without page refresh (via a Server-Sent Events sidecar service).

**Email notifications:**
- Opt-in per user (off by default), toggled in profile settings.
- When enabled, the user receives an email when a new message arrives in any of their
  threads.

---

## Listing Management

Both buyers and suppliers manage their listings from a dedicated list page (not the
dashboard).

- List view shows all listings as tiles, sorted by most recently created.
- Each tile shows: item description, number, status badge, quantity, category, location,
  and match counts (how many new suggestions and how many saved/watchlisted matches exist
  for that listing).
- **Instant filter bar** — type to narrow listings by name; shows a live "X / Y" match
  counter; clear button and Escape key support. Status checkboxes filter by active/paused/etc.
  when multiple statuses are present.
- Pagination at 25 items per page.
- Each listing gets a sequential number within its item description (e.g. "Widget #2" means
  the second listing for "Widget" by that user).

**Listing detail page** shows:
- Full listing fields
- Status badge and toggle button (pause/unpause for buyers; withdraw/restore for suppliers)
- Edit and delete buttons (owner only)
- Suggestions panel (owner only, active listings only)
- Conversations panel — a list of all message threads started about this listing (owner only)

---

## Profile & Account Settings

Users can edit:
- Display name, first name, last name
- Timezone (affects how dates/times are displayed)
- Distance unit preference (miles or km — affects radius field labels and values)
- Visual theme (see below)
- Email notification preference for new messages

There is no way to change email address or role from the profile UI.

---

## Visual Themes

Two themes are available, selectable from profile settings:

| Theme | Description |
|-------|-------------|
| Simple Blue (default) | Clean, utilitarian, blue and gray |
| Warm Editorial | Cream, coral, and serif typography |

Theme choice persists across sessions via a browser cookie. A user's theme is applied
before login (the cookie is read for unauthenticated visitors) and is updated on login,
signup, and profile save.

---

## What the Platform Deliberately Does Not Do

These are intentional product decisions, not missing features:

- **No payments or invoicing** — NicheMarket makes the introduction; deals happen outside
- **No auctions or bidding**
- **No ratings, reviews, or reputation system**
- **No public listings** — all content requires a login to view
- **No mobile app** — web browser only
- **No multi-user organizations** — one account owns one organization; there is no team
  membership or shared access

---

## Known Gaps and Rough Edges

These are things that exist partially or are not yet complete:

- **No email verification flow** — the data model has an `email_verified` flag but no
  verification email is sent on signup; users can log in immediately with any email address.
- **No automated listing expiry** — `expires_at` (wanted listings) and `available_until`
  (available listings) are stored and used to filter search results, but no background task
  exists to automatically flip listing status to "Expired" when the date passes.
- **Discover radius filter not applied** — the radius dropdown is present in the search form
  and its value is saved in session, but it is not currently used to filter search results.
- **No onboarding flow** — a brand-new user lands on a sparse dashboard with empty states
  and no guidance on what to do first.
- **No admin or moderation interface** — beyond the Django admin panel, there are no tools
  for a platform operator to review, flag, or remove listings or users.
- **Organization data is minimal** — buyers provide an organization name and optional type
  at signup, but there is no way to edit organization details after registration, and the
  organization information is not shown to counterparties.
- **Asking price is a whole number** — no decimal support (e.g. $1.50/kg is not possible).
- **No image attachments** — listings are text-only; no photos can be attached to a listing
  or sent in a message.

---

*For technical architecture, infrastructure setup, and developer instructions, see
[README.md](README.md).*
