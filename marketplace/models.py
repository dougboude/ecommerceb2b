from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from .constants import UNIT_CHOICES
from .skin_config import DEFAULT_SKIN_SLUG


# ---------------------------------------------------------------------------
# Custom User Manager (email-based auth)
# ---------------------------------------------------------------------------

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        extra_fields.setdefault("skin", DEFAULT_SKIN_SLUG)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "supplier")
        extra_fields.setdefault("country", "US")
        return self.create_user(email, password, **extra_fields)


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
    skin = models.CharField(
        _("theme"),
        max_length=20,
        choices=Skin.choices,
    )
    email_on_message = models.BooleanField(
        _("email me when I receive a message"), default=False,
    )
    organization_name = models.CharField(
        _("organization name"),
        max_length=255,
        blank=True,
        null=True,
    )

    objects = UserManager()

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
# Unified target Listing (additive schema for migration)
# ---------------------------------------------------------------------------

class Listing(LocationMixin):
    type = models.CharField(max_length=10, choices=ListingType.choices)
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="target_listings",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, blank=True)
    status = models.CharField(
        max_length=10,
        choices=ListingStatus.choices,
        default=ListingStatus.ACTIVE,
    )
    price_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_currency = models.CharField(max_length=3, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, blank=True)
    price_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, blank=True)
    shipping_scope = models.CharField(
        max_length=20,
        choices=ListingShippingScope.choices,
        blank=True,
    )
    radius_km = models.PositiveIntegerField(null=True, blank=True)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    legacy_source_type = models.CharField(max_length=20, blank=True)
    legacy_source_pk = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["legacy_source_type", "legacy_source_pk"],
                condition=models.Q(legacy_source_type__gt="", legacy_source_pk__isnull=False),
                name="unique_listing_legacy_source",
            ),
        ]

    def __str__(self):
        return self.title


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
# WatchlistItem
# ---------------------------------------------------------------------------

class WatchlistItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
    )
    supply_lot = models.ForeignKey(
        SupplyLot, on_delete=models.CASCADE, related_name="watchlist_items",
        null=True, blank=True,
    )
    demand_post = models.ForeignKey(
        DemandPost, on_delete=models.CASCADE, related_name="watchlist_items",
        null=True, blank=True,
    )
    status = models.CharField(
        max_length=10, choices=WatchlistStatus.choices,
        default=WatchlistStatus.WATCHING,
    )
    source = models.CharField(
        max_length=10, choices=WatchlistSource.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(supply_lot__isnull=False, demand_post__isnull=True)
                    | models.Q(supply_lot__isnull=True, demand_post__isnull=False)
                ),
                name="watchlist_exactly_one_listing",
            ),
            models.UniqueConstraint(
                fields=["user", "supply_lot"],
                condition=models.Q(supply_lot__isnull=False),
                name="unique_user_supply_lot",
            ),
            models.UniqueConstraint(
                fields=["user", "demand_post"],
                condition=models.Q(demand_post__isnull=False),
                name="unique_user_demand_post",
            ),
        ]

    def __str__(self):
        listing = self.supply_lot or self.demand_post
        return f"Watchlist: {listing}"

    @property
    def listing(self):
        return self.supply_lot or self.demand_post


# ---------------------------------------------------------------------------
# DismissedSuggestion
# ---------------------------------------------------------------------------

class DismissedSuggestion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dismissed_suggestions",
    )
    supply_lot = models.ForeignKey(
        SupplyLot, on_delete=models.CASCADE,
        null=True, blank=True,
    )
    demand_post = models.ForeignKey(
        DemandPost, on_delete=models.CASCADE,
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(supply_lot__isnull=False, demand_post__isnull=True)
                    | models.Q(supply_lot__isnull=True, demand_post__isnull=False)
                ),
                name="dismissed_exactly_one_listing",
            ),
            models.UniqueConstraint(
                fields=["user", "supply_lot"],
                condition=models.Q(supply_lot__isnull=False),
                name="unique_dismissed_supply_lot",
            ),
            models.UniqueConstraint(
                fields=["user", "demand_post"],
                condition=models.Q(demand_post__isnull=False),
                name="unique_dismissed_demand_post",
            ),
        ]


# ---------------------------------------------------------------------------
# MessageThread & Message
# ---------------------------------------------------------------------------

class MessageThread(models.Model):
    watchlist_item = models.OneToOneField(
        WatchlistItem, on_delete=models.CASCADE, related_name="thread",
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


# ---------------------------------------------------------------------------
# ThreadReadState (per-user read tracking)
# ---------------------------------------------------------------------------

class ThreadReadState(models.Model):
    thread = models.ForeignKey(
        MessageThread, on_delete=models.CASCADE, related_name="read_states",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="thread_read_states",
    )
    last_read_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "user"],
                name="unique_thread_read_state",
            ),
        ]

    def __str__(self):
        return f"ReadState thread={self.thread_id} user={self.user_id}"


# ---------------------------------------------------------------------------
# Migration control-plane persistence models
# ---------------------------------------------------------------------------

class MigrationState(models.Model):
    """
    Persisted migration control state so deploy/restart remains checkpoint-safe.
    """

    name = models.CharField(max_length=50, unique=True, default="default")
    mode = models.CharField(
        max_length=20,
        choices=MigrationMode.choices,
        default=MigrationMode.LEGACY,
    )
    stage = models.CharField(
        max_length=20,
        choices=MigrationStage.choices,
        default=MigrationStage.SCHEMA,
    )
    checkpoint = models.CharField(max_length=10, default="CP0")
    checkpoint_order = models.PositiveSmallIntegerField(default=0)
    dual_write_enabled = models.BooleanField(default=False)
    dual_read_enabled = models.BooleanField(default=False)
    read_canonical = models.CharField(
        max_length=10,
        choices=CanonicalSource.choices,
        default=CanonicalSource.LEGACY,
    )
    write_canonical = models.CharField(
        max_length=10,
        choices=CanonicalSource.choices,
        default=CanonicalSource.LEGACY,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(checkpoint_order__gte=0, checkpoint_order__lte=5),
                name="migration_state_checkpoint_order_bounds",
            ),
        ]

    def __str__(self):
        return (
            f"MigrationState({self.name} "
            f"mode={self.mode} checkpoint={self.checkpoint})"
        )


class LegacyToTargetMapping(models.Model):
    entity_type = models.CharField(
        max_length=20,
        choices=MigrationEntityType.choices,
    )
    legacy_pk = models.PositiveIntegerField()
    target_pk = models.PositiveIntegerField()
    mapping_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity_type", "legacy_pk"],
                name="unique_legacy_to_target_mapping",
            ),
        ]

    def __str__(self):
        return f"Mapping({self.entity_type}:{self.legacy_pk}->{self.target_pk})"


class BackfillAuditRecord(models.Model):
    entity_type = models.CharField(
        max_length=20,
        choices=MigrationEntityType.choices,
    )
    source_pk = models.PositiveIntegerField()
    target_pk = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=BackfillAuditStatus.choices,
    )
    reason_code = models.CharField(max_length=100, blank=True, null=True)
    details = models.JSONField(default=dict, blank=True)
    migrated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["entity_type", "source_pk"]),
            models.Index(fields=["status", "migrated_at"]),
        ]

    def __str__(self):
        return (
            f"BackfillAuditRecord({self.entity_type}:{self.source_pk} "
            f"status={self.status})"
        )


class ParityReport(models.Model):
    stage = models.CharField(
        max_length=20,
        choices=MigrationStage.choices,
    )
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
        return (
            f"ParityReport(stage={self.stage} scope={self.scope} "
            f"passed={self.passed})"
        )


class ListingWatchlistItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="target_watchlist_items",
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="target_watchlist_items",
    )
    status = models.CharField(
        max_length=10,
        choices=WatchlistStatus.choices,
        default=WatchlistStatus.WATCHING,
    )
    source = models.CharField(max_length=10, choices=WatchlistSource.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "listing"],
                name="unique_user_target_listing_watchlist",
            ),
        ]
        ordering = ["-updated_at"]


class ListingMessageThread(models.Model):
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="target_threads",
    )
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="target_created_threads",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "created_by_user"],
                name="unique_target_thread_per_listing_initiator",
            ),
        ]

    def __str__(self):
        return f"TargetThread listing={self.listing_id} initiator={self.created_by_user_id}"
