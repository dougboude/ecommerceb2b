# Messaging Real-Time Workspace Orchestration — Design Document

## Overview

This layer defines front-end orchestration logic that consumes expanded SSE events and mutates workspace DOM deterministically.

## Design Goals

1. No full-page reload for standard message updates.
2. Deterministic row/group create-update-reorder behavior.
3. Idempotent handling under rapid event bursts.

## Client Orchestration Responsibilities

- Locate target thread row by `thread_id`.
- If found: mutate row fields and reorder.
- If absent: fetch a server-rendered row fragment and insert.
- If grouped view and group absent: build group and insert row.

## Row Rendering Strategy

Chosen approach: **Option A (server-rendered row fragments)**.

- Add a Django endpoint for row-fragment rendering (for example, `GET /messages/row/{thread_id}/`).
- On absent-row events, SSE client fetches this endpoint and inserts returned HTML.
- Existing-row updates may still apply lightweight in-place mutations where safe, but row creation uses server-rendered HTML as canonical markup.

Rationale:
- Prevents drift between client-constructed markup and server template markup.
- Preserves Django template ownership of presentation logic.
- Removes the need for snapshot tests on client-constructed row HTML.

## Workspace Mode Signal

- Server renders workspace mode on the root workspace container via `data-view-mode` attribute.
  - Example values: `data-view-mode="grouped"` or `data-view-mode="flat"`.
- On SSE event handling, orchestration JS reads `data-view-mode` to decide whether grouped insertion/creation logic is required.
- Mode signal is request-cycle derived and static for page lifetime.
  - Grouped/flat switching is request-based (not in-page mode mutation), consistent with Layer 6.

## State and Safety

- Maintain in-memory map/set keyed by thread and listing ids to prevent duplicates.
- Handle event burst ordering by timestamp with stable fallback ordering.

## Risks and Mitigations

- Risk: additional network round-trips during absent-row creation bursts.
  - Mitigation: keep row endpoint lightweight and idempotent; use burst-deduplication guards keyed by `thread_id`.
