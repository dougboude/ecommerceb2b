# Email Verification and Account Activation — Design Document

## Overview

This spec is entirely additive. No existing tables are dropped or altered; no migration checkpoint advances. The work divides into two phases:

- **Phase 1 (Convergence):** Add `EmailVerificationToken`, wire signup and login, deliver the verification and resend flows. All changes are reversible via migration rollback + git revert.
- **Phase 2 (Verification):** Full test suite, manual smoke tests, sign-off.

## Pre-Execution Gate

Before any Phase 1 task begins, confirm both gates pass:

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

If either gate fails, STOP. Do not proceed.

## Architecture

```
Phase 1: Convergence (reversible)
  ┌──────────────────────────────────────────────────────────────────┐
  │  marketplace/models.py                                           │
  │  └── EmailVerificationToken (new model)                          │
  │       ├── user FK, token UUID, created_at, expires_at, used_at  │
  │       └── is_valid property                                      │
  │                                                                  │
  │  marketplace/migrations/                                         │
  │  └── 0015_emailverificationtoken.py (new, additive)              │
  │                                                                  │
  │  marketplace/views.py                                            │
  │  ├── signup_view — stop auto-login; send token; redirect         │
  │  ├── verify_email_confirm (new) — activate on valid token        │
  │  ├── resend_verification (new) — create new token + send         │
  │  └── MarketplaceLoginView — gate on email_verified               │
  │                                                                  │
  │  marketplace/urls.py                                             │
  │  ├── path("verify-email/", ..., name="verify_email")             │
  │  ├── path("verify-email/<uuid:token>/", ..., name="verify_email_confirm") │
  │  └── path("resend-verification/", ..., name="resend_verification")│
  │                                                                  │
  │  templates/registration/                                         │
  │  ├── email_verify.html (stub exists — enhance to show resend)    │
  │  ├── email_verify_expired.html (new)                             │
  │  ├── email_verify_used.html (new)                                │
  │  ├── resend_verification.html (new)                              │
  │  ├── verification_email_subject.txt (new)                        │
  │  └── verification_email_body.txt (new)                           │
  │                                                                  │
  │  marketplace/admin.py                                            │
  │  └── EmailVerificationToken registered                           │
  │                                                                  │
  │  settings.py                                                     │
  │  └── EMAIL_BACKEND defaulting to console backend for dev         │
  └──────────────────────────────────────────────────────────────────┘

Phase 2: Verification
  ┌──────────────────────────────────────────────────────────────────┐
  │  marketplace/tests/test_email_verification.py (new)              │
  │  Full test suite passing                                         │
  └──────────────────────────────────────────────────────────────────┘
```

## Phase 1: EmailVerificationToken Model

### Model Definition

```python
import uuid
from django.utils.timezone import now
from datetime import timedelta

class EmailVerificationToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_tokens",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    TOKEN_EXPIRY_HOURS = 24

    def save(self, *args, **kwargs):
        if not self.pk and not self.expires_at:
            self.expires_at = now() + timedelta(hours=self.TOKEN_EXPIRY_HOURS)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > now()

    def __str__(self):
        return f"VerificationToken({self.user_id}, expires={self.expires_at})"
```

The token UUID is generated by default and never exposed to the user except in the email URL. `expires_at` is set automatically on first save.

## Phase 1: Signup Flow Changes

### Current state

`signup_view` calls `login(request, user)` immediately after `form.save()`, then redirects to `marketplace:dashboard`. There is no verification gate.

### Target state

```python
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("marketplace:dashboard")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            identity_adapter.update_identity(
                user,
                organization_name=form.cleaned_data.get("organization_name"),
            )
            _send_verification_email(request, user)  # new helper
            # Do NOT call login() here
            return redirect("marketplace:verify_email")  # "check your email" page
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})
```

**`_send_verification_email(request, user)` helper:**
1. Invalidate any prior unused tokens for the user: `EmailVerificationToken.objects.filter(user=user, used_at=None).delete()`
2. Create a new token: `token = EmailVerificationToken.objects.create(user=user)`
3. Build the verification URL: `request.build_absolute_uri(reverse('marketplace:verify_email_confirm', args=[token.token]))`
4. Render email templates (`verification_email_subject.txt`, `verification_email_body.txt`) with context `{user, verification_url, expiry_hours}`
5. Call `send_mail(...)` wrapped in `try/except Exception`. On exception: log with `logger.error(...)` and add a `django.messages.warning(...)` to the request — do not re-raise.

## Phase 1: Verification View

### `verify_email` (GET)

Renders `templates/registration/email_verify.html` — the "Check your email" confirmation page. Already exists as a stub. Enhance to include a link to `/resend-verification/` for users who did not receive the email.

Accessible to unauthenticated users. No token logic here.

### `verify_email_confirm` (GET)

URL: `GET /verify-email/<uuid:token>/`

```python
def verify_email_confirm(request, token):
    try:
        obj = EmailVerificationToken.objects.select_related("user").get(token=token)
    except EmailVerificationToken.DoesNotExist:
        raise Http404

    if obj.used_at is not None:
        return render(request, "registration/email_verify_used.html")

    if not obj.is_valid:  # expired (used_at is None but past expiry)
        return render(request, "registration/email_verify_expired.html")

    # Valid — activate
    obj.user.email_verified = True
    obj.user.save(update_fields=["email_verified"])
    obj.used_at = now()
    obj.save(update_fields=["used_at"])
    login(request, obj.user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, _("Email verified. Welcome to NicheMarket!"))
    return redirect("marketplace:dashboard")
```

Checking `used_at is not None` before `is_valid` ensures "already used" and "expired" are distinct states. The `backend` kwarg is required when calling `login()` outside of `authenticate()`.

## Phase 1: Login Gate

### Current state

`MarketplaceLoginView.form_valid()` calls `super().form_valid(form)` and sets the skin cookie. No verification check.

### Target state

```python
class MarketplaceLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        if not user.email_verified:
            form.add_error(
                None,
                mark_safe(_(
                    'Email not verified. '
                    '<a href="%s">Resend verification email</a>.'
                ) % reverse("marketplace:resend_verification"))
            )
            return self.form_invalid(form)
        response = super().form_valid(form)
        return _set_skin_cookie(response, user.skin)
```

`mark_safe` is used here only for the anchor tag — the URL is reverse-resolved (no user input). This is safe.

## Phase 1: Resend Verification Flow

### `resend_verification` (GET + POST)

URL: `GET/POST /resend-verification/`

**GET:** Render `templates/registration/resend_verification.html` — a single email input form. If a `?email=` query param is present (linked from the login gate), pre-populate the field.

**POST:**
```python
def resend_verification(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        try:
            user = User.objects.get(email__iexact=email, email_verified=False)
            _send_verification_email(request, user)
        except User.DoesNotExist:
            pass  # neutral — do not leak account existence
        return redirect("marketplace:verify_email")
    # GET
    initial_email = request.GET.get("email", "")
    return render(request, "registration/resend_verification.html", {"initial_email": initial_email})
```

The `except User.DoesNotExist: pass` pattern handles both "no account" and "already verified" cases (a verified user would also fail `email_verified=False`). Both paths silently redirect to the confirmation page.

## Phase 1: Email Templates

All email templates live in `templates/registration/`:

**`verification_email_subject.txt`**
```
Confirm your NicheMarket account
```
(Single line, no trailing newline — Django uses this as the subject verbatim.)

**`verification_email_body.txt`**
```
Hi {{ display_name }},

Please confirm your NicheMarket account by clicking the link below:

{{ verification_url }}

This link expires in {{ expiry_hours }} hours.

If you did not register for NicheMarket, you can safely ignore this email.
```

`display_name` is `user.display_name` if set, otherwise `user.email`. Both templates are rendered with Django's template engine via `render_to_string(template, context)`.

## Phase 1: New URL Patterns

Three new paths added to `marketplace/urls.py`:

```python
path("verify-email/", views.verify_email, name="verify_email"),
path("verify-email/<uuid:token>/", views.verify_email_confirm, name="verify_email_confirm"),
path("resend-verification/", views.resend_verification, name="resend_verification"),
```

`<uuid:token>` uses Django's built-in UUID path converter — invalid UUIDs return 404 automatically without reaching the view.

## Phase 1: Settings

```python
# settings.py — development default
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
)
```

In development, verification emails are printed to the terminal. In staging/production, set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` (plus `EMAIL_HOST`, `EMAIL_PORT`, etc.) via environment variables.

## Phase 1: Admin Registration

```python
# marketplace/admin.py — additions
@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "token", "created_at", "expires_at", "used_at"]
    list_filter = ["used_at"]
    raw_id_fields = ["user"]
    readonly_fields = ["token", "created_at"]
```

`User` admin already exposes `email_verified` via `fieldsets` or `fields` — confirm it is editable. If not, add it to the relevant fieldset.

## Phase 2: Testing Strategy

### Test file: `marketplace/tests/test_email_verification.py`

All tests tagged `@tag('email_verification')`. Use `@override_settings(STORAGES=_STATIC_TEST_SETTINGS)` for view tests (same pattern as `test_permission_policy.py`). Use `@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')` to capture sent emails without SMTP.

| Test | What it verifies |
|---|---|
| `test_signup_does_not_autologin` | POST signup → response is redirect to verify_email page, user is NOT authenticated in session |
| `test_signup_creates_token` | POST signup → `EmailVerificationToken` record created for new user |
| `test_signup_sends_verification_email` | POST signup → one email sent, subject contains "Confirm", body contains verification URL |
| `test_verify_valid_token_activates_and_logs_in` | GET valid token URL → `email_verified=True`, token `used_at` set, session authenticated, redirect to dashboard |
| `test_verify_expired_token_shows_expired_page` | GET expired token URL → expired template rendered, no login |
| `test_verify_used_token_shows_used_page` | GET already-used token URL → used template rendered |
| `test_verify_nonexistent_token_returns_404` | GET unknown UUID → 404 |
| `test_login_blocked_for_unverified_user` | POST login with valid credentials, `email_verified=False` → form error, no session |
| `test_login_allowed_for_verified_user` | POST login with valid credentials, `email_verified=True` → redirect to dashboard |
| `test_resend_sends_new_token_for_unverified` | POST resend with valid unverified email → new token created, new email sent |
| `test_resend_invalidates_old_tokens` | POST resend → prior unused tokens for that user deleted before new one created |
| `test_resend_neutral_response_for_unknown_email` | POST resend with unknown email → redirect to verify_email page, no error, no email |
| `test_resend_neutral_response_for_verified_user` | POST resend for already-verified email → same neutral redirect, no email |
| `test_token_is_valid_property` | Unit test: new token → `is_valid=True`; expired token → `is_valid=False`; used token → `is_valid=False` |
| `test_email_send_failure_does_not_break_signup` | Patch `send_mail` to raise → signup completes, user created, warning message shown |

## Error Handling

| Error | Condition | Recovery |
|---|---|---|
| `PreconditionFailed: CP5 not achieved` | Checkpoint < 5 | Do not proceed; complete foundation specs first |
| `PreconditionFailed: email_verified missing` | Field absent from `User` | Add field via migration before proceeding |
| Email send failure | SMTP/backend exception | Log, warn user, do not fail signup. User can resend. |
| Token not found | UUID not in DB | 404 — no recovery needed |
| Token expired | `expires_at <= now()` | Render expired page with resend link |
| Token reuse | `used_at is not None` | Render "already verified" page |

## Scope Boundaries

- **In scope:** `EmailVerificationToken` model, signup flow gate, verification URL, login gate, resend flow, email templates, admin wiring, settings EMAIL_BACKEND.
- **Out of scope:** Email change verification, resend rate limiting, OAuth/social login, profile image upload, radius filtering, listing expiry, operator tools.
