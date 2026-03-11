# Feature Backlog (Spec Planning Input)

This backlog translates the UX/UI architecture artifacts into spec-sized, user-visible product features for the specsmd workflow.

Source inputs reviewed:
- `ui-ux/UX_SYSTEM_MAP.md`
- `ui-ux/UX_ARCHITECTURE.md`
- `ui-ux/UI_DESIGN_PRINCIPLES.md`
- `ui-ux/UI_COMPONENT_LIBRARY.md`

## Prioritized Features

### 1) Feature: Navigation and Information Architecture Unification
**Description:** Consolidate global navigation and page-level wayfinding so users can reliably move between Discover, Messages, Watchlist, Supply listings, Demand listings, and Profile with consistent active-state feedback and clear next actions.  
**Primary Journey:** User moves from entry page to target workflow without confusion or dead ends.  
**Key Components:**
- `top-nav`
- `nav-item`
- `user-menu`
- `empty-state`
**Dependencies:**
- Authentication/session state
- Existing route map and nav context logic
- Base layout/template includes

---

### 2) Feature: Discover Search Experience (Find Supply / Find Demand)
**Description:** Deliver a cohesive Discover experience with direction toggle, search modes, filtering/sorting, actionable result cards, and predictable result persistence.  
**Primary Journey:** Discover -> Search -> Evaluate results -> Save or Message.  
**Key Components:**
- `discover-search-bar`
- `search-direction-toggle`
- `filter-bar`
- `listing-grid`
- `listing-card`
- `empty-results-state`
- `save-listing-button`
- `message-listing-button`
**Dependencies:**
- Navigation and IA Unification
- Listing data model/status model
- Search services (semantic + keyword fallback)
- Watchlist and messaging action endpoints

---

### 3) Feature: Listing Detail Conversion Surface
**Description:** Rework listing detail pages into a conversion-oriented composite surface with listing context, owner trust panel, visible primary message CTA, and contextual secondary actions.  
**Primary Journey:** Listing detail -> Message listing owner (or save) with minimal friction.  
**Key Components:**
- `listing-page-layout`
- `listing-header`
- `listing-details`
- `listing-owner-panel`
- `listing-status-badge`
- `message-listing-button`
- `save-listing-button`
- `confirmation-dialog`
**Dependencies:**
- Discover Search Experience
- Messaging workspace/thread creation rules
- Watchlist save workflow

---

### 4) Feature: Messaging Workspace and Conversation Context
**Description:** Implement a coherent messaging workspace that preserves listing context at all times and supports quick continuation of active conversations.  
**Primary Journey:** Messages -> Open conversation -> Send message -> Continue negotiation.  
**Key Components:**
- `conversation-layout`
- `conversation-list`
- `conversation-thread-header`
- `message-thread`
- `message-bubble`
- `message-input`
- `unread-badge`
**Dependencies:**
- Listing Detail Conversion Surface
- Existing thread/message/read-state models
- SSE/unread signaling behavior

---

### 5) Feature: Watchlist Follow-Up Workflow
**Description:** Strengthen Watchlist as the user’s follow-up hub with clear state management (watching/starred/archived), quick conversation entry, and consistent linkage back to listings.  
**Primary Journey:** Discover or Suggestions -> Save to Watchlist -> Revisit -> Message.  
**Key Components:**
- `listing-grid`
- `listing-card`
- `save-listing-button`
- `status-badge`
- `empty-state`
- `unread-badge`
**Dependencies:**
- Discover Search Experience
- Messaging Workspace
- Listing Detail Conversion Surface

---

### 6) Feature: Supply and Demand Listing Management Hub
**Description:** Improve listing management surfaces so users can efficiently monitor, filter, and act on their own supply/demand listings with clear status and action affordances.  
**Primary Journey:** Open Supply/Demand listings -> Inspect status -> Edit/toggle/archive/delete as needed.  
**Key Components:**
- `my-listings-layout`
- `listing-management-card`
- `listing-status-badge`
- `filter-bar`
- `confirmation-dialog`
- `empty-state`
**Dependencies:**
- Navigation and IA Unification
- Listing status lifecycle rules
- Listing authoring/editing/deletion endpoints

---

### 7) Feature: Listing Authoring and Edit Flows
**Description:** Modernize create/edit/cancel/confirm flows for supply and demand listings with consistent forms, clear validation, and predictable return paths.  
**Primary Journey:** Create or edit listing -> Submit -> Return to actionable detail/list context.  
**Key Components:**
- `listing-form`
- `inline-form-error`
- `confirmation-dialog`
- `status-badge`
**Dependencies:**
- Supply and Demand Listing Management Hub
- Existing listing model constraints/validation

---

### 8) Feature: Profile and Trust Surfaces
**Description:** Improve profile usability and trust context across listing and messaging surfaces, including avatar workflows and identity consistency.  
**Primary Journey:** Update profile/avatar -> Present clear identity in listings and conversations.  
**Key Components:**
- `profile-header`
- `profile-summary`
- `avatar`
- `avatar-upload-control`
- `modal`
**Dependencies:**
- Navigation and IA Unification
- Existing profile + avatar backend
- Listing detail and messaging surfaces

---

### 9) Feature: Account Access and Verification Journey
**Description:** Refine signup/login/verification/recovery states so users can complete onboarding and recovery flows without confusion or dead ends.  
**Primary Journey:** Sign up -> Verify email -> Login -> Reach dashboard/discover path.  
**Key Components:**
- `inline-form-error`
- `empty-state` (for no-progress/auth-state pages)
- `top-nav` (unauthenticated variant)
- `confirmation-dialog` (where applicable)
**Dependencies:**
- Existing auth and email verification flows
- Navigation and IA Unification

---

### 10) Feature: Cross-Page Feedback, Recovery, and Empty-State System
**Description:** Standardize feedback and recovery patterns (success/error toasts, confirmation modals, empty-state CTAs) so every page has a clear next action and fewer dead ends.  
**Primary Journey:** User completes/attempts an action -> receives clear feedback -> takes next step immediately.  
**Key Components:**
- `toast`
- `inline-form-error`
- `confirmation-dialog`
- `empty-state`
- `modal`
**Dependencies:**
- Navigation and IA Unification
- All major interaction features above (discover, listing, watchlist, messaging, profile, auth)

---

## Backlog Notes

- These are refactor/evolution features mapped to the current product state, not greenfield inventions.
- Future-ready component slots (for example listing media gallery, duplicate listing controls) should be tracked as explicit non-v1 scope unless separately spec’d.
- Accessibility and stable `data-testid` contracts are cross-cutting acceptance requirements for each feature spec, not stand-alone visual-only specs.
