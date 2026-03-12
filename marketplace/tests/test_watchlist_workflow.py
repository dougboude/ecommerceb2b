from datetime import timedelta

from django.test import TestCase, override_settings, tag
from django.urls import reverse
from django.utils import timezone

from marketplace.models import (
    Listing,
    ListingShippingScope,
    ListingStatus,
    ListingType,
    Message,
    MessageThread,
    User,
    WatchlistItem,
    WatchlistSource,
    WatchlistStatus,
)


_STATIC_TEST_SETTINGS = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def _make_user(email, name):
    return User.objects.create_user(
        email=email,
        password="testpass123",
        country="US",
        display_name=name,
    )


def _make_supply(owner, title):
    return Listing.objects.create(
        type=ListingType.SUPPLY,
        created_by_user=owner,
        title=title,
        status=ListingStatus.ACTIVE,
        location_country="US",
        shipping_scope=ListingShippingScope.DOMESTIC,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=14),
    )


@override_settings(STORAGES=_STATIC_TEST_SETTINGS)
@tag("watchlist_workflow")
class WatchlistWorkflowTests(TestCase):
    def setUp(self):
        self.owner = _make_user("owner@watch.test", "Owner")
        self.user = _make_user("user@watch.test", "Watcher")
        self.client.force_login(self.user)

    def test_watchlist_separates_starred_watching_and_archived(self):
        a = _make_supply(self.owner, "Starred listing")
        b = _make_supply(self.owner, "Watching listing")
        c = _make_supply(self.owner, "Archived listing")
        WatchlistItem.objects.create(user=self.user, listing=a, source=WatchlistSource.DIRECT, status=WatchlistStatus.STARRED)
        WatchlistItem.objects.create(user=self.user, listing=b, source=WatchlistSource.DIRECT, status=WatchlistStatus.WATCHING)
        WatchlistItem.objects.create(user=self.user, listing=c, source=WatchlistSource.DIRECT, status=WatchlistStatus.ARCHIVED)

        response = self.client.get(reverse("marketplace:watchlist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Starred (1)")
        self.assertContains(response, "Watching (1)")
        self.assertContains(response, "Archived (1)")
        self.assertContains(response, "active items")

    def test_empty_active_watchlist_has_discover_cta(self):
        archived_listing = _make_supply(self.owner, "Archived only")
        WatchlistItem.objects.create(
            user=self.user,
            listing=archived_listing,
            source=WatchlistSource.DIRECT,
            status=WatchlistStatus.ARCHIVED,
        )

        response = self.client.get(reverse("marketplace:watchlist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items being watched.")
        self.assertContains(response, "Discover listings")
        self.assertContains(response, reverse("marketplace:discover"))

    def test_watchlist_message_starts_thread_and_shows_open_conversation(self):
        listing = _make_supply(self.owner, "Conversation target")
        item = WatchlistItem.objects.create(
            user=self.user,
            listing=listing,
            source=WatchlistSource.DIRECT,
            status=WatchlistStatus.WATCHING,
        )

        response = self.client.post(
            reverse("marketplace:watchlist_message", kwargs={"pk": item.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        thread = MessageThread.objects.get(listing=listing, created_by_user=self.user)
        self.assertContains(response, "Back to messages")

        # After thread exists, watchlist card should expose direct open action.
        watchlist_response = self.client.get(reverse("marketplace:watchlist"))
        self.assertEqual(watchlist_response.status_code, 200)
        self.assertContains(watchlist_response, reverse("marketplace:thread_detail", kwargs={"pk": thread.pk}))
        self.assertContains(watchlist_response, "Open conversation")

    def test_archive_and_restore_transitions(self):
        listing = _make_supply(self.owner, "Archive flow")
        item = WatchlistItem.objects.create(
            user=self.user,
            listing=listing,
            source=WatchlistSource.DIRECT,
            status=WatchlistStatus.WATCHING,
        )

        archive_response = self.client.post(
            reverse("marketplace:watchlist_archive", kwargs={"pk": item.pk}),
            follow=True,
        )
        self.assertEqual(archive_response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, WatchlistStatus.ARCHIVED)
        self.assertContains(archive_response, "Watchlist item archived.")

        restore_response = self.client.post(
            reverse("marketplace:watchlist_unarchive", kwargs={"pk": item.pk}),
            follow=True,
        )
        self.assertEqual(restore_response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, WatchlistStatus.WATCHING)
        self.assertContains(restore_response, "Watchlist item restored to watching.")

    def test_watchlist_summary_counts_unread_conversations(self):
        listing = _make_supply(self.owner, "Unread summary")
        item = WatchlistItem.objects.create(
            user=self.user,
            listing=listing,
            source=WatchlistSource.DIRECT,
            status=WatchlistStatus.WATCHING,
        )
        thread = MessageThread.objects.create(listing=listing, created_by_user=self.user)
        Message.objects.create(thread=thread, sender=self.owner, body="ping")

        response = self.client.get(reverse("marketplace:watchlist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "in conversation")
        self.assertContains(response, "with unread messages")
