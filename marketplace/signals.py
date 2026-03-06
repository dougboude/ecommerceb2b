from django.db.models.signals import post_save
from django.dispatch import receiver

from marketplace.migration_control.compatibility import CompatibilityRepository
from marketplace.models import DemandPost, MessageThread, SupplyLot, WatchlistItem

repo = CompatibilityRepository()


@receiver(post_save, sender=DemandPost)
def sync_demand_post_shadow(sender, instance, **kwargs):
    repo.sync_listing_shadow(instance)


@receiver(post_save, sender=SupplyLot)
def sync_supply_lot_shadow(sender, instance, **kwargs):
    repo.sync_listing_shadow(instance)


@receiver(post_save, sender=WatchlistItem)
def sync_watchlist_shadow(sender, instance, **kwargs):
    repo.sync_watchlist_shadow(instance)


@receiver(post_save, sender=MessageThread)
def sync_thread_shadow(sender, instance, **kwargs):
    repo.sync_thread_shadow(instance)
