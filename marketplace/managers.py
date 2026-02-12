from django.db import models
from django.utils import timezone


class ActiveDemandPostQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        return self.filter(
            status="active",
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now),
        )


class ActiveSupplyLotQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        return self.filter(
            status="active",
            available_until__gt=now,
        )
