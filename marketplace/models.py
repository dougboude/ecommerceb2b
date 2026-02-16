from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from .constants import UNIT_CHOICES


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Role(models.TextChoices):
    BUYER = "buyer", _("Buyer")
    SUPPLIER = "supplier", _("Supplier")


class Category(models.TextChoices):
    FOOD_FRESH = "food_fresh", _("Food — Fresh")
    FOOD_SHELF = "food_shelf", _("Food — Shelf-stable")
    BOTANICAL = "botanical", _("Botanical")
    ANIMAL_PRODUCT = "animal_product", _("Animal product")
    MATERIAL = "material", _("Material")
    EQUIPMENT = "equipment", _("Equipment")
    OTHER = "other", _("Other")


class Frequency(models.TextChoices):
    ONE_TIME = "one_time", _("One-time")
    RECURRING = "recurring", _("Recurring")
    SEASONAL = "seasonal", _("Seasonal")


class ShippingScope(models.TextChoices):
    LOCAL_ONLY = "local_only", _("Local pickup only")
    DOMESTIC = "domestic", _("Anywhere in my country")
    NORTH_AMERICA = "north_america", _("US, Canada & Mexico")
    INTERNATIONAL = "international", _("Worldwide")


class DemandStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    PAUSED = "paused", _("Paused")
    FULFILLED = "fulfilled", _("Fulfilled")
    EXPIRED = "expired", _("Expired")


class SupplyStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    EXPIRED = "expired", _("Expired")
    WITHDRAWN = "withdrawn", _("Withdrawn")


class DistanceUnit(models.TextChoices):
    MI = "mi", _("Miles")
    KM = "km", _("Kilometers")


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(AbstractUser):
    username = None
    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(max_length=10, choices=Role.choices)
    country = models.CharField(_("country"), max_length=2)
    display_name = models.CharField(_("display name"), max_length=100, default="")
    email_verified = models.BooleanField(default=False)
    timezone = models.CharField(
        _("timezone"), max_length=63, default="UTC",
    )
    distance_unit = models.CharField(
        _("distance unit"),
        max_length=2,
        choices=DistanceUnit.choices,
        default=DistanceUnit.MI,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.display_name or self.email


# ---------------------------------------------------------------------------
# Organization (buyers only)
# ---------------------------------------------------------------------------

class Organization(models.Model):
    name = models.CharField(_("name"), max_length=255)
    type = models.CharField(_("type"), max_length=100, blank=True)
    country = models.CharField(_("country"), max_length=2)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Location mixin (shared fields for DemandPost & SupplyLot)
# ---------------------------------------------------------------------------

class LocationMixin(models.Model):
    location_country = models.CharField(_("country"), max_length=2)
    location_locality = models.CharField(_("city / town"), max_length=255, blank=True)
    location_region = models.CharField(_("state / province"), max_length=255, blank=True)
    location_postal_code = models.CharField(_("postal code"), max_length=20, blank=True)
    location_lat = models.FloatField(_("latitude"), null=True, blank=True)
    location_lng = models.FloatField(_("longitude"), null=True, blank=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# DemandPost (buyer)
# ---------------------------------------------------------------------------

class DemandPost(LocationMixin):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="demand_posts",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="demand_posts",
    )
    item_text = models.CharField(_("item description"), max_length=500)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        blank=True,
    )
    quantity_value = models.PositiveIntegerField(
        _("quantity"), null=True, blank=True,
    )
    quantity_unit = models.CharField(
        _("unit"), max_length=20, choices=UNIT_CHOICES, blank=True,
    )
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    radius_km = models.PositiveIntegerField(null=True, blank=True)
    shipping_allowed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=DemandStatus.choices,
        default=DemandStatus.ACTIVE,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.item_text


# ---------------------------------------------------------------------------
# SupplyLot (supplier)
# ---------------------------------------------------------------------------

class SupplyLot(LocationMixin):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supply_lots",
    )
    item_text = models.CharField(_("item description"), max_length=500)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        blank=True,
    )
    quantity_value = models.PositiveIntegerField(
        _("quantity"), null=True, blank=True,
    )
    quantity_unit = models.CharField(
        _("unit"), max_length=20, choices=UNIT_CHOICES, blank=True,
    )
    available_until = models.DateTimeField(_("available until"))
    shipping_scope = models.CharField(
        _("shipping scope"),
        max_length=20,
        choices=ShippingScope.choices,
        default=ShippingScope.LOCAL_ONLY,
    )
    asking_price = models.PositiveIntegerField(
        _("asking price"), null=True, blank=True,
    )
    price_unit = models.CharField(
        _("price unit"), max_length=20, choices=UNIT_CHOICES, blank=True,
    )
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=SupplyStatus.choices,
        default=SupplyStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.item_text


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------

class Match(models.Model):
    demand_post = models.ForeignKey(
        DemandPost, on_delete=models.CASCADE, related_name="matches",
    )
    supply_lot = models.ForeignKey(
        SupplyLot, on_delete=models.CASCADE, related_name="matches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("demand_post", "supply_lot")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Match #{self.pk}"


# ---------------------------------------------------------------------------
# MessageThread & Message
# ---------------------------------------------------------------------------

class MessageThread(models.Model):
    match = models.OneToOneField(
        Match, on_delete=models.CASCADE, related_name="thread",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buyer_threads",
    )
    supplier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supplier_threads",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Thread #{self.pk}"


class Message(models.Model):
    thread = models.ForeignKey(
        MessageThread, on_delete=models.CASCADE, related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message #{self.pk}"
