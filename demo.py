"""End-to-end demo of the Subscripto lifecycle.

Run: python3 demo.py
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from subscripto import (
    DuplicateSubscriptionError,
    InvalidSplitError,
    StorageManager,
    SubscriptionManager,
)

DEMO_FILE = "demo_data.json"


def banner(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def main() -> None:
    storage = StorageManager(DEMO_FILE)
    mgr = SubscriptionManager(storage)

    banner("1. Register users and household")
    alice = mgr.register_user("Alice")
    bob = mgr.register_user("Bob")
    carol = mgr.register_user("Carol")
    house = mgr.create_household("Apt 4B", [alice.user_id, bob.user_id, carol.user_id])
    print(f"Household {house.name}: {[mgr.users[m].name for m in house.member_ids]}")

    banner("2. Add a Netflix subscription (renews in 23 hours)")
    renewal = datetime.now(timezone.utc) + timedelta(hours=23)
    netflix = mgr.add_subscription(
        platform="Netflix",
        monthly_cost=Decimal("15.99"),
        owner_id=alice.user_id,
        renewal_at=renewal,
        household_id=house.household_id,
        split_percentages={
            alice.user_id: Decimal("50"),
            bob.user_id: Decimal("25"),
            carol.user_id: Decimal("25"),
        },
    )
    print(f"Added {netflix.platform} ({netflix.subscription_id})")

    banner("3. Try to add duplicate Netflix -> should error")
    try:
        mgr.add_subscription(
            platform="Netflix",
            monthly_cost=Decimal("15.99"),
            owner_id=bob.user_id,
            renewal_at=renewal,
            household_id=house.household_id,
            split_percentages={bob.user_id: Decimal("100")},
        )
    except DuplicateSubscriptionError as e:
        print(f"Correctly blocked: {e}")

    banner("4. Try invalid split (90 total) -> should error")
    try:
        mgr.add_subscription(
            platform="Spotify",
            monthly_cost=Decimal("9.99"),
            owner_id=bob.user_id,
            renewal_at=renewal,
            household_id=house.household_id,
            split_percentages={
                alice.user_id: Decimal("50"),
                bob.user_id: Decimal("40"),
            },
        )
    except InvalidSplitError as e:
        print(f"Correctly blocked: {e}")

    banner("5. Add Spotify with valid 100% split")
    spotify = mgr.add_subscription(
        platform="Spotify",
        monthly_cost=Decimal("9.99"),
        owner_id=bob.user_id,
        renewal_at=datetime.now(timezone.utc) + timedelta(days=10),
        household_id=house.household_id,
        split_percentages={
            alice.user_id: Decimal("33.34"),
            bob.user_id: Decimal("33.33"),
            carol.user_id: Decimal("33.33"),
        },
    )
    print(f"Added {spotify.platform}")

    banner("6. Generate bill split for Netflix")
    shares = mgr.generate_bill_split(netflix.subscription_id)
    for uid, amt in shares.items():
        print(f"  {mgr.users[uid].name}: ${amt}")
    total = sum(shares.values())
    print(f"  TOTAL: ${total} (should equal ${netflix.monthly_cost})")

    banner("7. Pause Netflix and check dashboard")
    mgr.pause(netflix.subscription_id)
    for row in mgr.dashboard():
        print(
            f"  {row['platform']:10s} ${row['cost']}  [{row['status']}]  "
            f"owner={row['owner']}"
        )

    banner("8. Transfer Netflix ownership Alice -> Carol")
    mgr.transfer_ownership(netflix.subscription_id, carol.user_id)
    sub = mgr.subscriptions[netflix.subscription_id]
    print(
        f"  {sub.platform} owner is now {mgr.users[sub.owner_id].name}, "
        f"status={sub.status.value}"
    )

    banner("9. Renewal alerts (within next 24h)")
    alerts = mgr.renewal_alerts()
    if not alerts:
        print("  (none)")
    for a in alerts:
        print(f"  {a.platform} renews at {a.renewal_at.isoformat()}")

    banner("10. Save and reload from JSON")
    mgr.save()
    print(f"Saved to {DEMO_FILE}.")
    mgr2 = SubscriptionManager(StorageManager(DEMO_FILE))
    mgr2.load()
    print(f"Reloaded: {len(mgr2.users)} users, {len(mgr2.households)} households, "
          f"{len(mgr2.subscriptions)} subscriptions, {len(mgr2.payments)} payments.")

    banner("Demo complete")


if __name__ == "__main__":
    main()
