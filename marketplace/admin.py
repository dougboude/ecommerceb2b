from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    DemandPost,
    Match,
    Message,
    MessageThread,
    Organization,
    SupplyLot,
    User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "role", "country", "email_verified", "is_active")
    list_filter = ("role", "is_active", "email_verified")
    search_fields = ("email",)
    ordering = ("-date_joined",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("role", "country", "email_verified")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "role", "country")}),
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


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("id", "demand_post", "supply_lot", "created_at", "notified_at")


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "match", "buyer", "supplier")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender", "created_at")
