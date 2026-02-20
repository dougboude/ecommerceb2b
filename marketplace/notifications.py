from django.core.mail import send_mail
from django.conf import settings
from django.utils.translation import gettext as _


def send_watchlist_notification(watchlist_item):
    """Send email notification when a listing is added to watchlist via suggestion."""
    listing = watchlist_item.listing
    user = watchlist_item.user

    if watchlist_item.supply_lot:
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
