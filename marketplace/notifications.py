from django.core.mail import send_mail
from django.conf import settings
from django.utils.translation import gettext as _


def send_watchlist_notification(watchlist_item):
    """Send email notification when a listing is added to watchlist via suggestion."""
    listing = watchlist_item.resolve_listing() if hasattr(watchlist_item, "resolve_listing") else watchlist_item.listing
    if listing is None:
        return
    user = watchlist_item.user

    if getattr(listing, "type", None) == "supply":
        subject = _("A buyer saved your listing: %(item)s") % {
            "item": listing.item_text,
        }
        body = _(
            "Good news! A buyer has saved your supply lot \"%(item)s\" "
            "to their watchlist.\n\n"
            "Log in to view your watchlist and start a conversation."
        ) % {
            "item": listing.item_text,
        }
        recipient = listing.created_by
    else:
        subject = _("A supplier is interested in your demand: %(item)s") % {
            "item": listing.item_text,
        }
        body = _(
            "Good news! A supplier has saved your demand post \"%(item)s\" "
            "to their watchlist.\n\n"
            "Log in to view your watchlist and start a conversation."
        ) % {
            "item": listing.item_text,
        }
        recipient = listing.created_by

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient.email],
        fail_silently=True,
    )


def send_new_message_notification(message):
    """Send email notification when a new message is sent in a thread."""
    thread = message.thread
    sender = message.sender

    # Determine recipient (the other participant)
    recipient = thread.counterparty_for(sender)
    if recipient is None:
        return

    if not recipient.email_on_message:
        return

    # Determine listing text
    listing = thread.get_listing()
    if listing is None:
        return
    item_text = listing.item_text

    preview = message.body[:200]
    if len(message.body) > 200:
        preview += "..."

    sender_name = sender.display_name or sender.email

    subject = _("New message about: %(item)s") % {"item": item_text}
    body = _(
        "%(sender)s sent you a message about \"%(item)s\":\n\n"
        "%(preview)s\n\n"
        "Log in to read the full message and reply."
    ) % {
        "sender": sender_name,
        "item": item_text,
        "preview": preview,
    }

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient.email],
        fail_silently=True,
    )
