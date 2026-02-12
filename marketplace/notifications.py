from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _


def send_match_notification(match):
    if match.notified_at is not None:
        return

    buyer = match.demand_post.created_by
    supply_lot = match.supply_lot

    location_parts = [supply_lot.location_country]
    if supply_lot.location_region:
        location_parts.append(supply_lot.location_region)
    if supply_lot.location_locality:
        location_parts.append(supply_lot.location_locality)
    location_str = ", ".join(location_parts)

    subject = _("New match for your demand: %(item)s") % {
        "item": match.demand_post.item_text,
    }
    body = _(
        "A new supply lot matches your demand \"%(demand)s\".\n\n"
        "Item: %(supply)s\n"
        "Supplier location: %(location)s\n\n"
        "Log in to view details and start a conversation."
    ) % {
        "demand": match.demand_post.item_text,
        "supply": supply_lot.item_text,
        "location": location_str,
    }

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[buyer.email],
        fail_silently=True,
    )

    match.notified_at = timezone.now()
    match.save(update_fields=["notified_at"])
