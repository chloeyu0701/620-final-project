from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .manager import SubscriptionManager
from .models import SubscriptoError
from .storage import StorageManager

DATA_FILE = "data.json"

MENU = """
============================
    Subscripto Main Menu
============================
1. Add Subscription
2. View Dashboard
3. Pause Subscription
4. Transfer Ownership
5. Generate Bill Split Report
6. View Renewal Alerts
7. Save and Exit
"""


def _prompt(msg: str) -> str:
    return input(msg).strip()


def _ensure_setup(mgr: SubscriptionManager) -> None:
    if mgr.users and mgr.households:
        return
    print("No data found. Let's create a household and some members.")
    hh_name = _prompt("Household name (e.g. 'Apt 4B'): ") or "My Household"
    raw = _prompt("Comma-separated member names (e.g. 'Alice,Bob'): ") or "Alice,Bob"
    members = []
    for n in [x.strip() for x in raw.split(",") if x.strip()]:
        members.append(mgr.register_user(n).user_id)
    hh = mgr.create_household(hh_name, members)
    print(f"Created household {hh.name} with {len(members)} members.")
    for uid in members:
        print(f"  {mgr.users[uid]}")


def _list_users(mgr: SubscriptionManager) -> list[str]:
    """Print numbered user list and return the ordered id list."""
    ids = list(mgr.users.keys())
    for i, uid in enumerate(ids, start=1):
        print(f"  {i}. {mgr.users[uid].name}  (id={uid})")
    return ids


def _pick_user(mgr: SubscriptionManager, prompt: str) -> str | None:
    ids = _list_users(mgr)
    raw = _prompt(f"{prompt} (row # or full id): ")
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(ids):
            return ids[idx]
        print(f"  no row {raw}.")
        return None
    if raw in mgr.users:
        return raw
    print(f"  unknown user '{raw}'.")
    return None


def _list_subs(mgr: SubscriptionManager) -> list[str]:
    """Print numbered subscription list and return the ordered id list."""
    if not mgr.subscriptions:
        print("  (no subscriptions yet)")
        return []
    ids = list(mgr.subscriptions.keys())
    print(f"  {'#':<3} {'ID':<14} {'Platform':<12} {'Cost':<8} "
          f"{'Status':<11} {'Owner':<10} Renews")
    print("  " + "-" * 78)
    for i, sid in enumerate(ids, start=1):
        s = mgr.subscriptions[sid]
        print(
            f"  {i:<3} {s.subscription_id:<14} {s.platform:<12} "
            f"${s.monthly_cost:<7} [{s.status.value:<9}] "
            f"{mgr.users[s.owner_id].name:<10} {s.renewal_at.isoformat()}"
        )
    return ids


def _pick_sub(mgr: SubscriptionManager, verb: str) -> str | None:
    """Show subs, prompt for either a row number or a full id."""
    ids = _list_subs(mgr)
    if not ids:
        return None
    raw = _prompt(f"{verb} which? (row # or full id): ")
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(ids):
            return ids[idx]
        print(f"  no row {raw}.")
        return None
    if raw in mgr.subscriptions:
        return raw
    print(f"  unknown id '{raw}'.")
    return None


def _add_subscription(mgr: SubscriptionManager) -> None:
    hh_id = next(iter(mgr.households))
    platform = _prompt("Platform (e.g. Netflix): ")
    cost = Decimal(_prompt("Monthly cost (e.g. 15.99): "))
    print("Members:")
    owner_id = _pick_user(mgr, "Owner")
    if not owner_id:
        return
    renew_raw = _prompt(
        "Renewal date (YYYY-MM-DD HH:MM, UTC, blank=24h from now): "
    )
    if renew_raw:
        renewal = datetime.strptime(renew_raw, "%Y-%m-%d %H:%M").replace(
            tzinfo=timezone.utc
        )
    else:
        from datetime import timedelta

        renewal = datetime.now(timezone.utc) + timedelta(hours=23)
    print("Enter split percentages. Must total 100.")
    splits: dict[str, Decimal] = {}
    for uid in mgr.households[hh_id].member_ids:
        val = _prompt(f"  {mgr.users[uid].name} ({uid}) [%]: ")
        splits[uid] = Decimal(val or "0")
    sub = mgr.add_subscription(
        platform, cost, owner_id, renewal, hh_id, splits
    )
    mgr.save()
    print(f"\nAdded {sub.platform} (id={sub.subscription_id}). Current list:")
    _list_subs(mgr)


def _dashboard(mgr: SubscriptionManager) -> None:
    print("\n--- Dashboard ---")
    alerts = mgr.renewal_alerts()
    if alerts:
        print("!!! Renewal alerts within 24h:")
        for a in alerts:
            print(f"    {a.platform} renews at {a.renewal_at.isoformat()}")
    _list_subs(mgr)


def _pause(mgr: SubscriptionManager) -> None:
    sid = _pick_sub(mgr, "Pause")
    if not sid:
        return
    mgr.pause(sid)
    mgr.save()
    print(f"Paused {mgr.subscriptions[sid].platform}.")


def _transfer(mgr: SubscriptionManager) -> None:
    sid = _pick_sub(mgr, "Transfer")
    if not sid:
        return
    print("Members:")
    new_owner = _pick_user(mgr, "New owner")
    if not new_owner:
        return
    mgr.transfer_ownership(sid, new_owner)
    mgr.save()
    sub = mgr.subscriptions[sid]
    print(f"Ownership of {sub.platform} transferred to {mgr.users[new_owner].name}.")


def _bill_split(mgr: SubscriptionManager) -> None:
    sid = _pick_sub(mgr, "Bill split for")
    if not sid:
        return
    shares = mgr.generate_bill_split(sid)
    mgr.save()
    sub = mgr.subscriptions[sid]
    print(f"\nBill Split for {sub.platform} (${sub.monthly_cost}):")
    for uid, amount in shares.items():
        print(f"  {mgr.users[uid].name}: ${amount}")


def _renewal_alerts(mgr: SubscriptionManager) -> None:
    alerts = mgr.renewal_alerts()
    if not alerts:
        print("No renewals within the next 24 hours.")
        return
    for a in alerts:
        print(f"  {a.platform} renews at {a.renewal_at.isoformat()}")


def run() -> None:
    storage = StorageManager(DATA_FILE)
    mgr = SubscriptionManager(storage)
    mgr.load()
    _ensure_setup(mgr)

    actions = {
        "1": _add_subscription,
        "2": _dashboard,
        "3": _pause,
        "4": _transfer,
        "5": _bill_split,
        "6": _renewal_alerts,
    }

    while True:
        print(MENU)
        choice = _prompt("Choice: ")
        if choice == "7":
            mgr.save()
            print(f"Saved to {DATA_FILE}. Goodbye.")
            return
        action = actions.get(choice)
        if not action:
            print("Invalid choice.")
            continue
        try:
            action(mgr)
        except SubscriptoError as e:
            print(f"ERROR: {e}")
        except (ValueError, InvalidOperation) as e:
            print(f"BAD INPUT: {e}")


if __name__ == "__main__":
    run()
