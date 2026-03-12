# Requirements Document

## Introduction

This spec strengthens Watchlist as the follow-up workspace for saved opportunities, with clear state transitions and direct conversation continuity.

## Dependencies

- `discover-search-experience`
- `listing-detail-conversion-surface`
- `messaging-workspace-conversation-context`
- Existing watchlist and thread coordination behavior

## Scope Boundaries

### In Scope
- Watchlist state management clarity
- Follow-up actions from watchlist
- Watchlist-to-conversation continuity
- Archived item handling UX clarity

### Out of Scope
- New watchlist data model
- New recommendation algorithms

---

## Requirements

### Requirement 1: Watchlist as Follow-Up Hub

**User Story:** As a user, I want watchlist to clearly show what I am tracking and what needs action.

#### Acceptance Criteria (EARS)

1. WHEN users open watchlist, THE System SHALL clearly separate active tracking items from archived items.
2. WHEN item states change (star/archive/remove), THE System SHALL reflect state changes immediately.

---

### Requirement 2: Follow-Up Action Consistency

**User Story:** As a user, I want each watchlist item to expose clear next actions.

#### Acceptance Criteria (EARS)

1. WHEN watchlist item is active, THE item SHALL provide actions to prioritize, archive, remove, and message/open conversation where applicable.
2. WHEN watchlist item is archived, THE item SHALL provide clear restore behavior.

---

### Requirement 3: Conversation Continuity from Watchlist

**User Story:** As a user, I want to continue conversations directly from watchlist context.

#### Acceptance Criteria (EARS)

1. WHEN watchlist item has existing thread, THE System SHALL provide direct conversation access.
2. WHEN no thread exists and messaging is allowed, THE System SHALL provide thread initiation path.

---

### Requirement 4: Empty-State Recovery

**User Story:** As a user, I want an empty watchlist to direct me back to sourcing actions.

#### Acceptance Criteria (EARS)

1. WHEN watchlist has no active items, THE page SHALL include a clear CTA to discover listings.

---

### Requirement 5: Safety Boundary

**User Story:** As a product owner, I want watchlist UX improvements without changing ownership rules.

#### Acceptance Criteria (EARS)

1. THIS spec SHALL preserve watchlist ownership permissions.
2. THIS spec SHALL preserve existing watchlist-thread linkage semantics.
