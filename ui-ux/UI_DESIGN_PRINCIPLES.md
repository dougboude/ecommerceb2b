
# UI Design Principles

## Purpose
This document defines the user interface design standards for the application. It ensures visual consistency, usability, accessibility, and compatibility with automated UI testing.

The design philosophy draws inspiration from:
- Airbnb marketplace UI
- Stripe product interfaces
- Linear’s minimal interaction design

Goal: a calm, modern, efficient B2B marketplace interface.

---

# Design Philosophy

The interface should feel:

- Calm
- Clear
- Efficient
- Trustworthy
- Professional

The system is a **B2B marketplace**, not a social network or entertainment platform. Clarity and usefulness are more important than visual novelty.

---

# Component System

The application uses a **componentized Django template architecture** with reusable includes/partials and shared CSS tokens.

Principles:

- Reusable components
- Predictable spacing
- Minimal custom CSS
- Small composable primitives

Core components include:

- Buttons
- Cards
- Inputs
- Modals
- Dropdowns
- Navigation elements
- Avatars
- Badges

---

# Layout Architecture

## Global Layout

All pages follow:

Top Navigation  
Page Header / Title  
Primary Content

Navigation remains **sticky** at the top.

## Content Width

Max width: **1200px**

Page padding: **24px horizontal**

---

# Navigation Design

Primary navigation (top bar):

- Discover
- Messages
- Watchlist
- Supply
- Demand
- Profile

Rules:

- Keep top-level navigation minimal and task-focused
- No nested nav structures
- No hover‑dependent navigation
- Persistent across all pages

---

# Listing Card Design

Listing cards are the core UI element.

Structure:

Image  
Title  
Location  
Quantity / Availability  

Primary action: **Message**  
Secondary action: **Save**

Rules:

- Consistent card size
- Slight hover elevation
- Scan‑friendly layout

Used in:

- Discover
- Watchlist listings
- Related listings

---

# Listing Page Layout

Two‑column layout.

Left column:
- Images
- Description
- Details

Right column:
- Listing owner info
- Message button
- Save action

The **message action must be visible without scrolling**.

---

# Conversation Interface

Two panel messaging layout.

Conversation list | Active conversation

Header must show:

- Listing title
- Listing preview
- Counterparty

Users should always know what listing the conversation relates to.

---

# Button Hierarchy

Primary buttons:
- Filled style
- Main action of the screen

Examples:

Message Supplier  
Create Listing  
Send Message

Secondary buttons:
- Outline style
- Supporting actions

Examples:

Save Listing  
Edit Listing

Tertiary actions:
- Text links
- Icon buttons

---

# Spacing System

Use consistent spacing scale:

4px  
8px  
16px  
24px  
32px  
48px

Avoid arbitrary spacing.

---

# Typography

Preferred fonts:

- Inter
- System UI

Sizes:

Page Title: 24px  
Section Title: 18px  
Body Text: 14‑16px  
Metadata: 12‑13px

Focus on readability.

---

# Color System

Minimal palette:

Primary color  
Neutral grayscale  
Success color  
Error color

Neutral tones dominate the interface.

Primary color used mainly for:

- Primary buttons
- Important highlights

---

# Interaction Design

Provide subtle feedback.

Hover:

- Card elevation
- Button shade change

Click:

- Immediate feedback
- State updates

Example:

Saved to watchlist ✓

---

# Dark Mode

Optional support.

Rules:

- Light mode default
- Maintain WCAG contrast
- Toggle available from profile menu

Theme policy:

- Current product supports two managed themes/skins.
- New UI work must implement shared component tokens across all supported skins.
- Theme additions/removals require explicit product decision; do not introduce ad-hoc per-page themes.

---

# Accessibility (WCAG)

UI must comply with **WCAG 2.1 AA**.

Requirements:

- Sufficient color contrast
- Keyboard navigation
- Visible focus states
- Accessible form labels
- Alt text for images
- Screen reader compatibility

---

# Automated UI Testing

UI must support **Playwright or similar tools**.

Important elements must include stable selectors.

Example:

data-testid="listing-card"  
data-testid="message-button"  
data-testid="save-listing"

Avoid relying on CSS classes or DOM structure for tests.

---

# Empty State Design

Every empty state must provide a clear action.

Examples:

No listings found → Adjust search filters  
No watchlist items → Browse listings  
No conversations yet → Explore listings

---

# Performance Considerations

Prioritize fast UI.

Guidelines:

- Avoid heavy frameworks when unnecessary
- Prefer lightweight interactions
- Ensure fast page rendering

---

# Consistency Rules

All UI must follow:

- Consistent spacing
- Predictable layouts
- Reusable components
- Minimal visual clutter

Consistency is more important than novelty.

---

# Summary

The interface should feel:

Simple  
Modern  
Calm  
Fast  
Predictable

The goal is an interface that feels effortless for users and easy for developers and AI agents to extend.
