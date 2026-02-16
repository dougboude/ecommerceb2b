# V1 Implementation Decisions (Django Stack) — Aligned to Build Spec

## Purpose
This document locks in foundational engineering decisions for V1 so execution agents do not guess, debate, or substitute alternatives.

These decisions **must not conflict** with:
- `ai-docs/v1-agent-build-spec.md` (highest authority for product requirements)
- `ai-docs/ai-constitution.md`

This document intentionally prioritizes:
- Low operational complexity
- Low dependency / attack surface
- Predictable Linux deployment
- Boring, durable architecture

---

## 1) Tech Stack (Locked)

### Backend
- Language: **Python 3.12**
- Framework: **Django**
- Architecture: Monolithic Django app (HTML + JSON endpoints where appropriate)
- No SPA framework

### Frontend
- Server-rendered Django templates
- Minimal JavaScript only where necessary
- No webpack / no React build pipeline
- Optional: HTMX allowed (single small dependency) for progressive enhancement

### Database
- **PostgreSQL** (primary target)
- SQLite allowed for local development only

### ORM
- Django ORM (no Prisma)

---

## 2) API & UI Shape

- Primary UX is server-rendered pages (templates).
- Use JSON endpoints only where it clearly simplifies the UX (e.g., message send, notifications inbox), but **do not** introduce a full API-first architecture.
- Error handling:
  - HTML forms use standard Django form errors.
  - JSON endpoints return `{ ok: true, data: ... }` or `{ ok: false, error: { code, message } }`.

---

## 3) Authentication & Authorization (V1)

- Auth: Django built-in authentication
- Sessions: Secure session cookies (HTTP-only)
- Email verification: required before posting DemandPosts or SupplyLots
- Roles: user has exactly one role in V1:
  - `buyer` or `supplier`
  - `admin` exists for internal maintenance only (Django admin)

No OAuth/SSO, no MFA in V1.

---

## 3.5) Organization Constraints (V1)

### V1 Constraint (Clarification)
- In **V1**, each Organization has **exactly one buyer user**.
- No additional organization members, invites, or role changes are supported in V1.
- The data model may allow multi-user organizations for future loops, but enforcement in V1 must be strict.


## 4) Data Model (Must Match Build Spec Fields)

The build spec’s schemas are authoritative. The Django models must represent the same concepts and fields.

### User
Additional fields beyond build spec:
- `display_name` (CharField, max_length=100, default="") — user-facing name; defaults to email prefix for existing users via data migration. `User.__str__` returns `display_name or email`.

### Common Location Structure
Store as structured fields (not a single text blob):
- `country` (required, string; ISO-ish value acceptable)
- `locality` (optional string)
- `region` (optional string)
- `postal_code` (optional string; **string** always)
- `lat` (optional float)
- `lng` (optional float)

### DemandPost (Buyer)
Fields (minimum):
- `item_text` (required)
- `category` (optional enum): `food_fresh | food_shelf | botanical | animal_product | material | equipment | other`
- `quantity_value` (optional positive integer)
- `quantity_unit` (optional, predefined choices from `UNIT_CHOICES`)
- `frequency` (required enum): `one_time | recurring | seasonal`
- `location_country` (required) + other location subfields
- `radius_km` (optional number)
- `shipping_allowed` (required boolean)
- `notes` (optional text)
- `status` enum: `active | paused | fulfilled | expired`
- timestamps: `created_at`, `updated_at`

Expiration:
- Build spec allows `expired` but does not require an explicit expires_at.
- V1 decision: add optional `expires_at` (nullable datetime). If null, it does not auto-expire.

### SupplyLot (Supplier)
Fields (minimum):
- `item_text` (required)
- `category` (optional enum as above)
- `quantity_value` (optional positive integer)
- `quantity_unit` (optional, predefined choices from `UNIT_CHOICES`)
- `available_until` (required datetime)
- location subfields (country required)
- `shipping_scope` (required enum: `local_only | domestic | north_america | international`, default `local_only`)
- `asking_price` (optional positive integer)
- `price_unit` (optional, predefined choices from `UNIT_CHOICES`)
- `notes` (optional text)
- `status` enum: `active | expired | withdrawn`
- timestamps: `created_at`

### Match
- `demand_post_id`
- `supply_lot_id`
- `created_at`
- `notified_at` (nullable datetime) — used to prevent double sends

### Messaging
- MessageThread ties to a Match
- Messages belong to a thread
- Only matched participants may view/post

---

## 5) Expiration (No Cron / No Background Workers)

To avoid “danglers,” V1 uses **lazy expiration**:

### SupplyLot active predicate
A SupplyLot is active iff:
- `status == active`
- `available_until > now()`

### DemandPost active predicate
A DemandPost is active iff:
- `status == active`
- AND (`expires_at is null OR expires_at > now()`)

Implementation note:
- Queries for “active” must include these time predicates.
- Optionally, on read/write, the server may opportunistically flip status to `expired`, but correctness must not depend on it.

---

## 6) Matching Logic (V1)

Matching is deterministic and simple (no ML).

### Trigger Direction (V1)
- On **SupplyLot creation**, evaluate against active DemandPosts.
- On **DemandPost creation**, evaluate against active SupplyLots.
(If only one is implemented first, prioritize SupplyLot → DemandPost, but both are desired for V1 completeness.)

### normalize(text)
- lowercase
- trim
- replace punctuation with spaces
- collapse whitespace
- split into tokens
- drop tokens shorter than 2 chars
- optional small stopword list: `the, a, an, and, or, of, to, for`

### overlaps(a, b)
- token intersection size >= 1
- OR substring match (either direction)

### Location compatibility (must match build spec intent)
- If `DemandPost.shipping_allowed == false`:
  - `country` must match
  - If `radius_km` is set AND both sides have `lat/lng` → compute distance (Haversine) and enforce `<= radius_km`
  - If `radius_km` is set but coordinates missing → fall back to:
    - `postal_code` equality if both present, else
    - (`locality` + `region`) equality if both present
- If `DemandPost.shipping_allowed == true` → check supplier's `shipping_scope`:
  - `international` → always compatible
  - `north_america` → both in {US, CA, MX}
  - `domestic` → same country
  - `local_only` → fall through to same-country + radius check
- If `radius_km` is null → no distance constraint (worldwide)

Quantity mismatch must not block matches.

### Match creation rules
- Enforce uniqueness: one Match per (SupplyLot, DemandPost) pair.
- On match creation, create (or ensure) the related MessageThread.

---

## 7) Notifications (Required in V1)

This resolves the earlier conflict: **V1 MUST email the buyer when a Match is created.**

### Email backends
- Dev: Django console email backend (prints emails) or file-based backend
- Prod: SMTP backend configured via environment variables (no hardcoded vendor SDK)

### Notification trigger
- On successful Match creation, send one email to the buyer.
- Use `Match.notified_at` to prevent double sends.
- Email includes:
  - item name/text
  - coarse supplier location (country + region/locality if present)
  - link to MessageThread

---

## 8.5) Rate Limiting (Required in V1)

V1 must include rate limiting for:
- signup
- login
- message sending

### Approach (Django)
Use a small, well-established dependency:
- **`django-ratelimit`** (preferred) backed by Django’s cache.

Cache backend:
- **V1 assumption:** single Django instance (per Deployment Assumptions). Use **in-memory cache** for both dev and initial production.
- If/when you scale to multiple Django instances, switch to a **shared cache** (Redis or Memcached) so rate limits are consistent across instances.

### Thresholds (V1 defaults)
- Signup: **5 attempts / hour / IP**
- Login: **10 attempts / 15 minutes / IP** (and optionally / username)
- Messages: **30 messages / 10 minutes / user**

On limit exceeded:
- HTML endpoints: return a friendly error message (HTTP 429 semantics)
- JSON endpoints: return `{ ok: false, error: { code: "RATE_LIMITED", message: "Too many requests" } }`


## 8.6) Internationalization (i18n) (Required in V1)

All user-facing strings must use Django’s built-in i18n:
- Python: `gettext_lazy()` for labels/messages
- Templates: `{% trans %}` / `{% blocktrans %}`

V1 default language: **English (`en`)**. Additional locales are not required in V1, but the code must be i18n-ready (translation keys everywhere).


## 8) Pagination Defaults (V1)

- Offset pagination
- Default page size: 25
- Max page size: 100

---

## 9) Admin (Minimal, Internal)

- Use Django admin for minimal oversight:
  - view users, posts, lots, matches, threads
  - deactivate users
- No separate admin UI beyond Django admin.

---

## 10) Testing Expectations (V1)

Minimum automated tests:
- Unit tests:
  - normalize()
  - overlaps()
  - location compatibility
- Integration test:
  - Create DemandPost + SupplyLot → Match created → email notification sent → messaging allowed

---

## 11) Deployment Assumptions (V1)

- Linux target
- Container-friendly
- Single Django service + database
- Optional shared cache **only if** running multiple Django instances (not required in V1)
- No background workers
- No cron jobs

---

## 12) Explicit Non-Goals for V1 (Reaffirmed)

- Live auctions / bidding
- Payments / escrow
- Ratings / reviews
- MFA
- Real-time push notifications
- Advanced abuse detection

---

**END**
