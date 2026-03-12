# Requirements Document

## Introduction

This spec upgrades Discover into a cohesive, conversion-focused experience for both directions (`Find Supply`, `Find Demand`) while preserving existing semantic and keyword search behavior.

## Dependencies

- `navigation-ia-unification`
- `cross-page-feedback-recovery-empty-state-system`
- Existing listing/search/watchlist/messaging capabilities

## Scope Boundaries

### In Scope
- Direction clarity and persistence behavior
- Search controls coherence
- Results action consistency (save/unsave/message)
- Discover empty-state and short-query guidance behavior

### Out of Scope
- New ranking algorithms
- New matching engines
- New marketplace domains

---

## Requirements

### Requirement 1: Discover Direction Contract

**User Story:** As a user, I want to clearly choose whether I am finding supply or demand.

#### Acceptance Criteria (EARS)

1. WHEN Discover is loaded, THE System SHALL expose direction choices `Find Supply` and `Find Demand`.
2. WHEN direction changes, THE System SHALL apply the correct listing type target and not bleed results/state across directions.
3. WHEN returning to Discover via save/unsave workflows, THE System SHALL preserve valid search context for the active direction.

---

### Requirement 2: Search Control Clarity

**User Story:** As a user, I want search controls that are understandable and predictable.

#### Acceptance Criteria (EARS)

1. THE Discover page SHALL present query, direction, search mode, and key filters in a coherent form.
2. WHEN search is submitted, THE System SHALL provide clear results or an actionable empty state.
3. WHEN user triggers clear action, THE System SHALL reset discover state predictably.

---

### Requirement 3: Result Card Action Consistency

**User Story:** As a user, I want every result card to support immediate follow-up actions.

#### Acceptance Criteria (EARS)

1. WHEN results are shown, each result SHALL support opening listing detail.
2. WHEN results are shown, each result SHALL support watchlist save/unsave state action.
3. WHEN results are shown, each result SHALL support starting a conversation via message action.

---

### Requirement 4: Empty-State Recovery

**User Story:** As a user, I want useful guidance when discover returns no results.

#### Acceptance Criteria (EARS)

1. WHEN no results are returned, THE System SHALL show a clear empty-state message.
2. WHEN semantic mode receives short queries with no results, THE System SHALL provide descriptive-query guidance.
3. Empty-state SHALL include at least one clear refinement/recovery action.

---

### Requirement 5: UX Safety Boundary

**User Story:** As a product owner, I want discover UX improvements without breaking existing search integrations.

#### Acceptance Criteria (EARS)

1. THIS spec SHALL preserve existing semantic + keyword fallback service integration.
2. THIS spec SHALL preserve ownership and permission boundaries for save/message actions.
