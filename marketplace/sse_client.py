"""
SSE relay client — talks to the SSE sidecar service over TCP.

Follows the same lazy-singleton pattern as vector_search.py but uses
regular TCP (no UDS) since the SSE service listens on a port.
"""

import hashlib
import hmac
import logging
import time

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTTP client (lazy singleton)
# ---------------------------------------------------------------------------
_client = None


def _get_client():
    global _client
    if _client is None:
        base_url = getattr(settings, "SSE_SERVICE_URL", "http://127.0.0.1:8001")
        token = getattr(settings, "SSE_SERVICE_TOKEN", "dev-token-change-me")
        _client = httpx.Client(
            base_url=base_url,
            timeout=5.0,
            headers={"x-service-token": token},
        )
    return _client


# ---------------------------------------------------------------------------
# Stream token generation (HMAC-signed for browser EventSource auth)
# ---------------------------------------------------------------------------
def generate_stream_token(user_id):
    """Generate an HMAC-signed token for browser SSE auth."""
    secret = getattr(settings, "SSE_STREAM_SECRET", "dev-stream-secret")
    timestamp = str(int(time.time()))
    message = f"{user_id}:{timestamp}"
    sig = hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return f"{timestamp}:{sig}"


# ---------------------------------------------------------------------------
# Event publishing
# ---------------------------------------------------------------------------
def publish_event(user_id, event_type, data):
    """Publish an event to the SSE sidecar. Fails silently."""
    try:
        client = _get_client()
        resp = client.post("/publish", json={
            "user_id": user_id,
            "event_type": event_type,
            "data": data,
        })
        logger.info("SSE publish to user %s: %s %s", user_id, resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("SSE publish failed for user %s: %s", user_id, exc)


def publish_new_message(message):
    """Publish a new_message event to the recipient. Fails silently."""
    try:
        thread = message.thread
        sender = message.sender

        if sender == thread.buyer:
            recipient = thread.supplier
        else:
            recipient = thread.buyer

        from .context_processors import get_unread_thread_count
        from .models import Message, ThreadReadState
        unread_count = get_unread_thread_count(recipient)

        # Per-thread unread count for the watchlist card indicator.
        try:
            rs = ThreadReadState.objects.get(thread=thread, user=recipient)
            thread_unread_count = Message.objects.filter(
                thread=thread,
                created_at__gt=rs.last_read_at,
            ).exclude(sender=recipient).count()
        except ThreadReadState.DoesNotExist:
            thread_unread_count = Message.objects.filter(
                thread=thread,
            ).exclude(sender=recipient).count()

        listing = thread.watchlist_item.supply_lot or thread.watchlist_item.demand_post

        publish_event(recipient.pk, "new_message", {
            "thread_id": thread.pk,
            "sender_name": sender.display_name or sender.email,
            "message_body": message.body,
            "message_created_at": message.created_at.isoformat(),
            "unread_count": unread_count,
            "thread_unread_count": thread_unread_count,
            "listing_item_text": listing.item_text[:60],
        })
    except Exception as exc:
        logger.warning("SSE publish_new_message failed: %s", exc)
