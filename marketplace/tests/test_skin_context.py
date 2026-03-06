from types import SimpleNamespace

from django.test import SimpleTestCase

from marketplace.context_processors import SKIN_COOKIE_NAME, skin


class SkinContextProcessorTests(SimpleTestCase):
    def _request(self, *, is_authenticated=False, user_skin=None, cookie_skin=None):
        user = SimpleNamespace(is_authenticated=is_authenticated, skin=user_skin)
        cookies = {}
        if cookie_skin is not None:
            cookies[SKIN_COOKIE_NAME] = cookie_skin
        return SimpleNamespace(user=user, COOKIES=cookies)

    def test_anonymous_uses_cookie_skin_when_valid(self):
        request = self._request(cookie_skin="simple-blue")
        context = skin(request)
        self.assertEqual(context["skin_css"], "css/skin-simple-blue.css")

    def test_anonymous_invalid_cookie_falls_back_to_default_skin(self):
        request = self._request(cookie_skin="not-a-real-skin")
        context = skin(request)
        self.assertEqual(context["skin_css"], "css/skin-simple-blue.css")

    def test_authenticated_user_skin_overrides_cookie(self):
        request = self._request(
            is_authenticated=True,
            user_skin="simple-blue",
            cookie_skin="warm-editorial",
        )
        context = skin(request)
        self.assertEqual(context["skin_css"], "css/skin-simple-blue.css")
