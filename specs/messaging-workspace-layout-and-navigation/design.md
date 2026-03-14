# Messaging Workspace Layout and Navigation — Design Document

## Overview

This layer introduces the structural shell for a hybrid messaging workspace and responsive navigation behavior.

## Design Goals

1. Preserve current routing while introducing workspace layout state.
2. Provide desktop split behavior and mobile stack behavior without SPA migration.
3. Keep thread selection state deterministic.

## Proposed Surface Contract

- Desktop:
  - Left: conversation list pane
  - Right: active thread pane
- Mobile:
  - List view route/state
  - Thread view route/state with back-to-list action

## Suggested Template Strategy

- Introduce/extend a workspace template that can render both panes.
- Keep thread detail fragment reusable across full-page and pane rendering.

## Thread Switching Mechanism

Chosen approach: **Option A (HTMX-driven)**.

- Conversation row selection in the left pane uses `hx-get` to request a server-rendered thread fragment.
- The response is swapped into the right pane container.
- URL state is synchronized using `hx-push-url` so refresh/back-forward remain coherent.

Rationale:
- HTMX is already loaded globally in `templates/base.html`.
- Keeps rendering logic in Django templates (server-rendered architecture alignment).
- Avoids client-side HTML duplication and avoids full-page reload on desktop split-pane switches.

## State Contract

- Selected thread id may be derived from route/query.
- Empty state behavior when no thread selected.

## Risks and Mitigations

- Risk: divergent behavior between desktop and mobile.
  - Mitigation: shared selection contract + viewport-specific rendering rules.
