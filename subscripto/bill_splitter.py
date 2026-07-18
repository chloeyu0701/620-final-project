from decimal import Decimal, ROUND_HALF_UP

from .models import InvalidSplitError, Subscription


class BillSplitter:
    @staticmethod
    def validate(percentages: dict[str, Decimal]) -> None:
        if not percentages:
            raise InvalidSplitError("no participants provided")
        for uid, pct in percentages.items():
            if pct < 0:
                raise InvalidSplitError(f"negative percentage for {uid}")
        total = sum(percentages.values(), Decimal("0"))
        if total != Decimal("100"):
            raise InvalidSplitError(f"percentages must total 100, got {total}")

    @staticmethod
    def split(subscription: Subscription) -> dict[str, Decimal]:
        percentages = subscription.split_percentages
        BillSplitter.validate(percentages)
        cost = subscription.monthly_cost
        cents_total = (cost * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        shares_cents: dict[str, Decimal] = {}
        running = Decimal("0")
        items = list(percentages.items())
        for uid, pct in items[:-1]:
            share = (cents_total * pct / Decimal("100")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            shares_cents[uid] = share
            running += share
        last_uid = items[-1][0]
        shares_cents[last_uid] = cents_total - running

        return {
            uid: (v / Decimal("100")).quantize(Decimal("0.01"))
            for uid, v in shares_cents.items()
        }
