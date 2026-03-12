# Requirements Document

## Introduction

This spec refines the account access journey (signup, verification, login, resend, recovery screens) to remove onboarding dead ends and make progression explicit. It builds on existing authentication and email verification capabilities.

## Dependencies

- `navigation-ia-unification`
- `cross-page-feedback-recovery-empty-state-system`
- Existing auth and email verification implementation

## Scope Boundaries

### In Scope
- Auth entry-page flow coherence
- Verification/recovery navigation clarity
- Login block/recovery clarity for unverified users
- Consistent auth next-action paths

### Out of Scope
- New auth providers (OAuth/social)
- New account policy models
- New security domains beyond current auth/verification scope

---

## Requirements

### Requirement 1: Auth Entry Flow Clarity

**User Story:** As a new user, I want to understand the exact next step at each auth stage.

#### Acceptance Criteria (EARS)

1. WHEN a user signs up successfully, THE System SHALL route to a clear verification-wait page.
2. WHEN login is blocked due to unverified email, THE System SHALL provide a direct resend-recovery path.
3. WHEN verification succeeds, THE System SHALL route users to an obvious first authenticated destination.

---

### Requirement 2: Verification State Page Consistency

**User Story:** As a user in verification states, I want consistent pages with actionable recovery.

#### Acceptance Criteria (EARS)

1. WHEN verification link is expired, THE System SHALL provide a direct resend action.
2. WHEN verification link is already used, THE System SHALL provide clear login path.
3. WHEN on check-email page, THE System SHALL provide both resend and login navigation.

---

### Requirement 3: Auth Dead-End Elimination

**User Story:** As an unauthenticated user, I want no auth page to strand me.

#### Acceptance Criteria (EARS)

1. WHEN a user is on any auth/verification state page, THE page SHALL include at least one clear progression action.
2. THE System SHALL avoid terminal auth states with no operational next step.

---

### Requirement 4: Terminology and Message Consistency in Access Flow

**User Story:** As a user, I want auth messaging to be consistent and unambiguous.

#### Acceptance Criteria (EARS)

1. THE System SHALL use consistent labels for signup/login/verify/resend states.
2. WHEN access is blocked, THE error copy SHALL explain reason and immediate resolution path.

---

### Requirement 5: Safety Boundary

**User Story:** As a product owner, I want journey improvements without altering core security rules.

#### Acceptance Criteria (EARS)

1. THIS spec SHALL preserve existing verification gate policy.
2. THIS spec SHALL preserve existing permission/session behavior unless explicitly required for journey clarity.
