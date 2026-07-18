from datetime import datetime, timedelta

from .models import Subscription, SubscriptionStatus, now_utc


class RenewalAlert:
    WINDOW = timedelta(hours=24)

    @classmethod
    def upcoming(
        cls, subscriptions: list[Subscription], reference: datetime | None = None
    ) -> list[Subscription]:
        ref = reference or now_utc()
        due = []
        for sub in subscriptions:
            if sub.status != SubscriptionStatus.ACTIVE:
                continue
            delta = sub.renewal_at - ref
            if timedelta(0) <= delta <= cls.WINDOW:
                due.append(sub)
        return due
