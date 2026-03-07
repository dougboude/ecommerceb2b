from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Listing,
    DismissedSuggestion,
    Message,
    MessageThread,
    ThreadReadState,
    User,
    WatchlistItem,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "display_name", "organization_name", "country", "email_verified", "is_active")
    list_filter = ("is_active", "email_verified")
    search_fields = ("email",)
    ordering = ("-date_joined",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Profile",
            {
                "fields": (
                    "organization_name",
                    "country",
                    "display_name",
                    "email_verified",
                    "first_name",
                    "last_name",
                    "timezone",
                    "distance_unit",
                ),
            },
        ),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "display_name", "organization_name", "password1", "password2", "country"),
            },
        ),
    )


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "title", "status", "created_by_user", "created_at")
    list_filter = ("status", "category")


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "listing", "status", "source", "created_at")
    list_filter = ("status", "source")


@admin.register(DismissedSuggestion)
class DismissedSuggestionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "listing", "created_at")


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "created_by_user", "created_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender", "created_at")


@admin.register(ThreadReadState)
class ThreadReadStateAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "user", "last_read_at")
    raw_id_fields = ("thread", "user")
