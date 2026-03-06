
# PRODUCT_ROADMAP.md
*NicheMarket Development Roadmap (Role‑Agnostic Architecture)*

---

# 1. Product Vision

NicheMarket is a **private discovery network for niche supply and demand**.

The platform helps people discover hard‑to‑find suppliers and connect directly with them.
The defining success moment for the product is:

> "I finally found the supplier I've been looking for."

The system focuses on:

- discovery
- matching
- messaging
- relationship formation

Transactions currently occur **outside the platform**.

Long‑term, optional marketplace capabilities (payments, escrow, logistics) may be added, but **only after the discovery network proves valuable**.

---

# 2. Core Product Model

The platform operates on a **Supply ↔ Demand model**.

There are **no permanent user roles** such as buyer or supplier.

Users interact with the platform by creating listings. All listings share a single unified model with a **type field** that determines behavior:

- **Listing (type=DEMAND)** → things they are looking for
- **Listing (type=SUPPLY)** → things they have available

A user's role is **behavioral**, determined by their actions.

Example:

User creates Listing (type=DEMAND) → acting as a demander
User creates Listing (type=SUPPLY) → acting as a supplier

Users may create **both types of listings simultaneously**.

---

# 3. Immediate Architecture Changes (Highest Priority)

The existing system must be updated to support a **role‑agnostic user model**.

These changes must be completed before further feature work.

---

## 3.1 Remove User Role Field

The `User.role` field must be removed.

The `Organization` model must be removed. The organization name becomes an optional field directly on `User`. The organization type field is not retained.

### User Schema

```
User
  id
  email
  display_name
  organization_name    (optional)
  location_country
  location_locality
  profile_image
  timezone
  distance_unit
  skin
  email_on_message
  email_verified
  created_at
```

Removed from User:

```
role
```

Removed entirely (not migrated):

```
Organization model
Organization.type
```

---

## 3.2 Unified Listing Model

All listings are represented by a **single Listing entity** with a `type` field.

### Storage Strategy

The Listing model uses a **single database table with nullable type-specific columns**. Fields that do not apply to a given listing type are stored as null. No multi-table inheritance or JSON subtype fields are used.

### Base Listing

Fields shared by all listings regardless of type:

```
Listing
  id
  type                 (SUPPLY | DEMAND)
  created_by_user_id   → User
  title
  description
  category
  status
  location_country
  location_locality
  location_region
  location_postal_code
  location_lat          (nullable, derived)
  location_lng          (nullable, derived)
  price_value          (nullable)
  price_currency       (nullable)
  created_at
  expires_at
```

### Supply‑Specific Attributes

Fields that apply only when `type = SUPPLY`. Null for DEMAND listings.

```
quantity
unit
price_unit
shipping_scope    (LOCAL_ONLY | DOMESTIC | NORTH_AMERICA | WORLDWIDE)
```

`shipping_scope` definitions:

| Value | Meaning |
|-------|---------|
| `LOCAL_ONLY` | No shipping; pickup only |
| `DOMESTIC` | Ships anywhere within the supplier's country |
| `NORTH_AMERICA` | Ships within US, Canada, and Mexico |
| `WORLDWIDE` | Ships internationally |

### Demand‑Specific Attributes

Fields that apply only when `type = DEMAND`. Null for SUPPLY listings.

```
quantity
unit
radius_km
frequency    (ONE_TIME | RECURRING | SEASONAL)
```

### Status Enum

All listings share a single status field with the following values:

| Status | Applies to | Meaning |
|--------|-----------|---------|
| `ACTIVE` | both | Visible and matchable |
| `PAUSED` | both | Hidden from discovery; owner can reactivate |
| `FULFILLED` | DEMAND only | Buyer's need has been met |
| `WITHDRAWN` | SUPPLY only | Supplier has pulled the listing |
| `EXPIRED` | both | Expiration date has passed |
| `DELETED` | both | Soft-deleted; not shown anywhere |

`FULFILLED` and `WITHDRAWN` are type-specific by convention. Setting `FULFILLED` on a supply listing or `WITHDRAWN` on a demand listing is not valid and must be prevented at the application layer.

### Price Fields on Demand Listings

`price_value` and `price_currency` are present on the base Listing model and are nullable. For supply listings, `price_value` is **per** `price_unit` when `price_unit` is provided (e.g., $100 per kg). For demand listings they are stored but **not exposed in the demand listing UI** in the current implementation. They are reserved for future use (e.g., buyer budget signals in Phase 2 matching).

### Category

Category is a shared field on all listing types. The existing category set is retained:

```
FOOD_FRESH
FOOD_SHELF
BOTANICAL
ANIMAL_PRODUCT
MATERIAL
EQUIPMENT
OTHER
```

### Complete Field Summary

| Field | SUPPLY | DEMAND |
|-------|--------|--------|
| title | ✓ | ✓ |
| description | ✓ | ✓ |
| category | ✓ | ✓ |
| status | ✓ | ✓ |
| location fields | ✓ | ✓ |
| price_value | ✓ (shown) | ✓ (stored, not shown) |
| price_currency | ✓ (shown) | ✓ (stored, not shown) |
| expires_at | ✓ | ✓ |
| quantity | ✓ | ✓ |
| unit | ✓ | ✓ |
| shipping_scope | ✓ | — |
| radius_km | — | ✓ |
| frequency | — | ✓ |

A single user may own **any number of listings of either type**.

---

## 3.3 Permission Model Update

Permission checks must rely on **object ownership**, not roles.

Examples:

Allowed actions:

- create supply listing
- create demand listing
- edit own listings
- delete own listings
- message listing owners

Example rule:

```
user == listing.created_by_user
```

A user may not message their own listing:

```
user != listing.created_by_user
```

Role checks such as:

```
if user.role == "buyer"
```

must be removed.

---

## 3.4 UI Language Changes

All UI language referencing **buyers or suppliers** must be removed.

### Replace role‑based language

Instead of:

```
Buyer Dashboard
Supplier Dashboard
```

Use:

```
Your Listings
```

Instead of:

```
Register as Buyer
Register as Supplier
```

Use:

```
Create Account
```

Instead of:

```
Create Supplier Listing
```

Use:

```
Create Listing
  → Supply
  → Demand
```

---

## 3.5 Navigation Model

Navigation should focus on **listing management**, not roles.

Example navigation:

```
Dashboard
Discover
Messages
Your Listings
  Supply
  Demand
Profile
```

---

## 3.6 Messaging Model

Messaging must attach to **listings**, not user roles.

### Thread Schema

```
MessageThread
  id
  listing_id             → Listing
  created_by_user_id     → User  (the user who initiated the conversation)
  created_at

Unique constraint: (listing_id, created_by_user_id)
```

The listing owner is always derivable as `listing.created_by_user`. No explicit second participant FK is required on the thread.

Multiple conversations can exist per listing: each watcher (created_by_user) may have at most one thread for that listing, and all such threads are between that watcher and the listing owner.

### Auto‑Save Behavior

Initiating a message thread **automatically saves the listing to the initiating user's watchlist** if it is not already saved. Saving and messaging remain linked actions: a conversation always implies the listing is on the user's watchlist.

### Watchlist and Thread Relationship

`WatchlistItem` and `MessageThread` are independent records. They are correlated by the shared `(user, listing)` pair when needed but do not have a direct foreign key relationship. This replaces the previous OneToOne between WatchlistItem and MessageThread.

---

## 3.7 Profile Page Model

User profiles may show both sides of activity.

Example layout:

```
Profile

Supply Listings
Demand Listings
```

Profiles should include:

- display name
- optional organization name
- location
- profile image
- member since date

---

## 3.8 Discover Search Direction

Because there are no user roles, the Discover page cannot infer what type of listing the user is searching for. The user must explicitly choose a search direction.

### Search Direction Selector

The Discover page presents a **search direction selector** before or alongside the search form. Any authenticated user may search **either direction** regardless of what listings they currently have.

```
Find Supply    |    Find Demand
```

- **Find Supply** — searches listings where `type = SUPPLY`
- **Find Demand** — searches listings where `type = DEMAND`

The selected direction is passed explicitly to the search engine. It persists in the session alongside other search parameters and is cleared by the Clear Search action.

Both directions use the same semantic and keyword search infrastructure. The only difference is the `type` filter applied to the query.

---


## 3.9 Discovery Visibility Model

Listings are **discoverable by authenticated users through search and suggestions**.

Matching is **not required for a listing to be visible**.

Matching and suggestions act as **assistive discovery features**, not access gates.

Rules:

- All listings with `status = ACTIVE` are searchable by authenticated users.
- Search results always return the **counterpart listing type** (SUPPLY ↔ DEMAND).
- Suggestions enhance discovery but do not control visibility.
- Listings remain private to authenticated users and are not publicly indexed.

This ensures the platform remains a **discovery network first**, rather than a gated marketplace.

---

# 4. Launch Strategy

The platform should launch **as soon as the experience feels polished and trustworthy**.

Initial outreach should target:

- chefs
- restaurants
- foragers
- small farms
- specialty ingredient suppliers

However the system itself remains **horizontal and niche‑agnostic**.

---

# 5. Minimum Launch Requirements

## 5.1 Email Verification

Users must verify email before login.

Flow:

register → verification email → confirm link → account activated

---

## 5.2 Profile Improvements

Profiles must support:

- display name
- optional organization name (no organization type)
- location
- profile image
- member since date

---

## 5.3 Profile Image Upload

Users may upload a profile image used on:

- listings
- messages
- profile pages

---

## 5.4 Radius Filtering

Discover results should respect radius filtering when location data exists.

`location_lat`/`location_lng` are optional and derived (e.g., geocoded from the location fields). Users never enter coordinates directly. If coordinates are missing, radius filtering falls back to country-only matching.

Shipping scope overrides radius filtering. A supply listing with `shipping_scope = WORLDWIDE` is compatible with any demand listing regardless of radius. A supply listing with `shipping_scope = LOCAL_ONLY` must satisfy the demand listing's radius constraint.

---

## 5.5 Listing Expiry

Listings automatically expire after the expiration date.

Implementation options:

- scheduled background job
- lazy expiration check during queries

---

## 5.6 Operator Tools

Minimum moderation tools:

- deactivate account
- remove listing
- review flagged content

Initial implementation may exist entirely inside Django admin.

---

# 6. Phase 1 Enhancements

## 6.1 Saved Searches

Users may save search queries and receive notifications when new matching listings appear.

---

## 6.2 Standing Demand

Users can define persistent needs.

Example:

```
Standing Demand
• wild morels
• horseradish root
• heritage rye
```

Users receive alerts when supply appears.

---

## 6.3 Listing Duplication

Users may duplicate listings for recurring or seasonal supply/demand.

---

# 7. Phase 2 Discovery Improvements

## 7.1 Semantic Suggestions

Future discovery should use embeddings to recommend similar listings.

Workflow:

listing created → embedding generated → nearest listings of opposite type identified → suggestions displayed

---

## 7.2 Automatic Tags

Extract tags automatically from listing descriptions to improve discovery.

Example:

"Heirloom wheat cultivars"

tags:

- wheat
- grain
- heirloom

---

## 7.3 Currency Support

Listings already store `price_value` and `price_currency` in the base schema. Phase 2 exposes these fields fully in the demand listing UI and adds UI-level currency conversion for display purposes.

Stored values remain in their original currency. The database is not updated when exchange rates change.

---

## 7.4 Unit Conversion

Display quantities in preferred units.

Example:

```
Listing: 100 kg
Display: 100 kg (≈ 220 lb)
```

Database stores original values.

---

# 8. Phase 3 Trust Infrastructure

## 8.1 Verified Suppliers

Users who post supply listings may optionally verify their identity or credentials.

Verified accounts receive a badge visible on their listings and profile.

---

## 8.2 Reputation Signals

Profiles may eventually show:

- listing volume
- response rate
- membership age

---

## 8.3 Moderation Tools

Add tools for:

- listing flagging
- spam detection
- report management

---

# 9. Features Intentionally Deferred

The following are intentionally postponed:

- payment processing
- escrow
- auctions
- bidding
- logistics integration
- mobile apps

The platform will first validate value as a **supply discovery network**.

---

# 10. Long‑Term Direction

If the network grows successfully, the platform may evolve toward:

- optional marketplace transactions
- escrow services
- logistics integrations
- supplier storefronts
- APIs

However the core mission remains:

**help people discover the suppliers they have been searching for.**
