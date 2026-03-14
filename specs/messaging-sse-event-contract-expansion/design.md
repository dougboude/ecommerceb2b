# Messaging SSE Event Contract Expansion — Design Document

## Overview

This layer formalizes an expanded SSE payload for `new_message` so the client can create missing rows and listing groups.

## Design Goals

1. Add missing group/row identifiers.
2. Preserve compatibility with current consumer logic.
3. Keep payload compact but sufficient.

## Proposed Event Fields (target)

- `thread_id`
- `listing_id`
- `listing_type`
- `listing_title`
- `counterparty_name`
- `sender_name`
- `message_preview`
- `message_created_at`
- `unread_count`
- `thread_unread_count`

## Contract Notes

- `message_preview` should be precomputed to match UI truncation/prefix policy where practical.
- Timestamp format should remain sortable and parseable (ISO8601).
- Listing fields provide group-key + group-label data.
- `message_preview` prefixing is viewer-relative and must be computed per recipient payload:
  - Sender-view payload: `You: {body_preview}`
  - Recipient-view payload: `{sender_display_name}: {body_preview}`
- Since streams are per-user, preview prefix can be computed at publish time per recipient alongside `counterparty_name`.
- The required `publish_new_message()` publish-path update for recipient-relative counterparty resolution must also handle recipient-relative preview prefix construction.

## Recipient-Relative Counterparty Constraint

- `counterparty_name` is viewer-relative and must be resolved per recipient stream user.
- Because SSE streams are per-user (`/stream/{user_id}`), publish logic must compute counterparty with `thread.counterparty_for(user)` for each recipient independently.
- Publishing must emit recipient-specific payload instances rather than assuming a single counterparty value for all consumers.
- Implementation constraint: update `publish_new_message()` in `marketplace/sse_client.py` accordingly. This is a publish-path behavior constraint, not a schema change.

## Risks and Mitigations

- Risk: client/server contract drift.
  - Mitigation: document field contract in code comments and tests.
