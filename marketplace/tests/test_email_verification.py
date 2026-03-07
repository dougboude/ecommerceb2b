"""
Feature 9: Email Verification and Account Activation tests.

Covers:
- EmailVerificationToken model (is_valid property, expiry, revoked_at)
- Signup flow: no auto-login, token created, email sent
- verify_email_confirm: activation, expiry error, used error, 404
- Login gate: unverified accounts blocked, verified accounts allowed
- Resend flow: new token sent, old tokens revoked, neutral for unknown/verified
- Email send failure does not break signup
"""
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings, tag
from django.urls import reverse
from django.utils.timezone import now as timezone_now

from marketplace.models import EmailVerificationToken, User


_STATIC_TEST_SETTINGS = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

_LOCMEM_EMAIL = "django.core.mail.backends.locmem.EmailBackend"


def _make_user(email="verify@example.com", verified=False, **kwargs):
    user = User.objects.create_user(
        email=email,
        password="testpass123",
        country="US",
        display_name="Test User",
        **kwargs,
    )
    if verified:
        user.email_verified = True
        user.save(update_fields=["email_verified"])
    return user


def _make_token(user, expired=False, used=False, revoked=False):
    token = EmailVerificationToken(user=user)
    if expired:
        token.expires_at = timezone_now() - timedelta(hours=1)
    else:
        token.expires_at = timezone_now() + timedelta(hours=24)
    token.save()
    if used:
        token.used_at = timezone_now()
        token.save(update_fields=["used_at"])
    if revoked:
        token.revoked_at = timezone_now()
        token.save(update_fields=["revoked_at"])
    return token


@override_settings(STORAGES=_STATIC_TEST_SETTINGS, EMAIL_BACKEND=_LOCMEM_EMAIL)
@tag("email_verification")
class TokenModelTests(TestCase):
    def test_is_valid_for_fresh_token(self):
        user = _make_user()
        token = _make_token(user)
        self.assertTrue(token.is_valid)

    def test_is_valid_false_when_expired(self):
        user = _make_user()
        token = _make_token(user, expired=True)
        self.assertFalse(token.is_valid)

    def test_is_valid_false_when_used(self):
        user = _make_user()
        token = _make_token(user, used=True)
        self.assertFalse(token.is_valid)

    def test_is_valid_false_when_revoked(self):
        user = _make_user()
        token = _make_token(user, revoked=True)
        self.assertFalse(token.is_valid)

    def test_expires_at_set_automatically_on_create(self):
        user = _make_user()
        before = timezone_now()
        token = EmailVerificationToken.objects.create(user=user)
        after = timezone_now()
        expected_min = before + timedelta(hours=EmailVerificationToken.TOKEN_EXPIRY_HOURS)
        expected_max = after + timedelta(hours=EmailVerificationToken.TOKEN_EXPIRY_HOURS)
        self.assertGreaterEqual(token.expires_at, expected_min)
        self.assertLessEqual(token.expires_at, expected_max)


@override_settings(STORAGES=_STATIC_TEST_SETTINGS, EMAIL_BACKEND=_LOCMEM_EMAIL)
@tag("email_verification")
class SignupFlowTests(TestCase):
    def test_signup_does_not_autologin(self):
        response = self.client.post(
            reverse("marketplace:signup"),
            {"email": "new@example.com", "password1": "strongpass99!", "password2": "strongpass99!", "country": "US", "display_name": "Test User"},
        )
        # Should redirect to verify_email, not dashboard
        self.assertRedirects(response, reverse("marketplace:verify_email"))
        # Session must not contain an authenticated user
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_signup_creates_token(self):
        self.client.post(
            reverse("marketplace:signup"),
            {"email": "new2@example.com", "password1": "strongpass99!", "password2": "strongpass99!", "country": "US", "display_name": "Test User"},
        )
        user = User.objects.get(email="new2@example.com")
        self.assertEqual(EmailVerificationToken.objects.filter(user=user).count(), 1)

    def test_signup_sends_verification_email(self):
        self.client.post(
            reverse("marketplace:signup"),
            {"email": "new3@example.com", "password1": "strongpass99!", "password2": "strongpass99!", "country": "US", "display_name": "Test User"},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Confirm", mail.outbox[0].subject)
        user = User.objects.get(email="new3@example.com")
        token = EmailVerificationToken.objects.get(user=user)
        self.assertIn(str(token.token), mail.outbox[0].body)

    def test_email_send_failure_does_not_break_signup(self):
        with patch("marketplace.views.send_mail", side_effect=Exception("smtp error")):
            response = self.client.post(
                reverse("marketplace:signup"),
                {"email": "fail@example.com", "password1": "strongpass99!", "password2": "strongpass99!", "country": "US", "display_name": "Test User"},
            )
        # User should still be created
        self.assertTrue(User.objects.filter(email="fail@example.com").exists())
        # Response should redirect (not 500)
        self.assertEqual(response.status_code, 302)


@override_settings(STORAGES=_STATIC_TEST_SETTINGS, EMAIL_BACKEND=_LOCMEM_EMAIL)
@tag("email_verification")
class VerifyEmailConfirmTests(TestCase):
    def test_valid_token_activates_and_logs_in(self):
        user = _make_user()
        token = _make_token(user)
        url = reverse("marketplace:verify_email_confirm", args=[token.token])
        response = self.client.get(url)
        self.assertRedirects(response, reverse("marketplace:dashboard"))
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        token.refresh_from_db()
        self.assertIsNotNone(token.used_at)
        self.assertIn("_auth_user_id", self.client.session)

    def test_expired_token_shows_expired_page(self):
        user = _make_user()
        token = _make_token(user, expired=True)
        response = self.client.get(
            reverse("marketplace:verify_email_confirm", args=[token.token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/email_verify_expired.html")
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_used_token_shows_used_page(self):
        user = _make_user()
        token = _make_token(user, used=True)
        response = self.client.get(
            reverse("marketplace:verify_email_confirm", args=[token.token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/email_verify_used.html")

    def test_nonexistent_token_returns_404(self):
        import uuid
        response = self.client.get(
            reverse("marketplace:verify_email_confirm", args=[uuid.uuid4()])
        )
        self.assertEqual(response.status_code, 404)

    def test_revoked_token_shows_expired_page(self):
        # Revoked = not is_valid (revoked_at is set but used_at is None)
        user = _make_user()
        token = _make_token(user, revoked=True)
        # Revoked token has used_at=None so it hits the is_valid check path
        response = self.client.get(
            reverse("marketplace:verify_email_confirm", args=[token.token])
        )
        self.assertEqual(response.status_code, 200)
        # revoked_at set → is_valid=False → expired page
        self.assertTemplateUsed(response, "registration/email_verify_expired.html")


@override_settings(STORAGES=_STATIC_TEST_SETTINGS, EMAIL_BACKEND=_LOCMEM_EMAIL)
@tag("email_verification")
class LoginGateTests(TestCase):
    def test_login_blocked_for_unverified_user(self):
        user = _make_user(email="unverified@example.com", verified=False)
        response = self.client.post(
            reverse("marketplace:login"),
            {"username": user.email, "password": "testpass123"},
        )
        # Should NOT redirect to dashboard
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        html = response.content.decode()
        self.assertIn("not verified", html.lower())

    def test_login_blocked_shows_resend_link(self):
        user = _make_user(email="unverified2@example.com", verified=False)
        response = self.client.post(
            reverse("marketplace:login"),
            {"username": user.email, "password": "testpass123"},
        )
        html = response.content.decode()
        self.assertIn(reverse("marketplace:resend_verification"), html)

    def test_login_allowed_for_verified_user(self):
        user = _make_user(email="verified@example.com", verified=True)
        response = self.client.post(
            reverse("marketplace:login"),
            {"username": user.email, "password": "testpass123"},
        )
        self.assertRedirects(response, reverse("marketplace:dashboard"))
        self.assertIn("_auth_user_id", self.client.session)


@override_settings(STORAGES=_STATIC_TEST_SETTINGS, EMAIL_BACKEND=_LOCMEM_EMAIL)
@tag("email_verification")
class ResendVerificationTests(TestCase):
    def test_resend_sends_new_token(self):
        user = _make_user(email="resend@example.com", verified=False)
        self.client.post(
            reverse("marketplace:resend_verification"),
            {"email": user.email},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailVerificationToken.objects.filter(user=user).count(), 1)

    def test_resend_revokes_old_tokens(self):
        user = _make_user(email="resend2@example.com", verified=False)
        old_token = _make_token(user)
        self.assertIsNone(old_token.revoked_at)

        self.client.post(
            reverse("marketplace:resend_verification"),
            {"email": user.email},
        )

        old_token.refresh_from_db()
        # Old token must be revoked, not deleted
        self.assertIsNotNone(old_token.revoked_at)
        self.assertIsNone(old_token.used_at)
        # New token was created
        self.assertEqual(
            EmailVerificationToken.objects.filter(user=user, revoked_at=None).count(), 1
        )

    def test_resend_neutral_for_unknown_email(self):
        response = self.client.post(
            reverse("marketplace:resend_verification"),
            {"email": "nobody@example.com"},
        )
        self.assertRedirects(response, reverse("marketplace:verify_email"))
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_neutral_for_already_verified(self):
        user = _make_user(email="alreadyverified@example.com", verified=True)
        response = self.client.post(
            reverse("marketplace:resend_verification"),
            {"email": user.email},
        )
        self.assertRedirects(response, reverse("marketplace:verify_email"))
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_get_renders_form(self):
        response = self.client.get(reverse("marketplace:resend_verification"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/resend_verification.html")

    def test_resend_get_prefills_email_from_query_param(self):
        response = self.client.get(
            reverse("marketplace:resend_verification") + "?email=test@example.com"
        )
        html = response.content.decode()
        self.assertIn("test@example.com", html)
