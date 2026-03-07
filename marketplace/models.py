import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext_lazy as _

from .constants import UNIT_CHOICES
from .skin_config import DEFAULT_SKIN_SLUG


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        extra_fields.pop("role", None)
        extra_fields.setdefault("skin", DEFAULT_SKIN_SLUG)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("country", "US")
        extra_fields.setdefault("email_verified", True)
        return self.create_user(email, password, **extra_fields)


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


class ListingType(models.TextChoices):
    SUPPLY = "supply", _("Supply")
    DEMAND = "demand", _("Demand")


class ListingStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    PAUSED = "paused", _("Paused")
    FULFILLED = "fulfilled", _("Fulfilled")
    WITHDRAWN = "withdrawn", _("Withdrawn")
    EXPIRED = "expired", _("Expired")
    DELETED = "deleted", _("Deleted")


class ListingShippingScope(models.TextChoices):
    LOCAL_ONLY = "local_only", _("Local pickup only")
    DOMESTIC = "domestic", _("Domestic")
    NORTH_AMERICA = "north_america", _("North America")
    WORLDWIDE = "worldwide", _("Worldwide")


class DemandStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    PAUSED = "paused", _("Paused")
    FULFILLED = "fulfilled", _("Fulfilled")
    EXPIRED = "expired", _("Expired")
    DELETED = "deleted", _("Deleted")


class SupplyStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    EXPIRED = "expired", _("Expired")
    WITHDRAWN = "withdrawn", _("Withdrawn")
    DELETED = "deleted", _("Deleted")


class WatchlistStatus(models.TextChoices):
    STARRED = "starred", _("Starred")
    WATCHING = "watching", _("Watching")
    ARCHIVED = "archived", _("Archived")


class WatchlistSource(models.TextChoices):
    SUGGESTION = "suggestion", _("Suggestion")
    SEARCH = "search", _("Search")
    DIRECT = "direct", _("Direct")


class DistanceUnit(models.TextChoices):
    MI = "mi", _("Miles")
    KM = "km", _("Kilometers")


class Skin(models.TextChoices):
    WARM_EDITORIAL = "warm-editorial", _("Warm Editorial")
    SIMPLE_BLUE = "simple-blue", _("Simple Blue")


class MigrationMode(models.TextChoices):
    LEGACY = "legacy", _("Legacy")
    COMPATIBILITY = "compatibility", _("Compatibility")
    TARGET = "target", _("Target")


class MigrationStage(models.TextChoices):
    SCHEMA = "schema", _("Schema")
    BACKFILL = "backfill", _("Backfill")
    COMPAT = "compat", _("Compatibility")
    CUTOVER = "cutover", _("Cutover")
    CLEANUP = "cleanup", _("Cleanup")


class CanonicalSource(models.TextChoices):
    LEGACY = "legacy", _("Legacy")
    TARGET = "target", _("Target")


class MigrationEntityType(models.TextChoices):
    USER = "user", _("User")
    LISTING = "listing", _("Listing")
    THREAD = "thread", _("Thread")
    WATCHLIST = "watchlist", _("Watchlist")


class BackfillAuditStatus(models.TextChoices):
    SUCCESS = "success", _("Success")
    FAILED = "failed", _("Failed")
    SKIPPED = "skipped", _("Skipped")


class User(AbstractUser):
    username = None
    email = models.EmailField(_("email address"), unique=True)
    country = models.CharField(_("country"), max_length=2)
    display_name = models.CharField(_("display name"), max_length=100, default="")
    email_verified = models.BooleanField(default=False)
    timezone = models.CharField(_("timezone"), max_length=63, default="UTC")
    distance_unit = models.CharField(
        _("distance unit"),
        max_length=2,
        choices=DistanceUnit.choices,
        default=DistanceUnit.MI,
    )
    skin = models.CharField(_("theme"), max_length=20, choices=Skin.choices)
    email_on_message = models.BooleanField(_("email me when I receive a message"), default=False)
    organization_name = models.CharField(_("organization name"), max_length=255, blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-date_joined"]

    def clean(self):
        super().clean()
        if self.organization_name is not None:
            normalized = self.organization_name.strip()
            self.organization_name = normalized or None

    def __str__(self):
        return self.display_name or self.email


class LocationMixin(models.Model):
    location_country = models.CharField(_("country"), max_length=2)
    location_locality = models.CharField(_("city / town"), max_length=255, blank=True)
    location_region = models.CharField(_("state / province"), max_length=255, blank=True)
    location_postal_code = models.CharField(_("postal code"), max_length=20, blank=True)
    location_lat = models.FloatField(_("latitude"), null=True, blank=True)
    location_lng = models.FloatField(_("longitude"), null=True, blank=True)

    class Meta:
        abstract = True


class Listing(LocationMixin):
    type = models.CharField(max_length=10, choices=ListingType.choices)
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listings",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, blank=True)
    status = models.CharField(max_length=10, choices=ListingStatus.choices, default=ListingStatus.ACTIVE)
    price_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_currency = models.CharField(max_length=3, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, blank=True)
    price_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, blank=True)
    shipping_scope = models.CharField(max_length=20, choices=ListingShippingScope.choices, blank=True)
    radius_km = models.PositiveIntegerField(null=True, blank=True)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        errors = {}
        if self.type == ListingType.SUPPLY:
            if self.radius_km is not None:
                errors["radius_km"] = _("radius_km must be null for supply listings.")
            if self.frequency:
                errors["frequency"] = _("frequency must be blank for supply listings.")
            if self.status == ListingStatus.FULFILLED:
                errors["status"] = _("FULFILLED is only valid for demand listings.")
        elif self.type == ListingType.DEMAND:
            if self.shipping_scope:
                errors["shipping_scope"] = _("shipping_scope must be blank for demand listings.")
            if self.price_unit:
                errors["price_unit"] = _("price_unit must be blank for demand listings.")
            if self.status == ListingStatus.WITHDRAWN:
                errors["status"] = _("WITHDRAWN is only valid for supply listings.")

        if errors:
            raise ValidationError(errors)

    @property
    def item_text(self):
        return self.title

    @item_text.setter
    def item_text(self, value):
        self.title = value

    @property
    def available_until(self):
        return self.expires_at if self.type == ListingType.SUPPLY else None

    @property
    def quantity_value(self):
        return self.quantity

    @property
    def quantity_unit(self):
        return self.unit

    def get_quantity_unit_display(self):
        return self.get_unit_display()

    @property
    def asking_price(self):
        return self.price_value if self.type == ListingType.SUPPLY else None

    @asking_price.setter
    def asking_price(self, value):
        self.price_value = value

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone_now()

    @property
    def shipping_allowed(self):
        return True

    @property
    def created_by(self):
        return self.created_by_user

    def __str__(self):
        return self.title


class WatchlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watchlist_items")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="watchlist_items")
    status = models.CharField(max_length=10, choices=WatchlistStatus.choices, default=WatchlistStatus.WATCHING)
    source = models.CharField(max_length=10, choices=WatchlistSource.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "listing"], name="unique_user_listing"),
        ]

    def __str__(self):
        return f"Watchlist: {self.listing}"

    @property
    def thread(self):
        return MessageThread.objects.filter(listing=self.listing, created_by_user=self.user).order_by("-created_at").first()

    def resolve_listing(self):
        return self.listing


class DismissedSuggestion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dismissed_suggestions",
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="dismissed_suggestions",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "listing"], name="unique_dismissed_listing"),
        ]


class MessageThread(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="message_threads")
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_message_threads",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "created_by_user"],
                name="unique_message_thread_per_listing_initiator",
            ),
        ]

    def get_listing(self):
        return self.listing

    def get_initiator(self):
        return self.created_by_user

    def get_owner(self):
        return self.listing.created_by_user

    def participant_ids(self):
        return {self.created_by_user_id, self.listing.created_by_user_id}

    def is_participant(self, user_id):
        return user_id in self.participant_ids()

    def counterparty_for(self, user):
        owner = self.get_owner()
        initiator = self.get_initiator()
        return owner if user.pk == initiator.pk else initiator

    def is_supply_thread(self):
        return self.listing.type == ListingType.SUPPLY

    def __str__(self):
        return f"Thread #{self.pk}"


class Message(models.Model):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message #{self.pk}"


class ThreadReadState(models.Model):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="read_states")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="thread_read_states",
    )
    last_read_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["thread", "user"], name="unique_thread_read_state"),
        ]

    def __str__(self):
        return f"ReadState thread={self.thread_id} user={self.user_id}"


class EmailVerificationToken(models.Model):
    TOKEN_EXPIRY_HOURS = 24

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_tokens",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk and not self.expires_at:
            self.expires_at = timezone_now() + timedelta(hours=self.TOKEN_EXPIRY_HOURS)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return (
            self.used_at is None
            and self.revoked_at is None
            and self.expires_at > timezone_now()
        )

    def __str__(self):
        return f"VerificationToken(user={self.user_id}, expires={self.expires_at})"


class MigrationState(models.Model):
    name = models.CharField(max_length=50, unique=True, default="default")
    mode = models.CharField(max_length=20, choices=MigrationMode.choices, default=MigrationMode.LEGACY)
    stage = models.CharField(max_length=20, choices=MigrationStage.choices, default=MigrationStage.SCHEMA)
    checkpoint = models.CharField(max_length=10, default="CP0")
    checkpoint_order = models.PositiveSmallIntegerField(default=0)
    dual_write_enabled = models.BooleanField(default=False)
    dual_read_enabled = models.BooleanField(default=False)
    read_canonical = models.CharField(max_length=10, choices=CanonicalSource.choices, default=CanonicalSource.LEGACY)
    write_canonical = models.CharField(max_length=10, choices=CanonicalSource.choices, default=CanonicalSource.LEGACY)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(checkpoint_order__gte=0, checkpoint_order__lte=5),
                name="migration_state_checkpoint_order_bounds",
            ),
        ]

    def __str__(self):
        return f"MigrationState({self.name} mode={self.mode} checkpoint={self.checkpoint})"


class LegacyToTargetMapping(models.Model):
    entity_type = models.CharField(max_length=20, choices=MigrationEntityType.choices)
    legacy_pk = models.PositiveIntegerField()
    target_pk = models.PositiveIntegerField()
    mapping_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entity_type", "legacy_pk"], name="unique_legacy_to_target_mapping"),
        ]

    def __str__(self):
        return f"Mapping({self.entity_type}:{self.legacy_pk}->{self.target_pk})"


class BackfillAuditRecord(models.Model):
    entity_type = models.CharField(max_length=20, choices=MigrationEntityType.choices)
    source_pk = models.PositiveIntegerField()
    target_pk = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=BackfillAuditStatus.choices)
    reason_code = models.CharField(max_length=100, blank=True, null=True)
    details = models.JSONField(default=dict, blank=True)
    migrated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["entity_type", "source_pk"]),
            models.Index(fields=["status", "migrated_at"]),
        ]

    def __str__(self):
        return f"BackfillAuditRecord({self.entity_type}:{self.source_pk} status={self.status})"


class ParityReport(models.Model):
    stage = models.CharField(max_length=20, choices=MigrationStage.choices)
    scope = models.CharField(max_length=100)
    passed = models.BooleanField(default=False)
    total_checked = models.PositiveIntegerField(default=0)
    failures = models.PositiveIntegerField(default=0)
    failure_summary = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["stage", "scope", "generated_at"]),
            models.Index(fields=["passed", "generated_at"]),
        ]

    def __str__(self):
        return f"ParityReport(stage={self.stage} scope={self.scope} passed={self.passed})"
