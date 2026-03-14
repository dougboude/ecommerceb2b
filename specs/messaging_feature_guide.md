# Messaging UX Re‑Architecture Feature Guide

**Project Context:** B2B Marketplace Platform (Django + Server Rendered
Templates + SSE Real‑time Layer)\
**Purpose:** Provide architecture guidance for AI planning agents to
generate Epic, Requirements, Design, and Task specifications.

------------------------------------------------------------------------

# 1. Feature Objective

Messaging exists to **establish and maintain buyer--seller relationships
around marketplace listings**.

The system must support:

• Real‑time negotiation between two parties\
• Persistent conversation threads tied to a listing\
• Sellers managing multiple buyers simultaneously\
• Buyers negotiating across multiple listings\
• Fast, intuitive chat-like interaction

Messaging is **not just an inbox feature**. It is the **communication
layer of the marketplace**.

Listings initiate conversations.\
Conversations advance deals.

------------------------------------------------------------------------

# 2. Core UX Philosophy

### Conversation‑First Design

Once a conversation starts, the conversation becomes the primary object
of interaction.

### Listing Context Persistence

Every conversation is tied to a listing and must always display compact
listing context.

### Chat‑Like Interaction

Threads must behave like modern chat applications:

• real‑time message arrival\
• immediate composer availability\
• chronological message stream

### Negotiation Workspace

Messaging should feel like a workspace where users manage multiple
ongoing negotiations.

------------------------------------------------------------------------

# 3. Primary User Journeys

## Journey A -- Initiate Conversation

1.  User discovers listing
2.  User selects **Message**
3.  System creates or reopens thread
4.  User enters conversation workspace
5.  User sends first message

Goal: remove friction between interest and conversation.

------------------------------------------------------------------------

## Journey B -- Resume Conversation

1.  User opens Messages workspace
2.  User scans conversation list
3.  User selects thread
4.  User continues conversation

Goal: rapid re‑entry into negotiations.

------------------------------------------------------------------------

## Journey C -- Manage Multiple Negotiations

1.  User has many threads
2.  Conversation list shows active threads ordered by activity
3.  User switches between threads easily

Goal: support multi‑listing negotiation workflows.

------------------------------------------------------------------------

## Journey D -- Seller Manages Buyers

1.  Seller has listing
2.  Multiple buyers start conversations
3.  Seller reviews and responds to each thread

Goal: allow sellers to handle multiple inquiries efficiently.

------------------------------------------------------------------------

# 4. Messaging Workspace Architecture

## Hybrid Layout

Desktop Layout:

    -------------------------------------------
    | Conversation List | Conversation Thread |
    -------------------------------------------

Mobile Layout:

    Conversation List
    ↓
    Thread View

This approach mirrors modern communication tools such as Slack.

------------------------------------------------------------------------

# 5. Conversation List Design

Conversation rows must prioritize **message context**, not listing
metadata.

### Row Layout

    Avatar   Counterparty Name        Timestamp
             Listing Title
             Last message preview

### Elements

• Counterparty name\
• Listing title (compact)\
• Last message preview\
• Timestamp\
• Unread indicator

### Preview Format

Use sender prefix for clarity:

    You: I can deliver next week
    Sarah: Is bulk pricing possible?

------------------------------------------------------------------------

# 6. Thread View Design

Thread structure:

    Counterparty
    Listing summary card

    ------------------------
    message stream
    ------------------------

    message composer

Responsibilities:

• show counterparty identity • show listing context • display
chronological messages • keep message composer visible

------------------------------------------------------------------------

# 7. Conversation Grouping by Listing

For sellers with many buyers:

    Corn Listing
       Buyer A
       Buyer B
       Buyer C

    Soy Listing
       Buyer D
       Buyer E

Benefits:

• easier negotiation management • better conversation organization •
stronger listing context

------------------------------------------------------------------------

# 8. Messaging Entry Points

Messaging may originate from:

• Discover results\
• Suggestions\
• Watchlist\
• Listing detail\
• Messages workspace

All entry points must resolve to **open the conversation thread**.

Logic:

    If thread exists:
        open thread
    Else:
        create thread then open

------------------------------------------------------------------------

# 9. Real‑Time Architecture

Current system uses **Server‑Sent Events (SSE)** for message updates.

SSE is sufficient to support the redesigned UX.

Required enhancements:

### Expanded Event Payload

Events must include:

• thread_id\
• listing_id\
• listing_title\
• sender_name\
• message_preview\
• timestamp\
• unread counts

### Client Responsibilities

Client must:

• update existing rows\
• create rows when absent\
• create listing groups when absent\
• reorder conversations by activity

------------------------------------------------------------------------

# 10. Navigation Structure

Top‑level navigation:

    Marketplace
      Discover
      Watchlist
      Listings
      Messages

Messages becomes a **primary workspace**.

------------------------------------------------------------------------

# 11. Key Interaction Patterns

### Thread Switching

Instant switching between conversations in split layout.

### Message Composer

Always visible at bottom of thread.

### Unread Indicators

• dot or badge\
• bold preview text

### Real‑Time Updates

• thread updates live\
• list reorder on activity

------------------------------------------------------------------------

# 12. Responsiveness Strategy

Viewport determines layout:

Large screens: • split workspace

Medium screens: • collapsible list panel

Small screens: • list → thread navigation

------------------------------------------------------------------------

# 13. UI Framework Recommendation

Avoid heavy SPA frameworks.

Recommended approach:

• Django server templates • SSE updates • Lightweight client behavior
layer

Optional enhancement:

Stimulus.js controllers for:

• workspace state • conversation switching • SSE event handling

------------------------------------------------------------------------

# 14. Anti‑Patterns to Avoid

Avoid:

• listing‑first inbox layouts • multiple competing click targets •
message previews without sender clarity • duplicate thread creation •
fragmented messaging workflows

------------------------------------------------------------------------

# 15. Implementation Responsibilities

AI planning agents should produce:

### Epic

Messaging Workspace Re‑Architecture

### Requirements

Functional messaging behaviors

### Design Documents

UI structure and component architecture

### Task Breakdown

Backend changes Frontend layout changes SSE event enhancements

------------------------------------------------------------------------

# 16. Implementation Milestones

Suggested milestone phases:

1.  Conversation workspace layout
2.  Thread UI redesign
3.  Conversation row redesign
4.  SSE payload expansion
5.  Dynamic row/group creation
6.  Responsive behavior
7.  Seller listing grouping

------------------------------------------------------------------------

# 17. Success Metrics

The redesigned system should achieve:

• faster conversation initiation\
• clearer conversation scanning\
• improved negotiation flow\
• efficient multi‑conversation management
