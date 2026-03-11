# UX Architecture

## Purpose

This document defines the high-level UX architecture of the application. It exists to guide future UI work, ensure consistency across features, and provide a clear product interaction model that future specifications and implementations must follow.

The system exists to accomplish a single goal:

**Connect supply-side and demand-side businesses and enable easy, intuitive communication between them.**

Every interface decision should reinforce this goal.

---

# Guiding Principles

## 1. The Product Does One Thing Well

The application exists to:

**Connect supply-side and demand-side businesses and facilitate communication between them.**

All features must support one of two core actions:

- Discover listings
- Communicate about listings

---

## 2. Minimize Conceptual Complexity

Users should only need to understand three core concepts:

- Listings
- Conversations
- Profiles

All other features are secondary or derived from these.

---

## 3. Minimize Clicks

Primary actions should require **no more than two clicks** from the main interface.

Examples:

Discover → Message listing owner  
Listing → Message counterparty  
Discover → Save listing

---

## 4. Preserve Context

Conversations must always retain context.

A conversation must clearly show:

- the listing it relates to
- the counterparty
- listing status

Users should never wonder what a conversation refers to.

---

## 5. Every Page Leads Somewhere

No screen should be a dead end.

Every page must contain a **primary next action**.

---

# Core User Journeys

The system supports four primary user journeys.

---

## Journey 1: Source Supply (Demand-side user)

Goal: Find available goods.

Flow:

Discover  
→ Search or browse listings  
→ View listing  
→ Message listing owner  
→ Conversation thread

Primary action: **Message listing owner**

---

## Journey 2: Offer Supply (Supply-side user)

Goal: Offer goods for sale.

Flow:

Create listing  
→ Publish listing  
→ Listing appears in Discover  
→ Receive messages  
→ Conversation thread

Primary action: **Create listing**

---

## Journey 3: Save and Revisit

Goal: Track interesting listings.

Flow:

Discover  
→ Save listing  
→ Watchlist page  
→ Revisit listing later  
→ Message listing owner

Primary action: **Save listing**

---

## Journey 4: Manage Listings

Goal: Manage existing supply or demand posts.

Flow:

Supply or Demand Listings  
→ Edit listing  
→ Archive listing

Primary action: **Manage listings**

---

# Target Navigation Model

Navigation should be intentionally simple.

Terminology alignment note:

- `Watchlist` is the canonical product term in current implementation (not `Saved`).
- `Supply` and `Demand` listings remain separate top-level destinations in the current product.
- Where older drafts used `Saved` / `My Listings`, this architecture maps them to `Watchlist` and `Supply` + `Demand`.

Primary navigation:

- Discover
- Messages
- Watchlist
- Supply
- Demand
- Profile

---

## Discover

Purpose:

Find relevant listings.

Contains:

- search
- filters
- listing results

Primary action:

Open listing

---

## Messages

Purpose:

Manage conversations.

Contains:

- conversation list
- conversation threads

Primary action:

Continue conversation

---

## Watchlist

Purpose:

Maintain a shortlist of interesting listings.

Primary action:

Return to listing

---

## Supply / Demand Listings

Purpose:

Manage listings posted by the user.

Primary actions:

- Create listing
- Edit listing
- Archive listing

---

## Profile

Purpose:

Represent user identity and credibility.

Contains:

- profile information
- avatar
- organization
- location

---

# Page Purpose Contracts

Each page must have a single clear purpose.

---

## Discover Page

Purpose:

Find relevant listings.

Primary action:

Open listing.

Secondary actions:

- Save listing
- Refine search

---

## Listing Page

Purpose:

Evaluate a potential opportunity.

Primary action:

Message the listing owner.

Secondary actions:

- Save listing
- View listing owner profile

---

## Conversation Page

Purpose:

Communicate with another user about a listing.

Primary action:

Send message.

Secondary actions:

- View listing
- View user profile

---

## Supply / Demand Listings Page

Purpose:

Manage listings created by the user.

Primary actions:

- Create listing
- Edit listing
- Archive listing

---

# UX Simplification Decisions

## Replace "Wanted / Available" Language

Replace UI concepts:

Wanted  
Available

With:

Listing type:

Supply  
Demand

---

## Unified Discover Experience

All discovery occurs within a single Discover interface.

Users select search direction:

Find Supply  
Find Demand

---

## Messaging Origin

Message threads must originate from a listing.

Entry point:

Listing → Message

This preserves context.

---

## Composite Listing Page

The listing page should combine key information in one place:

- listing information
- listing owner profile snippet
- primary message action
- save action

This reduces navigation hops.

---

## Conversation Context

Conversation headers must display:

- listing title
- listing preview
- counterparty

Users must always know what the conversation concerns.

---

# Empty State Standards

All empty pages must provide a clear next action.

Examples:

No listings yet  
→ Create your first listing

No watchlist items  
→ Start exploring listings

No conversations yet  
→ Browse listings to start a conversation

---

# Product Interaction Loop

The core system interaction loop is:

Discover  
→ Listing  
→ Conversation

Everything else exists to support this loop.

---

# UX Metrics

The system should optimize for:

Primary metric:

Time from discovery → conversation

Target:

Less than three clicks.

Secondary metrics:

- conversation rate per listing view
- listing save rate
- listing response time
