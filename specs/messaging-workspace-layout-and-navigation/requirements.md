# Requirements Document

## Introduction

Define the messaging workspace shell and responsive navigation contract for a hybrid list/thread experience.

## Dependencies

- `messaging_feature_guide.md`
- `messaging-workspace-conversation-context`
- `navigation-ia-unification`

## Scope Boundaries

### In Scope
- Split-pane layout behavior on large viewports.
- List/thread navigation behavior on medium/small viewports.
- Stable messages workspace entry/return paths.

### Out of Scope
- Conversation row content redesign.
- SSE payload/schema changes.

---

## Requirements

### Requirement 1: Hybrid Workspace Layout

**User Story:** As a user, I want list and thread visible together on desktop so I can switch conversations quickly.

#### Acceptance Criteria (EARS)

1. WHEN viewport is large, THE System SHALL render a two-pane messaging workspace.
2. WHEN no thread is selected on large viewport, THE thread pane SHALL show a neutral empty/selection state.

---

### Requirement 2: Responsive Navigation Contract

**User Story:** As a mobile user, I want predictable list-to-thread navigation so messaging feels natural on small screens.

#### Acceptance Criteria (EARS)

1. WHEN viewport is small, THE System SHALL present list-first navigation into a single-thread view.
2. WHEN viewing a thread on small viewport, THE System SHALL provide an explicit path back to conversation list.

---

### Requirement 3: Entry Path Consistency

**User Story:** As a user entering from different surfaces, I want to land in the same workspace contract.

#### Acceptance Criteria (EARS)

1. WHEN users enter messaging from Discover/Suggestions/Watchlist/Listing detail, THE System SHALL resolve to the workspace with target thread selected.
2. WHEN users click Messages in top navigation, THE System SHALL open workspace root in list-oriented state.
