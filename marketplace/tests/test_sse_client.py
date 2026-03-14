from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from marketplace.models import (
    Listing,
    ListingShippingScope,
    ListingStatus,
    ListingType,
    Message,
    MessageThread,
    User,
)
from marketplace.sse_client import publish_new_message


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
        expires_at=timezone.now() + timedelta(days=7),
    )


class SSEClientPayloadTests(TestCase):
    def setUp(self):
        self.owner = _make_user("owner@sse.test", "Owner")
        self.viewer = _make_user("viewer@sse.test", "Viewer")
        self.listing = _make_supply(self.owner, "Organic wheat")
        self.thread = MessageThread.objects.create(
            listing=self.listing,
            created_by_user=self.viewer,
        )

    @patch("marketplace.sse_client.publish_event")
    @patch("marketplace.context_processors.get_unread_thread_count", return_value=4)
    def test_publish_new_message_emits_expanded_and_legacy_payload_fields(self, _unread, mock_publish):
        msg = Message.objects.create(
            thread=self.thread,
            sender=self.owner,
            body="Can deliver in two weeks.",
        )

        publish_new_message(msg)

        mock_publish.assert_called_once()
        user_id, event_type, payload = mock_publish.call_args.args
        self.assertEqual(user_id, self.viewer.pk)
        self.assertEqual(event_type, "new_message")

        # Expanded contract fields.
        self.assertEqual(payload["thread_id"], self.thread.pk)
        self.assertEqual(payload["listing_id"], self.listing.pk)
        self.assertEqual(payload["listing_type"], self.listing.type)
        self.assertEqual(payload["listing_title"], self.listing.item_text[:60])
        self.assertEqual(payload["counterparty_name"], "Owner")
        self.assertEqual(payload["sender_name"], "Owner")
        self.assertEqual(payload["message_preview"], "Owner: Can deliver in two weeks.")
        self.assertEqual(payload["timestamp"], msg.created_at.isoformat())
        self.assertEqual(payload["message_created_at"], msg.created_at.isoformat())
        self.assertEqual(payload["unread_count"], 4)
        self.assertEqual(payload["thread_unread_count"], 1)

        # Legacy compatibility fields.
        self.assertEqual(payload["message_body"], "Can deliver in two weeks.")
        self.assertEqual(payload["listing_item_text"], self.listing.item_text[:60])

    @patch("marketplace.sse_client.publish_event")
    @patch("marketplace.context_processors.get_unread_thread_count", return_value=1)
    def test_message_preview_truncates_with_sender_prefix(self, _unread, mock_publish):
        long_body = "x" * 400
        msg = Message.objects.create(
            thread=self.thread,
            sender=self.owner,
            body=long_body,
        )

        publish_new_message(msg)

        payload = mock_publish.call_args.args[2]
        self.assertTrue(payload["message_preview"].startswith("Owner: "))
        self.assertTrue(payload["message_preview"].endswith("..."))
        self.assertLessEqual(len(payload["message_preview"]), 120)
