from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum


class SubscriptoError(Exception):
    pass


class DuplicateSubscriptionError(SubscriptoError):
    pass


class InvalidSplitError(SubscriptoError):
    pass


class InvalidRenewalDateError(SubscriptoError):
    pass


class UnknownUserError(SubscriptoError):
    pass


class InvalidStatusTransitionError(SubscriptoError):
    pass


class SubscriptionStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    TRANSFERRED = "transferred"


_ALLOWED_TRANSITIONS = {
    SubscriptionStatus.ACTIVE: {SubscriptionStatus.PAUSED, SubscriptionStatus.CANCELLED, SubscriptionStatus.TRANSFERRED},
    SubscriptionStatus.PAUSED: {SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED, SubscriptionStatus.TRANSFERRED},
    SubscriptionStatus.TRANSFERRED: {SubscriptionStatus.ACTIVE, SubscriptionStatus.PAUSED, SubscriptionStatus.CANCELLED},
    SubscriptionStatus.CANCELLED: set(),
}


def can_transition(current: SubscriptionStatus, target: SubscriptionStatus) -> bool:
    return target in _ALLOWED_TRANSITIONS[current]


@dataclass
class User:
    user_id: str
    name: str

    def __str__(self) -> str:
        return f"{self.name} ({self.user_id})"


@dataclass
class Household:
    household_id: str
    name: str
    member_ids: list[str] = field(default_factory=list)

    def add_member(self, user_id: str) -> None:
        if user_id not in self.member_ids:
            self.member_ids.append(user_id)


@dataclass
class Subscription:
    subscription_id: str
    platform: str
    monthly_cost: Decimal
    owner_id: str
    renewal_at: datetime
    household_id: str
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    split_percentages: dict[str, Decimal] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.renewal_at.tzinfo is None:
            raise InvalidRenewalDateError("renewal_at must be timezone-aware")
        if self.monthly_cost < 0:
            raise SubscriptoError("monthly_cost cannot be negative")

    def set_status(self, new_status: SubscriptionStatus) -> None:
        if not can_transition(self.status, new_status):
            raise InvalidStatusTransitionError(
                f"cannot transition {self.status.value} -> {new_status.value}"
            )
        self.status = new_status


@dataclass
class PaymentRecord:
    subscription_id: str
    platform: str
    paid_at: datetime
    total_amount: Decimal
    shares: dict[str, Decimal]

    def to_dict(self) -> dict:
        return {
            "subscription_id": self.subscription_id,
            "platform": self.platform,
            "paid_at": self.paid_at.isoformat(),
            "total_amount": str(self.total_amount),
            "shares": {uid: str(v) for uid, v in self.shares.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PaymentRecord":
        return cls(
            subscription_id=data["subscription_id"],
            platform=data["platform"],
            paid_at=datetime.fromisoformat(data["paid_at"]),
            total_amount=Decimal(data["total_amount"]),
            shares={uid: Decimal(v) for uid, v in data["shares"].items()},
        )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
