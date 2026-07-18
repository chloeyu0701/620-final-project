# Subscripto

Subscription Lifecycle Management and Shared Bill Splitting System.
A Python MVP for CS625 Object Oriented Software final project.

## Requirements
- Python 3.10+ (standard library only)

## Run the interactive menu
```
python3 -m subscripto
```
First launch will prompt you to name a household and its members.
Data is saved to `data.json` in the working directory on exit.

## Run the end-to-end demo
```
python3 demo.py
```
Prints a full lifecycle: register users -> add subscription -> duplicate
error -> invalid split error -> valid split -> bill split -> pause ->
transfer ownership -> renewal alerts -> save + reload.

## Run the tests
```
python3 -m unittest discover -s tests
```

## Files
- `subscripto/models.py` - `User`, `Household`, `Subscription`,
  `SubscriptionStatus` (Enum with allowed transitions), `PaymentRecord`,
  and the `SubscriptoError` exception hierarchy.
- `subscripto/bill_splitter.py` - percentage validation and Decimal-based
  cost distribution.
- `subscripto/renewal_alert.py` - filters subscriptions renewing within 24h.
- `subscripto/storage.py` - JSON persistence.
- `subscripto/manager.py` - `SubscriptionManager` orchestrator.
- `subscripto/cli.py` - text menu.
- `demo.py` - non-interactive end-to-end lifecycle demo.
- `tests/test_subscripto.py` - the 8 test cases from the proposal.
