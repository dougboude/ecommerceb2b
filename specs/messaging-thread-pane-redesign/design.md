# Messaging Thread Pane Redesign — Design Document

## Overview

This layer redesigns the active thread pane while preserving listing-linked semantics and existing permissions.

## Design Goals

1. Keep identity and listing context visible at all times.
2. Preserve chronology and readability for ongoing negotiation.
3. Keep reply interaction low-friction.

## Pane Contract

- Header region:
  - Counterparty identity
  - Compact listing summary / link context
- Stream region:
  - Chronological message rendering
  - Unambiguous sender styling
- Composer region:
  - Persistent compose input and send control
  - Enter-to-send toggle/persistence contract retained

## Dual-Rendering Contract

The thread detail view must support two response shapes:

- Full-page response:
  - Used for direct navigation, refresh, and mobile URL-based flows.
  - Returns full template shell (`base.html` layout, nav, page scaffolding).
- Fragment response:
  - Used for desktop split-pane HTMX thread switching.
  - Detect with `request.headers.get("HX-Request")`.
  - Returns thread-content partial only (no `base.html` shell, no nav).

Template reuse constraint:
- Keep a reusable thread-content include/partial as the canonical thread markup.
- Both full-page and fragment responses must render this shared partial to prevent markup drift.

## Risks and Mitigations

- Risk: cramped layout in split-pane mode.
  - Mitigation: enforce compact context card and clear section boundaries.
