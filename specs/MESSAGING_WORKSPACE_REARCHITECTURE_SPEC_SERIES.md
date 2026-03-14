# Messaging Workspace Re-Architecture — Spec Series

## Source of Truth

- `specs/messaging_feature_guide.md` (architectural source of truth)

## Purpose

Define a layered, dependency-safe spec series for a major messaging UI/UX refactor so multiple agents can collaborate on spec authoring and implementation without ambiguity.

## Collaboration Rules

- Each feature folder in this series is independently executable once dependencies are complete.
- Agents should not implement code from these specs on `main`; execution work must occur on a dedicated feature branch.
- Spec and markdown authoring may be committed to `main`.
- If any requirement in a child spec conflicts with `messaging_feature_guide.md`, the guide wins.

## Layered Execution Sequence

1. `messaging-workspace-layout-and-navigation`
- Establish hybrid workspace shell and responsive navigation behavior.

2. `messaging-conversation-list-ia`
- Redesign conversation row information architecture and scan behavior.

3. `messaging-thread-pane-redesign`
- Redesign thread pane, persistent listing context, and composer contract.

4. `messaging-sse-event-contract-expansion`
- Expand and version event payload contract required for dynamic workspace updates.

5. `messaging-realtime-workspace-orchestration`
- Implement client orchestration for row/group creation, ordering, and live coherence.

6. `messaging-listing-grouped-conversations`
- Add grouped-by-listing seller workflow and workspace filtering/interaction rules.

## Series Dependencies

- Existing messaging foundation specs remain prerequisites:
  - `listing-centric-messaging-and-watchlist-decoupling`
  - `messaging-workspace-conversation-context`
  - `navigation-ia-unification`

## Deliverables Per Layer

Each layer includes:
- `requirements.md`
- `design.md`
- `tasks.md`

## Non-Goals for This Series

- Replace SSE with WebSockets.
- Convert messaging to a SPA framework architecture.
- Change ownership/participation permission boundaries.
