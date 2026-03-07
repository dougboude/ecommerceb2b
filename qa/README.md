# QA Directory

This directory contains the manual test script and environment reset tooling
for the Niche Supply / Professional Demand platform.

---

## Quick Start

```bash
bash qa/full_reset.sh
```

That's it. One command starts the full ecosystem, seeds the database with
representative test data, and rebuilds the vector search index. Open
`http://127.0.0.1:8000` when it reports all services healthy.
Press **Ctrl-C** to stop everything when you're done.

---

## Files

| File | Purpose |
|------|---------|
| `full_reset.sh` | **Complete reset** — starts ecosystem, seeds DB, rebuilds vector index. Use this to begin a clean test session. |
| `reset_and_seed.sh` | **DB-only reset** — wipes and re-seeds the database without restarting services. Use this when the ecosystem is already running and you just need fresh data. |
| `MANUAL_TEST_SCRIPT.md` | Human test checklist covering all shipped features. Work through it top to bottom for a full regression pass. |

---

## Seed Accounts

After running either reset script, these accounts are available.
**Password for all: `Seedpass1!`**

| Email | Name | State | What to test with this account |
|-------|------|-------|-------------------------------|
| alice@seed.test | Alice Thornton | Verified, has avatar | Supplier flows — active, paused, and expired listings; unread inbox message |
| bob@seed.test | Bob Mercado | Verified, has avatar | Demand poster flows — active watchlist, messaging, discover |
| carol@seed.test | Carol Vance | Verified, **no avatar** | Both supply and demand listings; archived watchlist item; default avatar fallback |
| dave@seed.test | Dave Okonkwo | Verified, has avatar | Fulfilled and withdrawn listing history; unread inbox message |
| eve@seed.test | Eve Nakamura | **UNVERIFIED** | Login-blocking and resend-verification flows |

### Pre-wired relationships

- Bob has 3 messages with Alice about her tomato listing — **Alice has 1 unread**
- Carol has 2 messages with Alice about her lavender listing — both have read
- Bob has 1 message with Dave about his salmon listing — **Dave has 1 unread**
- Bob watches Alice's tomato and lavender listings
- Carol has an archived watchlist item (Bob's tomato demand)
- Dave watches Carol's blueberry listing
- Bob has dismissed Alice's sunflower oil listing

### Listing states in the seed data

| State | Example |
|-------|---------|
| Active | Alice — Heritage Tomatoes |
| Paused | Alice — Organic Wheat Flour |
| Expired (lazy) | Alice — Seasonal Stone Fruit |
| Fulfilled | Dave — Artisan Cheese Wheels |
| Withdrawn | Dave — Raw Beeswax Blocks |

---

## When the Ecosystem Is Already Running

If you need to re-seed without restarting (faster — skips the 90-second
embedding model load):

```bash
bash qa/reset_and_seed.sh
.venv/bin/python manage.py rebuild_vector_index
```

The `rebuild_vector_index` step is required for Discover semantic search
to return results on the fresh seed data.

---

## Maintenance Contract

**Every time a feature ships, update these QA assets:**

### 1. `seed_test_data.py`
`marketplace/management/commands/seed_test_data.py`

Add representative data for every new model, status, or user-facing state
introduced by the feature. If the feature adds a new user state, extend an
existing persona or add a new one. If it changes a model field, update
existing seed rows.

### 2. `MANUAL_TEST_SCRIPT.md`
Add a section (or subsection) for the new feature covering:
- The happy path
- Key edge cases and rejection/error states
- Mark high-value automation candidates with `[AUTO]`
- Add new `[AUTO]` items to the "Future Automation Targets" list at the bottom
- Move anything newly in-scope out of "Known Limitations"

### 3. `CLAUDE.md` (project root)
- Add new CSS classes to the Skin Contract section
- Add new services or management commands to the relevant tables
- Update the Seed Personas table if new accounts are added

The test script and seed command are **living documents**.
A feature is not fully shipped until the QA assets are updated.

---

## Creating a Django Superuser (Admin)

The seed script does not create a superuser. Create one separately:

```bash
.venv/bin/python manage.py createsuperuser
```

Then log in at `http://127.0.0.1:8000/admin/`.
