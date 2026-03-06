# NicheMarket — Private B2B Marketplace for Niche Supply & Demand

NicheMarket connects buyers who need hard-to-find goods with suppliers who have them —
privately, efficiently, and without a public storefront.

> **Looking for a product overview rather than technical docs?**
> See [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) — written for consultants and product reviewers,
> covering user flows, feature details, known gaps, and deliberate exclusions.

---

## What Is This?

NicheMarket is a **private, authenticated marketplace** for niche business-to-business trade.
Think specialty food ingredients, unusual raw materials, surplus equipment, botanical products —
anything where supply and demand are real but the audience is small and the items don't belong
on a general-purpose exchange.

If you have ever tried to source something specific — an heirloom grain variety, a surplus lot
of industrial components, a specialty animal product — and found that Google, eBay, and Alibaba
all came up short, this platform is designed for you.

**It is not a public marketplace.** Every user is authenticated. Listings are never visible to
the general public. Buyers and suppliers only see each other's listings after the system
identifies a potential match or after they find each other through search.

---

## Who Is It For?

### Buyers
A **buyer** represents an organization (a restaurant, a manufacturer, a research lab, a
retailer) that needs to source specific goods, often on a recurring basis. Buyers:
- Post what they need ("Wanted Listings") with quantity, location, category, and notes
- Receive suggestions when a supplier posts something relevant
- Search for available listings manually and contact suppliers directly
- Track all active conversations and listings from their personal watchlist

### Suppliers
A **supplier** is an individual or business that has goods to offer, often in limited quantity
or for a limited time. Suppliers:
- Post what they have available ("Available Listings") with quantity, price, location, and
  an availability window
- Receive suggestions when a buyer posts a wanted listing that matches their supply
- Search for wanted listings manually and contact buyers directly
- Available listings expire automatically when their availability window closes

---

## Core Features

### Listings

**Wanted Listings** (buyers)
- Describe what you need, how much, how often, and where you are
- Set a geographic radius or allow shipping
- Pause or close a listing when your need is fulfilled
- Listings appear in supplier search results and suggestion feeds

**Available Listings** (suppliers)
- Describe what you have, quantity, asking price, and when it is available until
- Set shipping scope (local only, domestic, North America, international)
- Listings expire automatically — no manual cleanup required
- Listings appear in buyer search results and suggestion feeds

### Discover (Semantic Search)

The Discover page lets you actively search for counterpart listings using natural language.
You do not need to post a listing first — just search and reach out.

- **Semantic search** understands meaning, not just keywords. Searching
  "heritage grain varieties" will find a listing for "heirloom wheat cultivars" because
  the system understands they mean similar things.
- **Multilingual** — the search model supports 50+ languages, so cross-language matches
  work automatically.
- **Filters** for category, country, and distance radius
- **Keyword fallback** if the semantic engine is unavailable
- Results sorted by semantic relevance
- Option to hide listings you are already watching
- Sort by best match, newest posted, or ending soon
- Your search preferences are remembered during your session

### Suggestions

The system continuously computes potential matches between your listings and counterpart
listings from other users. These appear as suggestions on your dashboard and on each
listing's detail page.

- Suggestions are computed fresh on every load — always current
- Dismiss suggestions you are not interested in; they will not reappear
- Save a suggestion to your watchlist or go straight to messaging

### Watchlist

Your watchlist is the hub for everything you are tracking. Every listing you save, message
about, or receive a suggestion for ends up here.

- **Starred** — high priority items you are actively pursuing
- **Watching** — items on your radar
- **Archived** — items you are no longer pursuing, or listings that have closed;
  conversations are still accessible
- Visual indicator when a watchlist item has an active conversation in progress
- Unread message count shown directly on the watchlist card
- Star/unstar, archive/restore, and remove actions per item

### Private Messaging

Buyers and suppliers communicate through private, threaded conversations tied to a specific
listing. There is no shared forum or public comment section — every conversation is one-to-one.

- Start a conversation from a search result, a suggestion, or your watchlist
- Starting a conversation automatically saves the listing to your watchlist
- **Real-time delivery** — new messages appear instantly without refreshing the page
- **Unread indicators** on the inbox, navbar, and watchlist
- Navbar badge shows total unread message count across all conversations
- Email notification when you receive a new message (can be turned off in profile)
- Inbox page shows all conversations sorted by most recent activity

### Listing Management

- Create, edit, pause, and close your own listings
- Instant typeahead filter bar on the listing list pages — type to narrow down
  your listings by name, with live match counter
- Listing tiles show how many new suggestions and saved matches each listing has
- Status badges (active, paused, expired, withdrawn, fulfilled) visible at a glance
- Cancel button on create and edit forms returns you to the appropriate page

### Themes

Choose between two visual themes from your profile settings:

- **Simple Blue** — clean, utilitarian, blue and gray (default)
- **Warm Editorial** — cream, coral, and serif typography

Your theme choice persists across sessions, including before you log in.

---

## What This Platform Does Not Do

The following are intentionally outside the scope of this product:

- **No payments or invoicing** — NicheMarket facilitates introductions; transactions
  happen outside the platform
- **No auctions or bidding**
- **No ratings or reviews**
- **No public listings** — all content is private and requires authentication
- **No mobile app** — web browser only

---

## Technical Overview *(for developers and operators)*

### Stack
- Python 3.12 / Django 5 / SQLite (dev) or PostgreSQL (prod)
- Server-rendered templates, no JavaScript framework
- Two FastAPI sidecar services (see below)

### Sidecar Services

The application runs as three coordinated processes:

| Service | Purpose | Transport |
|---------|---------|-----------|
| Django (`manage.py runserver`) | Main application | TCP :8000 |
| Embedding sidecar (`services/embedding/`) | Semantic search via SentenceTransformers + ChromaDB | Unix socket |
| SSE relay sidecar (`services/sse/`) | Real-time message delivery to browsers | TCP :8001 |

**Starting the full ecosystem:**
```bash
bash start.sh
```
This starts all three services, waits for each to become healthy, then streams live logs
to the terminal. Press Ctrl-C to stop everything cleanly.

```bash
bash stop.sh
```
Stops everything, whether started via `start.sh` or manually.

### Semantic Search Architecture
- Model: `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions, 50+ languages, runs on CPU)
- Vector store: ChromaDB (persistent, file-based at `data/chroma/`)
- Model loads once at sidecar startup (~60–90 seconds cold start)
- Django never waits for the model — it communicates with the already-running sidecar
- If the sidecar is down, search falls back silently to keyword (`icontains`) search

### Real-Time Messaging Architecture
- Browser connects to the SSE relay via `EventSource` (long-lived HTTP stream)
- Django publishes a `new_message` event to the relay when a message is sent
- The relay fans the event out to the recipient's connected browser(s)
- Updates: thread view (new message inserted), inbox (thread marked unread, preview updated),
  navbar badge (total unread count), watchlist (per-thread unread count on card)

### Running Tests
```bash
.venv/bin/python manage.py test marketplace
```

### Key Directories
```
marketplace/          Django app (models, views, forms, matching logic)
services/embedding/   Semantic search sidecar (FastAPI + ChromaDB)
services/sse/         Real-time relay sidecar (FastAPI + EventSource)
templates/            Django HTML templates
static/css/           Skin CSS files (one file per theme)
static/js/            Browser JS (SSE client)
data/chroma/          ChromaDB vector store (gitignored)
logs/                 Runtime logs from start.sh (gitignored)
ai-docs/              Product specs and session status (for AI agents)
```

---

## Current Status

The platform is feature-complete for its intended V1 + V3 scope. All core workflows —
posting, discovering, suggesting, watchlisting, and messaging — are implemented and working.

**Recent additions not yet in a tagged release:**
- Start/stop ecosystem scripts (`start.sh`, `stop.sh`)
- Watchlist "In conversation" badge with live unread count
- Real-time watchlist unread count updates via SSE
- Cancel buttons on create/edit listing forms
- Shutdown now waits for processes to actually exit before reporting done

---

*This is a private development project. Not publicly deployed.*
