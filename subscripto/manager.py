from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from .bill_splitter import BillSplitter
from .models import (
    DuplicateSubscriptionError,
    Household,
    PaymentRecord,
    Subscription,
    SubscriptionStatus,
    SubscriptoError,
    UnknownUserError,
    User,
    now_utc,
)
from .renewal_alert import RenewalAlert
from .storage import StorageManager


class SubscriptionManager:
    def __init__(self, storage: StorageManager | None = None) -> None:
        self.users: dict[str, User] = {}
        self.households: dict[str, Household] = {}
        self.subscriptions: dict[str, Subscription] = {}
        self.payments: list[PaymentRecord] = []
        self.storage = storage

    def register_user(self, name: str, user_id: str | None = None) -> User:
        uid = user_id or f"user_{uuid.uuid4().hex[:8]}"
        user = User(user_id=uid, name=name)
        self.users[uid] = user
        return user

    def create_household(self, name: str, member_ids: list[str] | None = None) -> Household:
        hid = f"hh_{uuid.uuid4().hex[:8]}"
        members = list(member_ids or [])
        for mid in members:
            if mid not in self.users:
                raise UnknownUserError(f"unknown user {mid}")
        household = Household(household_id=hid, name=name, member_ids=members)
        self.households[hid] = household
        return household

    def add_subscription(
        self,
        platform: str,
        monthly_cost: Decimal,
        owner_id: str,
        renewal_at: datetime,
        household_id: str,
        split_percentages: dict[str, Decimal],
    ) -> Subscription:
        if owner_id not in self.users:
            raise UnknownUserError(f"unknown owner {owner_id}")
        if household_id not in self.households:
            raise UnknownUserError(f"unknown household {household_id}")

        for sub in self.subscriptions.values():
            if (
                sub.household_id == household_id
                and sub.platform.lower() == platform.lower()
                and sub.status == SubscriptionStatus.ACTIVE
            ):
                raise DuplicateSubscriptionError(
                    f"{platform} is already active in this household"
                )

        for uid in split_percentages:
            if uid not in self.users:
                raise UnknownUserError(f"unknown participant {uid}")

        BillSplitter.validate(split_percentages)

        sid = f"sub_{uuid.uuid4().hex[:8]}"
        sub = Subscription(
            subscription_id=sid,
            platform=platform,
            monthly_cost=monthly_cost,
            owner_id=owner_id,
            renewal_at=renewal_at,
            household_id=household_id,
            split_percentages=dict(split_percentages),
        )
        self.subscriptions[sid] = sub
        return sub

    def pause(self, subscription_id: str) -> None:
        self.subscriptions[subscription_id].set_status(SubscriptionStatus.PAUSED)

    def resume(self, subscription_id: str) -> None:
        self.subscriptions[subscription_id].set_status(SubscriptionStatus.ACTIVE)

    def cancel(self, subscription_id: str) -> None:
        self.subscriptions[subscription_id].set_status(SubscriptionStatus.CANCELLED)

    def transfer_ownership(self, subscription_id: str, new_owner_id: str) -> None:
        if new_owner_id not in self.users:
            raise UnknownUserError(f"unknown user {new_owner_id}")
        sub = self.subscriptions[subscription_id]
        sub.owner_id = new_owner_id
        sub.set_status(SubscriptionStatus.TRANSFERRED)
        sub.set_status(SubscriptionStatus.ACTIVE)

    def generate_bill_split(self, subscription_id: str) -> dict[str, Decimal]:
        sub = self.subscriptions[subscription_id]
        shares = BillSplitter.split(sub)
        record = PaymentRecord(
            subscription_id=sub.subscription_id,
            platform=sub.platform,
            paid_at=now_utc(),
            total_amount=sub.monthly_cost,
            shares=shares,
        )
        self.payments.append(record)
        return shares

    def renewal_alerts(self, reference: datetime | None = None) -> list[Subscription]:
        return RenewalAlert.upcoming(list(self.subscriptions.values()), reference)

    def dashboard(self) -> list[dict]:
        rows = []
        for sub in self.subscriptions.values():
            owner = self.users.get(sub.owner_id)
            rows.append(
                {
                    "id": sub.subscription_id,
                    "platform": sub.platform,
                    "cost": sub.monthly_cost,
                    "status": sub.status.value,
                    "owner": owner.name if owner else "?",
                    "renewal": sub.renewal_at.isoformat(),
                    "participants": list(sub.split_percentages.keys()),
                }
            )
        return rows

    def save(self) -> None:
        if not self.storage:
            raise SubscriptoError("no storage configured")
        self.storage.save(self.users, self.households, self.subscriptions, self.payments)

    def load(self) -> None:
        if not self.storage:
            raise SubscriptoError("no storage configured")
        self.users, self.households, self.subscriptions, self.payments = self.storage.load()
