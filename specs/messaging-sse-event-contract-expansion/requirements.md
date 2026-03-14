# Requirements Document

## Introduction

Define the expanded SSE event contract required to support dynamic workspace updates, including absent-row and absent-group creation paths.

## Dependencies

- `messaging_feature_guide.md`
- `messaging-conversation-list-ia`
- `messaging-thread-pane-redesign`

## Scope Boundaries

### In Scope
- `new_message` payload contract expansion.
- Event schema versioning/compatibility expectations.
- Required identifiers/metadata for dynamic row/group creation.

### Out of Scope
- Full client orchestration behavior implementation.
- Grouping UI implementation.

---

## Requirements

### Requirement 1: Expanded Message Event Payload

**User Story:** As a client implementer, I want complete event data so I can update or construct workspace state without reloading.

#### Acceptance Criteria (EARS)

1. WHEN publishing `new_message`, THE System SHALL include identifiers and metadata necessary for row creation and group assignment.
2. THE payload SHALL include at minimum:
   - `thread_id`
   - `listing_id`
   - `listing_title`
   - `sender_name`
   - `message_preview`
   - `timestamp`
   - unread counters

---

### Requirement 2: Deterministic Contract Semantics

**User Story:** As a client implementer, I want deterministic event semantics to avoid ambiguous rendering behavior.

#### Acceptance Criteria (EARS)

1. WHEN event payload fields are emitted, THE System SHALL use stable value formats suitable for client ordering and grouping.
2. WHEN preview fields are emitted, THE System SHALL align with row IA preview rules.

---

### Requirement 3: Backward-Safe Rollout

**User Story:** As a maintainer, I want to expand payloads without breaking existing consumers during migration.

#### Acceptance Criteria (EARS)

1. WHEN expanded fields are added, existing behavior for nav unread and current thread updates SHALL remain functional.
2. THE rollout SHALL avoid breaking consumers that only read the current minimal field subset.
