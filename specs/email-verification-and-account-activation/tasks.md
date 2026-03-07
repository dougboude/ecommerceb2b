# Implementation Plan

## Pre-Execution Gate Checklist

Before any task begins, confirm both gates pass and document the output:

```python
# Gate 1 — CP5 confirmed
manage.py shell -c "
from marketplace.migration_control.state import get_or_create_state
s = get_or_create_state()
assert s.checkpoint_order == 5, f'CP5 required, got CP{s.checkpoint_order}'
print('Gate 1 OK — CP5 confirmed')
"

# Gate 2 — User.email_verified present
manage.py shell -c "
from marketplace.models import User
from django.core.exceptions import FieldDoesNotExist
try:
    User._meta.get_field('email_verified')
    print('Gate 2 OK — User.email_verified field present')
except FieldDoesNotExist:
    raise AssertionError('User.email_verified missing — check models.py')
"
```

If either gate fails, STOP. Do not proceed with Phase 1 tasks.

---

## Phase 1: Convergence (Reversible)

### Group 1 — EmailVerificationToken Model and Migration

- [ ] 1.1 Add `EmailVerificationToken` to `marketplace/models.py`
  - Fields: `user` (FK User, CASCADE), `token` (UUIDField, unique, db_index), `created_at` (auto_now_add), `expires_at` (DateTimeField), `used_at` (nullable DateTimeField)
  - `TOKEN_EXPIRY_HOURS = 24` class constant
  - `save()` sets `expires_at = now() + timedelta(hours=TOKEN_EXPIRY_HOURS)` on first save if not already set
  - `is_valid` property: `used_at is None and expires_at > now()`
  - `__str__` returns meaningful representation
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 1.2 Generate and apply additive migration for `EmailVerificationToken`
  - Run `manage.py makemigrations` — confirm the new migration is additive only (no drops, no alters on existing tables)
  - Run `manage.py migrate`
  - Confirm `manage.py migration_validate --scope all --fail-on-error` still passes after migration
  - _Requirements: 1.1_

- [ ] 1.3 Register `EmailVerificationToken` in `marketplace/admin.py`
  - `list_display = ["user", "token", "created_at", "expires_at", "used_at"]`
  - `list_filter = ["used_at"]`
  - `raw_id_fields = ["user"]`
  - `readonly_fields = ["token", "created_at"]`
  - Confirm `email_verified` is editable on the User admin change page; add to fieldset if absent
  - _Requirements: 1.5, 7.1, 7.2_

### Group 2 — Signup Flow Integration

- [ ] 2.1 Add `_send_verification_email(request, user)` helper in `marketplace/views.py`
  - Invalidate prior unused tokens: `EmailVerificationToken.objects.filter(user=user, used_at=None).delete()`
  - Create new token: `EmailVerificationToken.objects.create(user=user)`
  - Build absolute verification URL using `request.build_absolute_uri(reverse(...))`
  - Render `templates/registration/verification_email_subject.txt` and `templates/registration/verification_email_body.txt` via `render_to_string`
  - Call `send_mail(...)` inside `try/except Exception`: on failure log with `logger.error` and add `messages.warning` — do not re-raise
  - _Requirements: 2.1, 2.3, 2.4, 2.5, 2.6_

- [ ] 2.2 Update `signup_view` in `marketplace/views.py`
  - Replace `login(request, user)` + `redirect("marketplace:dashboard")` with `_send_verification_email(request, user)` + `redirect("marketplace:verify_email")`
  - The skin cookie redirect logic (skin cookie set on login) moves to `verify_email_confirm` where login now occurs
  - _Requirements: 2.1, 2.2_

### Group 3 — Verification URL and View

- [ ] 3.1 Add `verify_email` view in `marketplace/views.py`
  - Renders `templates/registration/email_verify.html`
  - Accessible to unauthenticated users (no `@login_required`)
  - _Requirements: 3.6_

- [ ] 3.2 Add `verify_email_confirm` view in `marketplace/views.py`
  - `GET /verify-email/<uuid:token>/`
  - Look up token by UUID; raise `Http404` if not found
  - If `used_at is not None`: render `templates/registration/email_verify_used.html`
  - If not `is_valid` (expired): render `templates/registration/email_verify_expired.html`
  - If valid: set `user.email_verified=True`, `token.used_at=now()`, save both, call `login(request, user, backend=...)`, add success message, redirect to `marketplace:dashboard`, set skin cookie
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 3.3 Add new URL patterns to `marketplace/urls.py`
  - `path("verify-email/", views.verify_email, name="verify_email")`
  - `path("verify-email/<uuid:token>/", views.verify_email_confirm, name="verify_email_confirm")`
  - `path("resend-verification/", views.resend_verification, name="resend_verification")`
  - _Requirements: 3.1, 5.1_

### Group 4 — Login Gate

- [ ] 4.1 Update `MarketplaceLoginView.form_valid()` in `marketplace/views.py`
  - After `user = form.get_user()`, check `if not user.email_verified:`
  - If unverified: `form.add_error(None, mark_safe(...))` with resend link anchored to `reverse("marketplace:resend_verification")`, then `return self.form_invalid(form)`
  - Only call `super().form_valid(form)` (and set skin cookie) if `email_verified=True`
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

### Group 5 — Resend Verification Flow

- [ ] 5.1 Add `resend_verification` view in `marketplace/views.py`
  - GET: render `templates/registration/resend_verification.html` with `initial_email` from `request.GET.get("email", "")`
  - POST: look up `User` by email with `email_verified=False`; call `_send_verification_email` if found; swallow `User.DoesNotExist` silently; redirect to `marketplace:verify_email`
  - Accessible to unauthenticated users
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

### Group 6 — Email Templates

- [ ] 6.1 Create `templates/registration/verification_email_subject.txt`
  - Content: `Confirm your NicheMarket account` (single line, no trailing newline)
  - _Requirements: 2.4_

- [ ] 6.2 Create `templates/registration/verification_email_body.txt`
  - Context variables: `display_name`, `verification_url`, `expiry_hours`
  - Include: greeting with display_name (fallback to email), verification URL on its own line, expiry note, ignore-this-email footer
  - _Requirements: 2.5_

### Group 7 — Template Updates

- [ ] 7.1 Update `templates/registration/email_verify.html` (existing stub)
  - Confirm heading reads `Check your email` — update if not
  - Add a link to `{% url 'marketplace:resend_verification' %}` for users who did not receive the email
  - _Requirements: 2.2, 5.1_

- [ ] 7.2 Create `templates/registration/email_verify_expired.html`
  - Extend `base.html`; use `.auth-form` container
  - Heading: `Verification link expired`
  - Explanation: link is valid for 24 hours
  - Action link: `{% url 'marketplace:resend_verification' %}` — "Request a new verification email"
  - _Requirements: 3.3, 6.1_

- [ ] 7.3 Create `templates/registration/email_verify_used.html`
  - Extend `base.html`; use `.auth-form` container
  - Heading: `Already verified`
  - Message: account is already active
  - Action link: `{% url 'marketplace:login' %}` — "Go to login"
  - _Requirements: 3.4, 6.2_

- [ ] 7.4 Create `templates/registration/resend_verification.html`
  - Extend `base.html`; use `.auth-form` container
  - Heading: `Resend verification email`
  - Single email input; submit button: `Send verification email`
  - Pre-populate email field from `initial_email` context variable
  - _Requirements: 5.1_

### Group 8 — Settings

- [ ] 8.1 Audit `settings.py` for `EMAIL_BACKEND`; add if not present
  - Default: `django.core.mail.backends.console.EmailBackend` for local development
  - Override via `os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")`
  - Confirm `EMAIL_HOST`, `EMAIL_PORT`, `DEFAULT_FROM_EMAIL` are also overridable via env vars (add stubs if absent)
  - _Requirements: 7.3, 7.4_

---

## Phase 1 Gate — Before Proceeding to Phase 2

Run the following before beginning Phase 2. All must pass:

```
manage.py test marketplace --verbosity=1
```

Expected: all tests pass, 0 failures, 0 errors. If any test fails, fix the regression before proceeding. Do not carry failing tests into Phase 2.

---

## Phase 2: Tests and Final Verification

### Group 9 — Tests

- [ ] 9.1 Create `marketplace/tests/test_email_verification.py`
  - All tests tagged `@tag('email_verification')`
  - Use `@override_settings(STORAGES=_STATIC_TEST_SETTINGS)` on view test classes (same pattern as `test_permission_policy.py`)
  - Use `@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')` to capture emails
  - _Requirements: 2.1_

- [ ] 9.2 Write `test_signup_does_not_autologin`
  - POST to `/signup/` with valid data
  - Assert response redirects to `verify_email` URL (not dashboard)
  - Assert the session does NOT contain an authenticated user
  - _Requirements: 2.1, 2.2_

- [ ] 9.3 Write `test_signup_creates_token`
  - POST to `/signup/` with valid data
  - Assert `EmailVerificationToken.objects.filter(user=<new_user>).count() == 1`
  - _Requirements: 2.1_

- [ ] 9.4 Write `test_signup_sends_verification_email`
  - POST to `/signup/` with valid data
  - Assert `len(mail.outbox) == 1`
  - Assert `mail.outbox[0].subject` contains `"Confirm"`
  - Assert verification URL appears in `mail.outbox[0].body`
  - _Requirements: 2.3, 2.4, 2.5_

- [ ] 9.5 Write `test_verify_valid_token_activates_and_logs_in`
  - Create user with `email_verified=False` + valid token
  - GET `/verify-email/<token>/`
  - Assert user `email_verified=True` after response
  - Assert token `used_at` is set
  - Assert response redirects to dashboard
  - Assert session contains authenticated user
  - _Requirements: 3.1, 3.2_

- [ ] 9.6 Write `test_verify_expired_token_shows_expired_page`
  - Create expired token (set `expires_at` in the past)
  - GET `/verify-email/<token>/`
  - Assert response renders `email_verify_expired.html`
  - Assert user `email_verified` remains `False`
  - _Requirements: 3.3, 6.1_

- [ ] 9.7 Write `test_verify_used_token_shows_used_page`
  - Create token with `used_at` already set
  - GET `/verify-email/<token>/`
  - Assert response renders `email_verify_used.html`
  - _Requirements: 3.4, 6.2_

- [ ] 9.8 Write `test_verify_nonexistent_token_returns_404`
  - GET `/verify-email/<random-uuid>/`
  - Assert 404 response
  - _Requirements: 3.5_

- [ ] 9.9 Write `test_login_blocked_for_unverified_user`
  - Create user with `email_verified=False`
  - POST to `/login/` with valid credentials
  - Assert response does NOT redirect to dashboard
  - Assert session does not contain authenticated user
  - Assert response contains verification error message
  - _Requirements: 4.1, 4.2, 4.3_

- [ ] 9.10 Write `test_login_allowed_for_verified_user`
  - Create user with `email_verified=True`
  - POST to `/login/` with valid credentials
  - Assert response redirects to dashboard (or next URL)
  - Assert session contains authenticated user
  - _Requirements: 4.1_

- [ ] 9.11 Write `test_resend_sends_new_token`
  - Create user with `email_verified=False`; create an existing unused token
  - POST to `/resend-verification/` with that user's email
  - Assert old token is deleted (or has no `used_at`-less siblings after)
  - Assert new token created
  - Assert one email sent
  - _Requirements: 5.2_

- [ ] 9.12 Write `test_resend_neutral_for_unknown_email`
  - POST to `/resend-verification/` with a non-existent email
  - Assert response redirects to `verify_email` (neutral)
  - Assert `len(mail.outbox) == 0`
  - _Requirements: 5.3_

- [ ] 9.13 Write `test_resend_neutral_for_already_verified`
  - Create user with `email_verified=True`
  - POST to `/resend-verification/` with that email
  - Assert response redirects to `verify_email` (neutral)
  - Assert `len(mail.outbox) == 0`
  - _Requirements: 5.3_

- [ ] 9.14 Write `test_token_is_valid_property`
  - Unit test (no HTTP): new token → `is_valid=True`; token with past `expires_at` → `is_valid=False`; token with `used_at` set → `is_valid=False`
  - _Requirements: 1.3, 1.4_

- [ ] 9.15 Write `test_email_send_failure_does_not_break_signup`
  - Patch `send_mail` to raise `Exception("smtp error")`
  - POST to `/signup/` with valid data
  - Assert user was created in DB
  - Assert response redirects (does not 500)
  - _Requirements: 2.6_

### Group 10 — Final Verification Checkpoint

- [ ] 10.1 Run full test suite
  ```
  manage.py test marketplace --verbosity=1
  ```
  Expected: all tests pass. Zero failures. Zero errors.
  _Requirements: all_

- [ ] 10.2 Run all migration validate scopes
  ```
  manage.py migration_validate --scope all --fail-on-error
  ```
  Expected: all scopes pass. New `email_verification` scope not required (no compliance scanner in this spec).
  _Requirements: 1.2_

- [ ] 10.3 Manual smoke test (dev environment)
  - Start Django server with console email backend
  - Register a new account
  - Confirm no auto-login; redirected to "check your email" page
  - Copy verification URL from console output; visit it
  - Confirm activation success and redirect to dashboard
  - Log out; confirm login works for the now-verified account
  - Register a second account; attempt login before verifying; confirm blocked with resend link
  - Use resend flow; confirm new token appears in console
  - _Requirements: 2.1, 2.2, 3.2, 4.1, 5.2_

- [ ] 10.4 Confirm scope boundaries — no unrelated features included
  - No email change verification code added
  - No resend rate limiting code added
  - No OAuth or social login added
  - No profile image upload, radius filtering, listing expiry, or operator tools
  - _Requirements: 8.2, 8.3, 8.4, 8.5_

- [ ] 10.5 Update `specs/SPEC_ORDER.md` status to `REQ, DES, TASK, EXEC`
  - Update `ai-docs/SESSION_STATUS.md` with implementation summary
