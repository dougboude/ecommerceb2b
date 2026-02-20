from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    DemandPost,
    DismissedSuggestion,
    Message,
    MessageThread,
    Organization,
    SupplyLot,
    User,
    WatchlistItem,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "display_name", "role", "country", "email_verified", "is_active")
    list_filter = ("role", "is_active", "email_verified")
    search_fields = ("email",)
    ordering = ("-date_joined",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("role", "country", "display_name", "email_verified", "first_name", "last_name", "timezone", "distance_unit")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "display_name", "password1", "password2", "role", "country")}),
    )


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "country", "owner")


@admin.register(DemandPost)
class DemandPostAdmin(admin.ModelAdmin):
    list_display = ("item_text", "organization", "status", "created_at")
    list_filter = ("status", "category")


@admin.register(SupplyLot)
class SupplyLotAdmin(admin.ModelAdmin):
    list_display = ("item_text", "created_by", "status", "available_until")
    list_filter = ("status", "category")


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "supply_lot", "demand_post", "status", "source", "created_at")
    list_filter = ("status", "source")


@admin.register(DismissedSuggestion)
class DismissedSuggestionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "supply_lot", "demand_post", "created_at")


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "watchlist_item", "buyer", "supplier")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender", "created_at")
