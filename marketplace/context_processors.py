from django.conf import settings as django_settings
from django.db.models import F, Q, Subquery, OuterRef

from .models import Message, MessageThread, Skin, ThreadReadState
from .skin_config import DEFAULT_SKIN_SLUG


SKIN_COOKIE_NAME = "marketplace_skin"
_ALLOWED_SKINS = {value for value, _label in Skin.choices}


def _resolve_skin_name(candidate):
    if candidate in _ALLOWED_SKINS:
        return candidate
    return DEFAULT_SKIN_SLUG


def skin(request):
    if hasattr(request, "user") and request.user.is_authenticated:
        skin_name = _resolve_skin_name(request.user.skin)
    else:
        skin_name = _resolve_skin_name(request.COOKIES.get(SKIN_COOKIE_NAME))
    return {"skin_css": f"css/skin-{skin_name}.css"}


def nav_section(request):
    """Provide the current nav section name based on the URL path."""
    path = request.path
    if path == "/":
        return {"nav_section": "dashboard"}
    prefix_map = [
        ("/messages", "messages"),
        ("/discover", "discover"),
        ("/watchlist", "watchlist"),
        ("/profile", "profile"),
        ("/demands", "listings"),
        ("/supply", "listings"),
        ("/threads", "messages"),
    ]
    for prefix, section in prefix_map:
        if path.startswith(prefix):
            return {"nav_section": section}
    return {"nav_section": ""}


def get_unread_thread_count(user):
    """Count threads with unread messages for a given user (reusable helper)."""
    read_at_sq = ThreadReadState.objects.filter(
        thread=OuterRef("pk"), user=user,
    ).values("last_read_at")[:1]

    last_other_msg_sq = Message.objects.filter(
        thread=OuterRef("pk"),
    ).exclude(
        sender=user,
    ).order_by("-created_at").values("created_at")[:1]

    return MessageThread.objects.filter(
        Q(created_by_user=user)
        | Q(listing__created_by_user=user),
    ).annotate(
        last_other_message_at=Subquery(last_other_msg_sq),
        user_read_at=Subquery(read_at_sq),
    ).filter(
        last_other_message_at__isnull=False,
    ).filter(
        Q(user_read_at__isnull=True)
        | Q(last_other_message_at__gt=F("user_read_at")),
    ).count()


def unread_thread_count(request):
    """Context processor: count threads with unread messages."""
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {"unread_thread_count": 0}
    return {"unread_thread_count": get_unread_thread_count(request.user)}


def sse_stream(request):
    """Context processor: provide SSE stream URL for authenticated users."""
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {}
    from .sse_client import generate_stream_token
    token = generate_stream_token(request.user.pk)
    base_url = getattr(django_settings, "SSE_SERVICE_URL", "http://127.0.0.1:8001")
    return {
        "sse_stream_url": f"{base_url}/stream/{request.user.pk}?token={token}",
    }
