# Requirements Document

## Introduction

This spec unifies messaging workspace behavior so users can quickly locate active conversations and always understand listing context inside threads.

## Dependencies

- `listing-detail-conversion-surface`
- Existing `MessageThread`, `Message`, and `ThreadReadState` models
- Existing inbox and thread views

## Scope Boundaries

### In Scope
- Inbox/workspace coherence
- Thread context preservation
- Read/unread state clarity
- Conversation continuation flow consistency

### Out of Scope
- New messaging protocol/service architecture
- New moderation/admin messaging scopes

---

## Requirements

### Requirement 1: Workspace Coherence

**User Story:** As a user, I want a clear messages workspace so I can resume active conversations quickly.

#### Acceptance Criteria (EARS)

1. WHEN users open Messages, THE System SHALL present conversation list in a clear recency-oriented structure.
2. WHEN unread threads exist, THE workspace SHALL indicate unread state clearly.

---

### Requirement 2: Thread Context Preservation

**User Story:** As a user, I want every thread to clearly indicate what listing and counterparty the conversation is about.

#### Acceptance Criteria (EARS)

1. WHEN thread detail is rendered, THE page SHALL show counterparty and listing context.
2. WHEN sending messages, THE context header SHALL remain visible and unchanged.

---

### Requirement 3: Conversation Continuation Flow

**User Story:** As a user, I want reliable transitions between inbox and thread.

#### Acceptance Criteria (EARS)

1. WHEN users open a thread from inbox or other entry points, THE page SHALL provide a consistent return path to messages workspace.
2. WHEN a message is sent successfully, THE thread SHALL reflect the new message and remain in coherent order.

---

### Requirement 4: Unread-State Accuracy

**User Story:** As a user, I want unread indicators to match real conversation state.

#### Acceptance Criteria (EARS)

1. WHEN users view a thread, THE System SHALL update read-state accordingly.
2. WHEN new messages arrive in other threads, THE System SHALL reflect unread indicators in workspace/nav.

---

### Requirement 5: Safety Boundary

**User Story:** As a product owner, I want messaging UX improvements without changing core privacy and permission rules.

#### Acceptance Criteria (EARS)

1. THIS spec SHALL preserve thread participation access rules.
2. THIS spec SHALL preserve listing-linked thread semantics.
