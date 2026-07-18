import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from subscripto import (
    DuplicateSubscriptionError,
    InvalidRenewalDateError,
    InvalidSplitError,
    StorageManager,
    SubscriptionManager,
    SubscriptionStatus,
)


def _future(hours: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


class SubscriptoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mgr = SubscriptionManager()
        self.alice = self.mgr.register_user("Alice")
        self.bob = self.mgr.register_user("Bob")
        self.house = self.mgr.create_household(
            "House", [self.alice.user_id, self.bob.user_id]
        )

    def _add(self, platform="Netflix", cost="10.00", renew_hours=48):
        return self.mgr.add_subscription(
            platform=platform,
            monthly_cost=Decimal(cost),
            owner_id=self.alice.user_id,
            renewal_at=_future(renew_hours),
            household_id=self.house.household_id,
            split_percentages={
                self.alice.user_id: Decimal("50"),
                self.bob.user_id: Decimal("50"),
            },
        )

    # 1. add new subscription
    def test_add_new_subscription(self):
        sub = self._add()
        self.assertEqual(sub.platform, "Netflix")
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)
        self.assertIn(sub.subscription_id, self.mgr.subscriptions)

    # 2. duplicate platform
    def test_add_duplicate_raises(self):
        self._add()
        with self.assertRaises(DuplicateSubscriptionError):
            self._add()

    # 3. split with total 100
    def test_split_100_percent_computes(self):
        sub = self._add(cost="10.00")
        shares = self.mgr.generate_bill_split(sub.subscription_id)
        self.assertEqual(shares[self.alice.user_id], Decimal("5.00"))
        self.assertEqual(shares[self.bob.user_id], Decimal("5.00"))

    # 4. split not 100
    def test_split_bad_total_raises(self):
        with self.assertRaises(InvalidSplitError):
            self.mgr.add_subscription(
                platform="Hulu",
                monthly_cost=Decimal("10"),
                owner_id=self.alice.user_id,
                renewal_at=_future(48),
                household_id=self.house.household_id,
                split_percentages={
                    self.alice.user_id: Decimal("40"),
                    self.bob.user_id: Decimal("40"),
                },
            )

    # 5. renewal due within 24h
    def test_renewal_within_24h(self):
        self._add(platform="Netflix", renew_hours=23)
        self._add(platform="Spotify", renew_hours=48)
        alerts = self.mgr.renewal_alerts()
        platforms = {a.platform for a in alerts}
        self.assertIn("Netflix", platforms)
        self.assertNotIn("Spotify", platforms)

    # 6. invalid renewal date (naive datetime)
    def test_invalid_renewal_date_raises(self):
        with self.assertRaises(InvalidRenewalDateError):
            self.mgr.add_subscription(
                platform="Hulu",
                monthly_cost=Decimal("10"),
                owner_id=self.alice.user_id,
                renewal_at=datetime(2099, 1, 1),  # naive, no tz
                household_id=self.house.household_id,
                split_percentages={
                    self.alice.user_id: Decimal("50"),
                    self.bob.user_id: Decimal("50"),
                },
            )

    # 7. transfer ownership
    def test_transfer_ownership(self):
        sub = self._add()
        self.mgr.transfer_ownership(sub.subscription_id, self.bob.user_id)
        self.assertEqual(sub.owner_id, self.bob.user_id)
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)

    # 8. save + reload JSON
    def test_save_and_reload_json(self):
        self._add(platform="Netflix")
        self._add(platform="Spotify")

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.mgr.storage = StorageManager(path)
            self.mgr.save()

            fresh = SubscriptionManager(StorageManager(path))
            fresh.load()

            self.assertEqual(len(fresh.users), 2)
            self.assertEqual(len(fresh.households), 1)
            self.assertEqual(len(fresh.subscriptions), 2)
            platforms = {s.platform for s in fresh.subscriptions.values()}
            self.assertEqual(platforms, {"Netflix", "Spotify"})
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
