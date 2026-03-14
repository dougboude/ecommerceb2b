# Messaging Listing-Grouped Conversations — Design Document

## Overview

This layer introduces listing-grouped conversation presentation and interaction behavior, primarily for seller multi-buyer workflows.

## Design Goals

1. Keep grouping intuitive and lightweight.
2. Preserve fast thread switching.
3. Keep grouped and flat modes behaviorally compatible.

## Group Structure

- Group key: `listing_id`
- Group header:
  - listing title
  - optional compact activity signal
- Group body:
  - conversation rows following shared IA contract

## Ordering Contract

- Group order: latest activity among member rows.
- Row order within group: latest activity descending.

## Grouped Mode Toggle and Default

Default mode:
- Flat conversation list is the default for new users and for requests without explicit mode selection.

Activation mechanism:
- Initial grouped/flat switching uses query parameter state:
  - `?view=grouped` -> grouped mode
  - `?view=flat` (or omitted) -> flat mode

Persistence strategy:
- Initial implementation is stateless (query-param driven), with no `User` model preference field.
- This leaves room for future upgrade to persisted preference without blocking current rollout.

Interaction model:
- Initial mode switching is request/navigation based (server-rendered mode switch), not a purely client-side toggle.

## Risks and Mitigations

- Risk: grouping adds cognitive overhead for low-volume users.
  - Mitigation: preserve flat-list fallback mode with identical row contract.
