# Messaging Workspace Re-Architecture — Feature Plan

## Objective

Refactor messaging into a conversation-first negotiation workspace with hybrid layout, listing-aware thread context, real-time coherence, and seller-friendly listing grouping.

## Architectural Constraints

- Keep Django server-rendered templates as primary rendering path.
- Keep SSE as the real-time transport.
- Preserve listing-centric thread uniqueness (`listing + initiator`).
- Preserve existing permission boundaries.

## Planned Feature Layers

### Layer 1: Workspace Shell + Responsive Navigation

Outcomes:
- Desktop split-pane shell (list + thread).
- Mobile list -> thread flow with consistent back path.
- Workspace-level navigation state model.

### Layer 2: Conversation List Information Architecture

Outcomes:
- Conversation rows optimized for communication context.
- Sender-prefixed preview text.
- Consistent unread and recency signals.

### Layer 3: Thread Pane Redesign

Outcomes:
- Stable counterparty + listing summary context header.
- Chronological stream behavior contract.
- Always-available composer behavior.

### Layer 4: SSE Event Contract Expansion

Outcomes:
- Payload includes stable identifiers and metadata needed for row/group creation.
- Backward-safe rollout contract.

### Layer 5: Real-Time Workspace Orchestration

Outcomes:
- Update existing rows.
- Create missing rows.
- Create missing listing groups.
- Reorder by activity without full page reload.

### Layer 6: Listing-Grouped Conversation Management

Outcomes:
- Grouped conversation list by listing for multi-buyer seller workflows.
- Group-level open/close and interaction patterns.

## Validation Strategy

- Unit and integration tests per layer.
- End-to-end path coverage from all entry points: Discover, Suggestions, Watchlist, Listing Detail, Messages.
- Real-time behavior tests for absent-row and absent-group creation paths.

## Execution Policy

- Specs/docs can be authored and merged on `main`.
- Any implementation work beyond markdown/spec files must occur on a dedicated feature branch.
