# V1 AGENT-FIRST BUILD SPEC

**Project:** Niche Supply ↔ Professional Demand Platform  
**Status:** V1 / Loop 1  
**Audience:** AI coding agents (primary), human reviewer (secondary)

---

## 1. MISSION & NON-GOALS

### Mission (Immutable)
Enable fast, private connection between **niche supply** and **professional demand** at the moment value is time-sensitive.

### Non-Goals (Do Not Implement)
The following are explicitly **out of scope** for V1:
- Payments, escrow, invoicing
- Auctions or bidding
- Ratings, reviews, reputation systems
- Compliance automation
- Public browsing/search marketplace
- Mobile apps
- Monetization logic

⚠️ **Agents must not invent or scaffold placeholders for non-goals.**

---

## 2. CORE LOOP (CANONICAL — DO NOT ALTER)

1. Buyer posts DemandPost  
2. Supplier posts SupplyLot  
3. System evaluates matches  
4. Buyer is notified of relevant supply  
5. Buyer and Supplier connect privately

This loop is the **entire product** for V1.

---

## 3. DOMAIN VOCABULARY (AUTHORITATIVE)

- **User**: an authenticated person  
- **Organization**: a business entity (buyers belong to one)  
- **Buyer**: User acting on behalf of an Organization  
- **Supplier**: User offering supply (individual or business)  
- **DemandPost**: buyer-created statement of need  
- **SupplyLot**: supplier-created statement of availability  
- **Match**: system-detected overlap between DemandPost and SupplyLot  
- **Notification**: system-initiated alert (email)  
- **MessageThread**: private buyer↔supplier conversation  

---

## 4. ROLES & ACCESS RULES

### Roles
- `buyer`
- `supplier`
- `admin` (internal only)

### Access Invariants
- Buyers may only see SupplyLots after a Match  
- Suppliers may only see DemandPosts after a Match  
- No public visibility of posts  
- Users may not message without a Match  

Violation of these rules is a **critical bug**.

---

## 5. DATA SCHEMAS (V1)

### User
- id
- email (verified)
- password_hash
- role (`buyer` | `supplier`)
- display_name (string, max 100 chars, default derived from email)
- country (ISO string)
- created_at

### Organization (buyers only)
- id
- name
- type (e.g., restaurant)
- country
- created_at

### DemandPost
- id
- organization_id
- created_by_user_id
- item_text (string, required)
- category (enum, optional):  
  `food_fresh | food_shelf | botanical | animal_product | material | equipment | other`
- quantity_value (positive integer)
- quantity_unit (predefined choices — see `UNIT_CHOICES` in `constants.py`)
- frequency (`one_time | recurring | seasonal`)
- location:
  - country (required)
  - locality (city/town)
  - region (state/province/free text)
  - postal_code (string)
- radius_km (number | null)
- shipping_allowed (boolean)
- notes (text)
- status (`active | paused | fulfilled | expired`)
- created_at
- updated_at

### SupplyLot
- id
- created_by_user_id
- item_text (string, required)
- category (same enum as DemandPost)
- quantity_value (positive integer)
- quantity_unit (predefined choices — see `UNIT_CHOICES` in `constants.py`)
- available_until (datetime, required)
- location (same structure as DemandPost)
- shipping_scope (enum: `local_only | domestic | north_america | international`, default `local_only`)
- asking_price (positive integer | null)
- price_unit (predefined choices — see `UNIT_CHOICES` in `constants.py`)
- notes (text)
- status (`active | expired | withdrawn`)
- created_at

### Match
- id
- demand_post_id
- supply_lot_id
- created_at
- notified_at

### MessageThread
- id
- match_id
- buyer_user_id
- supplier_user_id
- created_at

### Message
- id
- thread_id
- sender_user_id
- body
- created_at

---

## 6. MATCHING RULES (V1 SIMPLE)

### Matching Intent
Detect *plausible* overlap, not perfect optimization.

### Matching Algorithm (Pseudocode)
```
for each new SupplyLot S:
  for each active DemandPost D:
    if normalize(S.item_text) overlaps normalize(D.item_text):
      if location_compatible(S, D):
        create Match
        notify Buyer
```

### Location Compatibility
- If `D.shipping_allowed == false`:
  - Country must match
  - If `radius_km` is set → distance ≤ radius_km
- If `D.shipping_allowed == true` → check supplier's `shipping_scope`:
  - `international` → always compatible
  - `north_america` → both in {US, CA, MX}
  - `domestic` → same country
  - `local_only` → fall through to radius/country check
- If `radius_km` is null → no distance constraint (worldwide)

### Quantity Rules
- Quantity mismatch must NOT block a match  
- Quantity is informational only in V1  

⚠️ Do NOT:
- add ranking scores
- introduce ML
- add fuzzy weighting beyond simple normalization

---

## 7. NOTIFICATIONS (V1)

### Channel
- Email only

### When to Notify
- On Match creation
- One email per match

### Notification Content
- Item name
- Supplier location (coarse)
- Link to MessageThread

---

## 8. UI / UX CONTRACT (MINIMUM BAR)

### General
- Every screen has one primary action
- No “Coming Soon” UI
- No feature toggles exposed to users

### Buyer Experience
- Can create DemandPost in ≤ 2 minutes
- Can pause or close DemandPost
- Can receive notifications reliably

### Supplier Experience
- Can create SupplyLot quickly
- SupplyLot auto-expires at `available_until`
- Can see interest via MessageThread

---

## 9. I18N & FUTURE-PROOFING GUARDRAILS

- All user-facing text uses translation keys
- Country is required everywhere
- Postal codes are strings
- Unit fields use a predefined choice list (`UNIT_CHOICES` in `constants.py`) organized by category
- All timestamps stored in UTC

---

## 10. SECURITY BASELINE (V1)

### Required
- Authentication required for all actions
- Email verification on signup
- Rate limiting on signup, login, messages
- No unauthenticated access to posts or messages
- Private data never exposed via URLs

### Explicitly Not Required in V1
- MFA
- Audit logs
- Compliance frameworks
- Advanced abuse detection

---

## 11. ACCEPTANCE CRITERIA (STOP CONDITIONS)

The system is V1-complete when:

- A buyer can post a DemandPost
- A supplier can post a SupplyLot
- A Match is created automatically
- Buyer receives an email notification
- Buyer and Supplier can exchange messages privately
- SupplyLots expire automatically
- No unauthorized access to private data is possible

If all above are true, **agents must stop**.

---

## 12. CHANGE AUTHORITY

- Agents may refactor internal code freely
- Agents may not alter:
  - Core Loop
  - Role boundaries
  - Data access rules
  - Non-Goals list

Any deviation requires **explicit human approval**.

---

**END OF SPEC**
