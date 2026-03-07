# Requirements Document

## Introduction

This spec implements email verification as a required step in the NicheMarket account activation flow. After registration, new accounts are placed in an unverified state. A time-limited single-use token is emailed to the user. Clicking the link activates the account. Login is blocked for unverified accounts until activation is complete.

`User.email_verified` already exists in the schema (`BooleanField(default=False)`). This spec adds the token model, wires the signup and login flows, and delivers the end-to-end activation UX. It is additive — no destructive schema changes and no new migration checkpoint.

## State Assumptions

| Assumption | Required State | Fail Condition |
|---|---|---|
| Foundation complete | CP5 achieved | Block execution if `MigrationState.checkpoint_order < 5` |
| `User.email_verified` field | Present on the `User` model | Block execution if `User._meta.get_field('email_verified')` raises `FieldDoesNotExist` |
| Feature 8 complete | `ui-language-and-navigation-derolification` is `EXEC` | Block if Feature 8 tasks are not all marked complete in `specs/SPEC_ORDER.md` |

**Pre-execution gate (run before any task begins):**
```python
manage.py shell -c "
from marketplace.migration_control.state import get_or_create_state
from marketplace.models import User
from django.core.exceptions import FieldDoesNotExist

s = get_or_create_state()
assert s.checkpoint_order == 5, f'CP5 required, got CP{s.checkpoint_order}'
print('Gate 1 OK — CP5 confirmed')

try:
    User._meta.get_field('email_verified')
    print('Gate 2 OK — User.email_verified field present')
except FieldDoesNotExist:
    raise AssertionError('User.email_verified missing — check models.py')
"
```

## Dependencies

- **Required predecessor specs:** all foundation specs 1–7 (`EXEC`), Feature 8 `ui-language-and-navigation-derolification` (`EXEC`)
- No new migration checkpoint is required. Changes are additive only.

## Glossary

- **Unverified account:** A `User` with `email_verified=False`. Created at signup; cannot log in until activated.
- **Verification token:** An `EmailVerificationToken` record: UUID token, expiry timestamp, single-use constraint.
- **Activation:** Setting `user.email_verified=True` and marking the token used. Triggered by visiting the verification URL.
- **Token expiry:** 24 hours from creation. Expired tokens cannot activate an account.
- **Resend:** Creating a new token + sending a new email, invalidating any prior unused tokens for that user.

---

## Requirements

### Requirement 1: EmailVerificationToken Model

**User Story:** As a platform architect, I want a dedicated token model for email verification so that token lifecycle (creation, expiry, use) is auditable and self-contained.

#### Acceptance Criteria

1. THE System SHALL add `EmailVerificationToken` to `marketplace/models.py` with fields: `user` (FK to `User`, CASCADE), `token` (UUID, unique, db_index), `created_at` (auto_now_add), `expires_at` (DateTimeField), `used_at` (nullable DateTimeField).
2. THE `expires_at` field SHALL be set to `created_at + 24 hours` automatically at creation — not left to the caller.
3. A token SHALL be valid only when `used_at is None` AND `expires_at > now()`.
4. THE model SHALL expose an `is_valid` property returning `True` only for valid tokens.
5. THE `EmailVerificationToken` table SHALL be registered in Django admin.

### Requirement 2: Signup Triggers Verification

**User Story:** As a new user, I want to receive a verification email immediately after registering so that I can activate my account in a single flow.

#### Acceptance Criteria

1. WHEN a new user submits a valid signup form, THE System SHALL create the `User`, create an `EmailVerificationToken`, and send the verification email before redirecting.
2. THE System SHALL NOT log the user in automatically after signup. The post-signup redirect SHALL be to `GET /verify-email/` (the "check your email" confirmation page), not the dashboard.
3. THE verification email SHALL contain a clickable link to `GET /verify-email/<token>/` that is valid for 24 hours.
4. THE email subject SHALL be `"Confirm your NicheMarket account"`.
5. THE email body SHALL include the user's display name (or email if none), the verification link, and a note that the link expires in 24 hours.
6. IF email sending raises an exception, THE System SHALL log the error, complete user creation, and display a message directing the user to use the resend flow. The signup SHALL NOT fail because of an email send error.

### Requirement 3: Verification Link and Account Activation

**User Story:** As a new user, I want clicking the link in my verification email to immediately activate my account so I can log in without any additional steps.

#### Acceptance Criteria

1. `GET /verify-email/<token>/` SHALL look up the `EmailVerificationToken` by its UUID.
2. IF the token `is_valid`: THE System SHALL set `user.email_verified=True`, set `token.used_at=now()`, save both, log the user in, and redirect to `marketplace:dashboard` with a success message.
3. IF the token is expired (`used_at is None` but `expires_at <= now()`): THE System SHALL render an "expired link" error page with a link to `/resend-verification/`.
4. IF the token has already been used (`used_at is not None`): THE System SHALL render an "already verified" page directing the user to log in.
5. IF the token UUID does not exist: THE System SHALL return a 404 response.
6. THE verification view SHALL be accessible without authentication — unauthenticated users must be able to visit the link and log in as part of the flow.

### Requirement 4: Login Gate for Unverified Accounts

**User Story:** As a platform operator, I want unverified accounts blocked from logging in so that only email-confirmed users access the platform.

#### Acceptance Criteria

1. WHEN a user attempts to log in with valid credentials and `user.email_verified=False`, THE System SHALL reject the login attempt and NOT create an authenticated session.
2. THE rejection SHALL display a non-field form error on the login page: a message that the email is not verified, with a link to `/resend-verification/`.
3. THE login gate SHALL apply to all users including staff and superusers (unless `email_verified` is manually set to `True` via admin).
4. THE gate SHALL be enforced in `MarketplaceLoginView.form_valid()` — not via a custom authentication backend — to keep the existing auth backend unchanged.

### Requirement 5: Resend Verification Email

**User Story:** As a user whose verification email expired or was lost, I want to request a new verification email so I can activate my account without re-registering.

#### Acceptance Criteria

1. `GET /resend-verification/` SHALL render a page with an email address input form.
2. `POST /resend-verification/` SHALL accept an email address. IF a `User` with that email and `email_verified=False` exists, THE System SHALL invalidate all existing unused tokens for that user and create + send a new one.
3. IF no matching unverified user exists (email not found, or account already verified), THE System SHALL show the same neutral success-like confirmation — it SHALL NOT leak whether an account exists for that email.
4. After POST (success or indeterminate), THE System SHALL redirect to `GET /verify-email/` (the "check your email" confirmation page).
5. THE resend view SHALL be accessible without authentication.

### Requirement 6: Token Expiry and Error States

**User Story:** As a user with an expired verification link, I want a clear message and a fast path to request a new one so I am not stuck at a dead-end error.

#### Acceptance Criteria

1. WHEN a user visits an expired verification URL, THE System SHALL display a page with: heading `"Verification link expired"`, explanation that links are valid for 24 hours, and a link to `/resend-verification/`.
2. WHEN a user visits an already-used verification URL, THE System SHALL display a page with: heading `"Already verified"`, a note that the account is active, and a link to the login page.
3. Both error states SHALL render within `base.html` using `.auth-form` styling for consistency.

### Requirement 7: Admin and Development Support

**User Story:** As an operator or developer, I want to manage verification state in Django admin and send verification emails to the console in development so I can support users and test without SMTP.

#### Acceptance Criteria

1. THE Django admin `User` change page SHALL include `email_verified` as an editable field.
2. THE Django admin SHALL register `EmailVerificationToken` with fields visible and editable for operator support.
3. `settings.py` SHALL default `EMAIL_BACKEND` to `django.core.mail.backends.console.EmailBackend` for local development so verification emails print to the terminal.
4. THE email backend SHALL be overridable via the `EMAIL_BACKEND` environment variable for staging/production.

### Requirement 8: Scope Boundaries

**User Story:** As a product owner, I want this spec tightly scoped to the initial verification flow so feature work is not bundled in.

#### Acceptance Criteria

1. THE System SHALL limit scope to: `EmailVerificationToken` model + migration, signup flow changes, verification URL and view, login gate, resend flow, email templates, and admin wiring.
2. THE System SHALL NOT implement email change verification (verifying a new email on profile update). That is a future spec.
3. THE System SHALL NOT implement resend rate limiting. That is a future hardening task.
4. THE System SHALL NOT implement social/OAuth login.
5. THE System SHALL NOT add profile image upload, radius filtering, listing expiry, or operator moderation tools in this spec.
