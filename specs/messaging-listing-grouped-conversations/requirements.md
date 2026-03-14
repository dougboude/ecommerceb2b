# Requirements Document

## Introduction

Define listing-grouped conversation management behavior for high-volume seller negotiation workflows.

## Dependencies

- `messaging_feature_guide.md`
- `messaging-conversation-list-ia`
- `messaging-realtime-workspace-orchestration`

## Scope Boundaries

### In Scope
- Group-by-listing conversation structure.
- Group labels and row membership rules.
- Group-level interaction contract.

### Out of Scope
- New message protocol.
- Non-messaging listing workflow redesign.

---

## Requirements

### Requirement 1: Listing Grouping Model

**User Story:** As a seller, I want conversations grouped by listing so I can manage multiple buyers efficiently.

#### Acceptance Criteria (EARS)

1. WHEN grouped mode is active, THE System SHALL organize conversation rows under listing headers.
2. WHEN a listing has multiple conversation threads, THE System SHALL display all threads in that listing group.

---

### Requirement 2: Group Interaction Behavior

**User Story:** As a user, I want grouped lists to remain easy to scan and navigate.

#### Acceptance Criteria (EARS)

1. WHEN groups are rendered, THE System SHALL keep group labels compact and identifiable.
2. WHEN users interact with a row inside a group, THE System SHALL open the selected thread without losing group/list context.

---

### Requirement 3: Real-Time Group Coherence

**User Story:** As a user, I want grouped conversations to stay accurate during live updates.

#### Acceptance Criteria (EARS)

1. WHEN real-time events occur, THE System SHALL update row membership/order in the appropriate listing group.
2. WHEN group activity changes ordering, THE System SHALL reorder groups deterministically by latest activity.

---

### Requirement 4: Fallback Behavior

**User Story:** As a maintainer, I want clear behavior when grouping is unavailable or disabled.

#### Acceptance Criteria (EARS)

1. WHEN grouped mode is not active, THE System SHALL render a flat conversation list using the same row IA contract.
2. Grouping features SHALL not regress baseline thread access and unread behavior.

---

### Requirement 5: Grouped Mode Activation and Default

**User Story:** As a user, I want a clear and predictable way to switch between grouped and flat conversation views.

#### Acceptance Criteria (EARS)

1. WHEN a user opens Messages without explicit view selection, THE System SHALL default to flat list mode.
2. WHEN a user selects grouped mode, THE System SHALL activate grouped rendering via query parameter `?view=grouped`.
3. WHEN a user selects flat mode, THE System SHALL activate flat rendering via query parameter `?view=flat` or no view parameter.
4. Mode switching SHALL be stateless in the initial implementation and SHALL NOT require a persisted `User` preference field.
5. Toggling between grouped and flat mode SHALL occur via page navigation/request cycle in the initial implementation.
