# Messaging Conversation List IA — Design Document

## Overview

This layer redesigns conversation rows to prioritize communication context over listing metadata density.

## Design Goals

1. Improve scan speed for users with many concurrent threads.
2. Preserve compact listing context without overwhelming row content.
3. Standardize preview and recency semantics.

## Row Composition

- Avatar / counterparty identity
- Primary line: counterparty name + recency marker
- Secondary line: listing title (compact)
- Tertiary line: sender-prefixed last-message preview
- Unread indicator/badge treatment

## Ordering Contract

- Deterministic sort by last message timestamp descending.
- Stable tie-break behavior if equal timestamps.

## Last-Message Preview Data Strategy

Chosen approach: **query annotation**, no schema change in this layer.

- Build row preview inputs from query-time annotations/subqueries for each thread (last message body, last message sender, and last message timestamp).
- This aligns with current Django server-rendered patterns and avoids migration overhead in this refactor phase.
- Denormalized `MessageThread` summary fields are intentionally deferred; they can be introduced later if measured scale/performance requires it.

Render-time prefix rule:
- Sender-prefix formatting (`You:` vs counterparty name) is computed at render time using the viewing user identity.
- Sender-prefixed preview text is not stored as a persisted string.

## Risks and Mitigations

- Risk: row noise from too many metadata fields.
  - Mitigation: strict hierarchy and truncation rules.
