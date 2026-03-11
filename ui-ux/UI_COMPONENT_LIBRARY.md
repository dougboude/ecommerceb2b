# UI Component Library

## Purpose

This document defines the core reusable UI components for the application.

It exists to ensure:

- consistent user experience across the product
- a shared UI vocabulary for human developers and AI agents
- predictable DOM structure for Playwright and similar testing tools
- alignment with `UX_ARCHITECTURE.md` and `UI_DESIGN_PRINCIPLES.md`

This component library is designed for the current stack:

- Django templates
- vanilla JavaScript
- componentized server-rendered includes/partials with shared CSS tokens

Components should be implemented as reusable template partials, include fragments, or other lightweight server-rendered patterns. JavaScript should be used only where needed for interactivity.

---

# General Component Rules

## 1. Reuse First

If a UI element appears in more than one place, it should become a reusable component.

## 2. Stable Test Selectors

All important interactive components must include stable selectors for automation.

Examples:

- `data-testid="listing-card"`
- `data-testid="message-button"`
- `data-testid="save-listing-button"`

Do not rely on CSS classes or text labels for automated tests.

## 3. Accessibility

All components must follow WCAG 2.1 AA expectations:

- keyboard accessible
- visible focus states
- proper labels
- correct heading hierarchy
- alt text where applicable
- semantic HTML before ARIA

## 4. Server-Rendered First

Prefer server-rendered HTML with progressive enhancement via vanilla JS.

Do not require client-side rendering for basic workflows.

## 5. Clear Primary Action

Each interactive component must make the primary action obvious.

---

# Component Groups

- Global Navigation
- Discovery Components
- Listing Components
- Messaging Components
- Listings Management Components
- Profile Components
- Feedback and System Components
- Admin-Ready Utility Components

---

# Global Navigation Components

## top-nav

### Purpose
Primary navigation bar across the application.

### Appears In
All authenticated user-facing pages.

### Structure
- logo / product name
- primary nav items
- user/profile menu

### Primary Actions
- navigate to Discover
- navigate to Messages
- navigate to Watchlist
- navigate to Supply listings
- navigate to Demand listings
- navigate to Profile

### Required Selectors
- `data-testid="top-nav"`
- `data-testid="nav-discover"`
- `data-testid="nav-messages"`
- `data-testid="nav-watchlist"`
- `data-testid="nav-supply-listings"`
- `data-testid="nav-demand-listings"`
- `data-testid="nav-profile"`

### Accessibility
- use `<nav>`
- current page item must expose active state
- all items keyboard reachable

---

## nav-item

### Purpose
Single navigation link inside the top nav.

### States
- default
- hover
- active
- disabled (rare)

### Required Selectors
- `data-testid="nav-item"`

---

## user-menu

### Purpose
Compact access point for profile and session actions.

### Appears In
Top navigation.

### Contents
- profile link
- settings / preferences link
- dark mode toggle (if implemented)
- logout

### Required Selectors
- `data-testid="user-menu"`
- `data-testid="logout-button"`

---

# Discovery Components

## discover-search-bar

### Purpose
Primary search input for finding listings.

### Appears In
Discover page.

### Structure
- search input
- submit button
- optional clear button

### Required Selectors
- `data-testid="discover-search-bar"`
- `data-testid="discover-search-input"`
- `data-testid="discover-search-submit"`
- `data-testid="discover-search-clear"`

### Accessibility
- labeled input
- Enter key submits
- clear action keyboard accessible

---

## search-direction-toggle

### Purpose
Allows user to choose discovery direction.

### Appears In
Discover page.

### Options
- Find Supply
- Find Demand

### Required Selectors
- `data-testid="search-direction-toggle"`
- `data-testid="search-direction-supply"`
- `data-testid="search-direction-demand"`

### Accessibility
- should behave like radio group or segmented control
- clear active state required

---

## filter-bar

### Purpose
Holds filtering and sorting controls for Discover and listings views.

### Appears In
Discover page, optionally Supply/Demand listing management pages.

### Typical Controls
- category
- sort order
- status (where relevant)

### Required Selectors
- `data-testid="filter-bar"`
- `data-testid="sort-control"`
- `data-testid="category-filter"`

---

## listing-grid

### Purpose
Reusable grid wrapper for listing cards.

### Appears In
- Discover results
- Watchlist page
- Related listings
- Supply/Demand listings (if card-based)

### Required Selectors
- `data-testid="listing-grid"`

---

## listing-card

### Purpose
Primary preview component for a listing.

### Appears In
- Discover
- Watchlist
- Related listings
- Supply/Demand listings (optional variant)

### Structure
- listing media slot (future-ready; currently may render placeholder/text-only)
- title
- listing type badge
- location
- quantity / unit
- status (when relevant)
- primary action
- secondary action

### Primary Action
Open listing or message owner, depending on context.

### Secondary Action
Save / unsave listing.

### Required Selectors
- `data-testid="listing-card"`
- `data-testid="listing-card-title"`
- `data-testid="listing-card-type"`
- `data-testid="listing-card-location"`
- `data-testid="listing-card-primary-action"`
- `data-testid="listing-card-save-action"`

### Accessibility
- card must be keyboard reachable if clickable
- image requires alt text
- actions must not rely on hover only

### Notes
This is the most important component in the product and should receive extra attention.

---

## empty-results-state

### Purpose
Displayed when discovery returns no results.

### Appears In
Discover page.

### Structure
- short explanation
- suggested next action
- optional “Clear filters” button

### Required Selectors
- `data-testid="empty-results-state"`

---

# Listing Components

## listing-page-layout

### Purpose
Structural wrapper for listing detail pages.

### Layout
Two-column layout.

Left column:
- listing media
- title
- description
- details

Right column:
- owner panel
- primary CTA
- save action
- listing meta

### Required Selectors
- `data-testid="listing-page-layout"`

---

## listing-header

### Purpose
Top section of a listing detail page.

### Contents
- title
- listing type
- status
- location

### Required Selectors
- `data-testid="listing-header"`

---

## listing-details

### Purpose
Displays structured details for the listing.

### Contents
- quantity
- unit
- category
- frequency (for demand)
- shipping info (for supply)
- pricing info if shown

### Required Selectors
- `data-testid="listing-details"`

---

## listing-gallery

### Purpose
Displays listing image area.

### Current State
Future-ready component slot only. Current product does not support per-listing image uploads.

### Future Use
Should be reusable when listing images are added.

### Required Selectors
- `data-testid="listing-gallery"`

---

## listing-owner-panel

### Purpose
Compact trust and identity panel for the listing owner/counterparty.

### Contents
- avatar
- display name
- organization name (if present)
- location
- member since

### Primary Action
View profile.

### Required Selectors
- `data-testid="listing-owner-panel"`
- `data-testid="listing-owner-avatar"`
- `data-testid="listing-owner-name"`
- `data-testid="listing-owner-profile-link"`

---

## message-listing-button

### Purpose
Primary call to action on a listing detail page.

### Appears In
Listing detail page, listing card variants where appropriate.

### Required Selectors
- `data-testid="message-listing-button"`

### Accessibility
- button text must clearly identify action
- must be visible without hover

---

## save-listing-button

### Purpose
Save or unsave a listing.

### States
- saved
- unsaved

### Required Selectors
- `data-testid="save-listing-button"`

---

## listing-status-badge

### Purpose
Displays listing lifecycle state.

### Supported Values
- active
- paused
- expired
- fulfilled
- withdrawn
- deleted (admin/internal only if shown)

### Required Selectors
- `data-testid="listing-status-badge"`

---

# Messaging Components

## conversation-layout

### Purpose
Overall layout for the messaging area.

### Structure
- thread list panel
- active thread panel

### Required Selectors
- `data-testid="conversation-layout"`

---

## conversation-list

### Purpose
Shows all threads available to the user.

### Structure
- thread preview rows
- unread indicators
- active thread highlight

### Required Selectors
- `data-testid="conversation-list"`
- `data-testid="conversation-list-item"`

---

## conversation-thread-header

### Purpose
Preserves context for the active conversation.

### Contents
- counterparty name
- listing title
- listing preview or thumbnail
- link back to listing

### Required Selectors
- `data-testid="conversation-thread-header"`
- `data-testid="conversation-listing-link"`

---

## message-thread

### Purpose
Container for message history.

### Required Selectors
- `data-testid="message-thread"`

---

## message-bubble

### Purpose
Displays a single message in a thread.

### Contents
- sender avatar
- sender name
- timestamp
- message text

### Required Selectors
- `data-testid="message-bubble"`
- `data-testid="message-sender"`
- `data-testid="message-timestamp"`

---

## message-input

### Purpose
Compose and send a new message.

### Structure
- text input / textarea
- send button

### Required Selectors
- `data-testid="message-input"`
- `data-testid="message-send-button"`

### Accessibility
- textarea labeled
- send button keyboard accessible
- Enter/Shift+Enter behavior must be documented if customized

---

## unread-badge

### Purpose
Indicates unread messages or notifications.

### Appears In
- nav
- conversation list

### Required Selectors
- `data-testid="unread-badge"`

---

# Listings Management Components

## my-listings-layout

### Purpose
Wrapper for a user’s supply/demand listing management area.

### Contents
- page header
- create listing CTA
- listing collection

### Required Selectors
- `data-testid="my-listings-layout"`
- `data-testid="create-listing-button"`

---

## listing-management-card

### Purpose
Management-focused variant of the listing card.

### Contents
- title
- status
- message/conversation count if applicable
- edit action
- archive action
- duplicate action (future-ready slot; not currently implemented)

### Required Selectors
- `data-testid="listing-management-card"`
- `data-testid="listing-edit-button"`
- `data-testid="listing-archive-button"`
- `data-testid="listing-duplicate-button"`

---

## listing-form

### Purpose
Shared form shell for create/edit listing workflows.

### Structure
- title/item field
- description
- category
- type-specific fields
- submit controls

### Required Selectors
- `data-testid="listing-form"`
- `data-testid="listing-form-submit"`

### Accessibility
- every field labeled
- validation errors associated with fields
- focus management on error

---

# Profile Components

## profile-header

### Purpose
Primary header for user profile page.

### Contents
- avatar
- display name
- organization
- location
- member since

### Required Selectors
- `data-testid="profile-header"`

---

## avatar

### Purpose
Displays a user profile image or fallback avatar.

### Appears In
- profile page
- listing-owner panel
- message bubble
- listing owner block

### States
- uploaded image
- default fallback

### Required Selectors
- `data-testid="avatar"`

### Accessibility
- image alt text required where meaningful
- fallback must not render broken image UI

---

## avatar-upload-control

### Purpose
Allows user to upload and change profile image.

### Contents
- upload button
- crop modal trigger
- confirm/cancel controls

### Required Selectors
- `data-testid="avatar-upload-control"`
- `data-testid="avatar-upload-input"`
- `data-testid="avatar-crop-confirm"`
- `data-testid="avatar-crop-cancel"`

---

## profile-summary

### Purpose
Displays read-only identity summary.

### Required Selectors
- `data-testid="profile-summary"`

---

# Feedback and System Components

## toast

### Purpose
Transient success or error feedback.

### Examples
- listing saved
- profile updated
- message sent

### Required Selectors
- `data-testid="toast"`

---

## inline-form-error

### Purpose
Displays field-level validation errors.

### Required Selectors
- `data-testid="inline-form-error"`

---

## confirmation-dialog

### Purpose
Confirms destructive or significant actions.

### Appears In
- delete listing
- archive listing
- admin destructive actions later

### Required Selectors
- `data-testid="confirmation-dialog"`
- `data-testid="confirm-action-button"`
- `data-testid="cancel-action-button"`

---

## modal

### Purpose
Reusable modal wrapper.

### Uses
- avatar crop
- image lightbox
- confirmation flows

### Required Selectors
- `data-testid="modal"`

### Accessibility
- focus trap
- ESC to close where appropriate
- return focus to invoking element

---

## empty-state

### Purpose
Reusable empty-state pattern.

### Contents
- headline
- short explanation
- clear next action

### Required Selectors
- `data-testid="empty-state"`

---

## status-badge

### Purpose
Generic badge component for statuses.

### Required Selectors
- `data-testid="status-badge"`

---

# Admin-Ready Utility Components

These may not all be implemented immediately in the user-facing product but should be designed consistently for later operator/admin surfaces.

## search-result-row

### Purpose
Reusable row for grouped search results.

### Required Selectors
- `data-testid="search-result-row"`

---

## audit-timeline

### Purpose
Displays chronological system/admin events.

### Required Selectors
- `data-testid="audit-timeline"`

---

## moderation-note

### Purpose
Displays internal moderation note content.

### Required Selectors
- `data-testid="moderation-note"`

---

# Component Composition Rules

## 1. Listing surfaces should reuse the same primitives

The same `listing-card`, `status-badge`, `avatar`, and `message-listing-button` should be reused across contexts.

## 2. Conversation context must always be visible

The `conversation-thread-header` is mandatory in thread views.

## 3. Empty states must always include a CTA

No page should end in a dead end.

## 4. Test selectors are part of the component contract

When a component is implemented, the `data-testid` attributes are part of the accepted design.

## 5. Avoid one-off variants unless necessary

If a new component is needed, prefer extending an existing one before introducing a new pattern.

---

# Implementation Notes for Django + Vanilla JS

- Components should be implemented as Django template partials/includes where practical.
- Use semantic HTML first.
- Use vanilla JS only for behavior that requires client-side interaction:
  - modals
  - dropdowns
  - avatar crop flow
  - optimistic save state where desired
- Avoid deeply coupling UI behavior to DOM shape.
- Keep selectors stable for Playwright.

---

# Scope and Terminology Alignment Notes

- Canonical current product terms are `Watchlist`, `Supply`, and `Demand`.
- Where earlier drafts used `Saved` or `My Listings`, interpret those as `Watchlist` and supply/demand listing management surfaces.
- `listing-gallery` and `listing-duplicate-button` are intentionally marked as future-ready slots to prevent accidental scope expansion in current UI implementation.

---

# Summary

This component library defines the shared UI vocabulary for the product.

It should help ensure that:

- the UI remains consistent
- future features compose from known parts
- Playwright automation remains stable
- AI agents build with reuse instead of invention

The most important components in the product are:

- `listing-card`
- `listing-owner-panel`
- `conversation-thread-header`
- `message-input`
- `top-nav`
