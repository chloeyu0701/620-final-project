from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .models import (
    Household,
    PaymentRecord,
    Subscription,
    SubscriptionStatus,
    User,
)


class StorageManager:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(
        self,
        users: dict[str, User],
        households: dict[str, Household],
        subscriptions: dict[str, Subscription],
        payments: list[PaymentRecord],
    ) -> None:
        payload = {
            "users": [
                {"user_id": u.user_id, "name": u.name} for u in users.values()
            ],
            "households": [
                {
                    "household_id": h.household_id,
                    "name": h.name,
                    "member_ids": list(h.member_ids),
                }
                for h in households.values()
            ],
            "subscriptions": [
                {
                    "subscription_id": s.subscription_id,
                    "platform": s.platform,
                    "monthly_cost": str(s.monthly_cost),
                    "owner_id": s.owner_id,
                    "renewal_at": s.renewal_at.isoformat(),
                    "household_id": s.household_id,
                    "status": s.status.value,
                    "split_percentages": {
                        uid: str(v) for uid, v in s.split_percentages.items()
                    },
                }
                for s in subscriptions.values()
            ],
            "payments": [p.to_dict() for p in payments],
        }
        self.path.write_text(json.dumps(payload, indent=2))

    def load(self) -> tuple[
        dict[str, User],
        dict[str, Household],
        dict[str, Subscription],
        list[PaymentRecord],
    ]:
        if not self.path.exists():
            return {}, {}, {}, []
        data = json.loads(self.path.read_text())

        users = {
            u["user_id"]: User(user_id=u["user_id"], name=u["name"])
            for u in data.get("users", [])
        }
        households = {
            h["household_id"]: Household(
                household_id=h["household_id"],
                name=h["name"],
                member_ids=list(h.get("member_ids", [])),
            )
            for h in data.get("households", [])
        }
        subscriptions = {}
        for s in data.get("subscriptions", []):
            sub = Subscription(
                subscription_id=s["subscription_id"],
                platform=s["platform"],
                monthly_cost=Decimal(s["monthly_cost"]),
                owner_id=s["owner_id"],
                renewal_at=datetime.fromisoformat(s["renewal_at"]),
                household_id=s["household_id"],
                status=SubscriptionStatus(s["status"]),
                split_percentages={
                    uid: Decimal(v) for uid, v in s.get("split_percentages", {}).items()
                },
            )
            subscriptions[sub.subscription_id] = sub
        payments = [PaymentRecord.from_dict(p) for p in data.get("payments", [])]
        return users, households, subscriptions, payments
