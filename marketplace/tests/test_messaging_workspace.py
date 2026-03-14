from datetime import timedelta

from django.test import TestCase, override_settings, tag
from django.urls import reverse
from django.utils import timezone

from marketplace.models import (
    Listing,
    ListingShippingScope,
    ListingStatus,
    ListingType,
    Message,
    MessageThread,
    ThreadReadState,
    User,
)


_STATIC_TEST_SETTINGS = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def _make_user(email, name):
    return User.objects.create_user(
        email=email,
        password="testpass123",
        country="US",
        display_name=name,
    )


def _make_supply(owner, title):
    return Listing.objects.create(
        type=ListingType.SUPPLY,
        created_by_user=owner,
        title=title,
        status=ListingStatus.ACTIVE,
        location_country="US",
        shipping_scope=ListingShippingScope.DOMESTIC,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=10),
    )


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
@tag("messaging_workspace")
class MessagingWorkspaceTests(TestCase):
    def setUp(self):
        self.owner = _make_user("owner@msg.test", "Owner")
        self.viewer = _make_user("viewer@msg.test", "Viewer")
        self.client.force_login(self.viewer)

    def _make_thread_with_message(self, listing, body, created_at):
        thread = MessageThread.objects.create(
            listing=listing,
            created_by_user=self.viewer,
        )
        msg = Message.objects.create(
            thread=thread,
            sender=self.owner,
            body=body,
        )
        Message.objects.filter(pk=msg.pk).update(created_at=created_at)
        return thread

    def test_inbox_orders_threads_by_recent_activity_and_marks_unread(self):
        older_listing = _make_supply(self.owner, "Older listing")
        newer_listing = _make_supply(self.owner, "Newer listing")
        older_thread = self._make_thread_with_message(
            older_listing,
            "older message",
            timezone.now() - timedelta(days=1),
        )
        newer_thread = self._make_thread_with_message(
            newer_listing,
            "newer message",
            timezone.now() - timedelta(hours=1),
        )

        response = self.client.get(reverse("marketplace:inbox"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        first_pos = html.find(f'data-thread-id="{newer_thread.pk}"')
        second_pos = html.find(f'data-thread-id="{older_thread.pk}"')
        self.assertTrue(0 <= first_pos < second_pos)
        self.assertContains(response, "conversations,")
        self.assertContains(response, "unread.")
        self.assertContains(response, 'class="messages-workspace"')
        self.assertContains(response, 'id="messages-thread-pane"')
        self.assertContains(response, "data-thread-fragment-url")

    def test_thread_context_shows_counterparty_and_listing_link(self):
        listing = _make_supply(self.owner, "Context listing")
        thread = self._make_thread_with_message(
            listing,
            "hello context",
            timezone.now() - timedelta(minutes=5),
        )

        response = self.client.get(reverse("marketplace:thread_detail", kwargs={"pk": thread.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "listing-owner")
        self.assertContains(response, "About:")
        self.assertContains(response, "Supply listing")
        self.assertContains(response, reverse("marketplace:supply_lot_detail", kwargs={"pk": listing.pk}))
        self.assertContains(response, "Back to messages")
        self.assertContains(response, "Back to listing")
        self.assertContains(response, 'name="body"')
        self.assertContains(response, 'rows="5"')
        self.assertContains(response, 'name="enter_to_send"')

    def test_enter_to_send_preference_persists_on_post(self):
        listing = _make_supply(self.owner, "Preference listing")
        thread = self._make_thread_with_message(
            listing,
            "pref seed",
            timezone.now() - timedelta(minutes=5),
        )

        response = self.client.post(
            reverse("marketplace:thread_detail", kwargs={"pk": thread.pk}),
            {"body": "toggle pref", "enter_to_send": "on"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.viewer.refresh_from_db()
        self.assertTrue(self.viewer.enter_to_send)
        self.assertContains(response, 'name="enter_to_send"')
        self.assertContains(response, "checked")

    def test_opening_thread_updates_read_state(self):
        listing = _make_supply(self.owner, "Read-state listing")
        thread = self._make_thread_with_message(
            listing,
            "unread now",
            timezone.now() - timedelta(minutes=2),
        )

        # Before opening, should appear unread in inbox.
        inbox_before = self.client.get(reverse("marketplace:inbox"))
        self.assertContains(inbox_before, f'data-thread-id="{thread.pk}"')
        self.assertContains(inbox_before, "New")

        # Open thread to mark read.
        response = self.client.get(reverse("marketplace:thread_detail", kwargs={"pk": thread.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ThreadReadState.objects.filter(thread=thread, user=self.viewer).exists()
        )

        # After opening, unread badge should clear on fresh inbox load.
        inbox_after = self.client.get(reverse("marketplace:inbox"))
        row_marker = f'data-thread-id="{thread.pk}"'
        html = inbox_after.content.decode("utf-8")
        row_start = html.find(row_marker)
        self.assertNotEqual(row_start, -1)
        row_slice = html[row_start: row_start + 600]
        self.assertNotIn("New", row_slice)

    def test_sending_message_keeps_thread_context_visible(self):
        listing = _make_supply(self.owner, "Compose listing")
        thread = self._make_thread_with_message(
            listing,
            "owner message",
            timezone.now() - timedelta(minutes=15),
        )

        response = self.client.post(
            reverse("marketplace:thread_detail", kwargs={"pk": thread.pk}),
            {"body": "viewer reply"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "listing-owner")
        self.assertContains(response, "About:")
        self.assertContains(response, "Back to messages")
        self.assertContains(response, "viewer reply")

    def test_inbox_thread_query_renders_selected_thread_in_workspace_pane(self):
        listing = _make_supply(self.owner, "Workspace selection listing")
        thread = self._make_thread_with_message(
            listing,
            "workspace hello",
            timezone.now() - timedelta(minutes=10),
        )

        response = self.client.get(reverse("marketplace:inbox"), {"thread": thread.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "thread-pane-content")
        self.assertContains(response, 'data-thread-id="%s"' % thread.pk)
        self.assertContains(response, "workspace-thread-link--active")

    def test_thread_fragment_requires_hx_request_header(self):
        listing = _make_supply(self.owner, "Fragment fallback listing")
        thread = self._make_thread_with_message(
            listing,
            "fragment hello",
            timezone.now() - timedelta(minutes=9),
        )

        response = self.client.get(reverse("marketplace:thread_fragment", kwargs={"pk": thread.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("marketplace:thread_detail", kwargs={"pk": thread.pk}), response["Location"])

    def test_thread_fragment_returns_partial_for_hx_request(self):
        listing = _make_supply(self.owner, "Fragment listing")
        thread = self._make_thread_with_message(
            listing,
            "fragment content",
            timezone.now() - timedelta(minutes=8),
        )

        response = self.client.get(
            reverse("marketplace:thread_fragment", kwargs={"pk": thread.pk}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("thread-pane-content", html)
        self.assertIn('data-thread-id="%s"' % thread.pk, html)
        self.assertNotIn("<nav", html.lower())
