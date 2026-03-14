# Requirements Document

## Introduction

Define conversation list information architecture focused on communication context and scan efficiency.

## Dependencies

- `messaging_feature_guide.md`
- `messaging-workspace-layout-and-navigation`

## Scope Boundaries

### In Scope
- Conversation row structure/content.
- Preview format and unread/recency cues.
- Sorting behavior contract for list rendering.

### Out of Scope
- Grouped-by-listing behavior.
- SSE event schema changes.

---

## Requirements

### Requirement 1: Row Information Contract

**User Story:** As a user, I want each conversation row to show the right context for fast scanning.

#### Acceptance Criteria (EARS)

1. WHEN conversation rows are rendered, THE System SHALL show counterparty identity, listing title, message preview, timestamp, and unread indicator.
2. WHEN listing title is shown, THE System SHALL render it in compact form suitable for row scanning.

---

### Requirement 2: Sender-Prefixed Preview

**User Story:** As a user, I want to know who sent the latest message without opening the thread.

#### Acceptance Criteria (EARS)

1. WHEN preview text is displayed, THE System SHALL prefix preview with sender context (`You:` or counterparty name).
2. WHEN preview exceeds display budget, THE System SHALL truncate predictably while preserving prefix clarity.

---

### Requirement 3: Activity Ordering and Unread Cues

**User Story:** As a user managing negotiations, I want most active and unread items to be obvious.

#### Acceptance Criteria (EARS)

1. WHEN conversation list is rendered, THE System SHALL order rows by latest activity descending.
2. WHEN a conversation is unread, THE row SHALL present explicit unread visual treatment.
