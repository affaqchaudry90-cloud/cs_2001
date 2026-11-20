# LEDGER — Digital Bank with Simulated Customers & Fraud Detection (CS 2001 Fall 2026)

**Authors:** Chaudry Affaq Ur Rehman (29020161) & Ahmed Mohammad Iqbal (28020022)

**LEDGER** is a pure-Python digital banking core, multi-agent day-by-day simulator, and rule-based fraud monitor built with exact integer-paisa `Money` arithmetic (`1 rupee = 100 paisa`). Three stretch goals from the brief are implemented end-to-end: **(2) Joint accounts** (`Account._holder_ids`, `add_holder()`, `is_joint()`, `Customer.joint_accounts()`, and CSV `joint_with`); **(3) Recursive back-dated interest** (`InterestBearing.backdated_interest()` / `_compound()`, `Bank.backdate_interest()`, and CSV `opened_days_ago`); and **(4) Both custom ADTs** — `PaymentQueue` (FIFO) and `UndoStack` (LIFO), wired into `Bank.rollback_last()` and CLI `--undo`.

---

## (a) Architecture & OOP Relationships

LEDGER separates responsibilities across 11 modules under `ledger/` with a strict acyclic import order (`exceptions` → `money` → `accounts` → `transactions` → `scheduler` → `bank` → `agents` → `fraud` → `reports` → `files` → `simulation`) driven by `main.py`. Every relationship follows its exact lifetime semantics:

- **Composition (owns):** `Bank` creates and owns its `Account` instances, `Branch` objects, `TransactionLog`, and `UndoStack`; `Simulation` creates and owns its `Bank`, `FraudMonitor`, and `PaymentQueue`; `FraudMonitor` owns its `Rule` objects. Internal collections stay private (`_`-prefixed) and expose only read-only views or copies.
- **Aggregation (has):** `Customer` holds references to `Account` objects created by `Bank` (`Customer` ↔ `Account` is many-to-many for joint accounts, so removing a customer does not destroy an account). `Bank` likewise aggregates `Customer` objects passed to `add_customer()`.
- **Association (knows):** Each `Customer` references its home `Branch`, each `CustomerAgent` acts for a `Customer`, `Statement` describes an `Account`, and `AuditReport` reads `Bank` and `FraudMonitor`.
- **Inheritance & Interfaces:** Abstract base classes enforce contracts on `Account` (`CurrentAccount`, `SavingsAccount`, `YouthSavingsAccount`, `LoanAccount`), frozen `Transaction` (`Deposit`, `Withdrawal`, `Transfer`, `FeeCharge`, `InterestCredit`), duck-typed `CustomerAgent` (`SalariedAgent`, `StudentAgent`, `MerchantAgent`, `FraudsterAgent`), `Rule` (`VelocityRule`, `LargeAmountRule`, `RoundTripRule`), and the `Reportable` interface implemented by `Statement` and `AuditReport`.

---

## (b) Multiple Inheritance & MRO

`SavingsAccount` uses cooperative multiple inheritance via the stateless `InterestBearing` mixin (`class SavingsAccount(InterestBearing, Account)`), and `YouthSavingsAccount` inherits from `SavingsAccount`. Because `InterestBearing` defines no `__init__`, `Account.__init__` runs cleanly while Python's C3 Method Resolution Order gives:

```text
SavingsAccount.__mro__:
(<class 'ledger.accounts.SavingsAccount'>, <class 'ledger.accounts.InterestBearing'>,
 <class 'ledger.accounts.Account'>, <class 'abc.ABC'>, <class 'object'>)

YouthSavingsAccount.__mro__:
(<class 'ledger.accounts.YouthSavingsAccount'>, <class 'ledger.accounts.SavingsAccount'>,
 <class 'ledger.accounts.InterestBearing'>, <class 'ledger.accounts.Account'>,
 <class 'abc.ABC'>, <class 'object'>)
```

Placing `InterestBearing` **before** `Account` ensures Python resolves `daily_interest()` and recursive `backdated_interest(days)` on `InterestBearing` rather than `Account`'s default `Money(0)` stubs. `CurrentAccount` and `LoanAccount` inherit the zero defaults, allowing `Simulation._close_day()` and `Bank.backdate_interest()` to run polymorphically on every account with zero `isinstance` chains.

---

## (c) Exception Strategy (LBYL vs. EAFP)

All domain failures inherit from `LedgerError` across a 14-class tree (`AccountError` → `InsufficientFundsError`, `FrozenAccountError`, `UnknownAccountError`, `WithdrawalLimitError`; `TransactionError` → `NegativeAmountError`, `RollbackError`; `FraudError` → `SuspiciousActivityError`; plus `ConfigError`, `EmptyQueueError`, `EmptyStackError`). Five subclasses store typed context in private fields with read-only properties so callers never parse strings.

`Bank.transfer()` guarantees atomicity via `try / except / else / finally`: it withdraws from the source first, attempts to deposit into the target inside `try`, refunds the source on any `LedgerError` before re-raising, updates `_transfers_done` in `else`, and increments `_transfers_tried` in `finally`. All file operations in `ledger/files.py` and `main.py` use `with open(...)` context managers.

LEDGER deliberately pairs **LBYL** (Look Before You Leap) with **EAFP** (Easier to Ask Forgiveness than Permission). Where a condition is cheap and expected on the normal path — such as `if not account.is_frozen:` in `Simulation._close_day()` and `if iban not in self._accounts:` in `Bank.__getitem__()` — LBYL avoids exception overhead. Where an operation may fail for multiple domain reasons mid-flight — such as `FraudMonitor.scan()` catching `SuspiciousActivityError`, `Bank.execute()` catching `LedgerError` to log rejections, and `Bank.transfer()` catching `LedgerError` on step 2 to reverse step 1 — EAFP keeps the happy path clear and guarantees cleanup.

---

## (d) Custom ADTs & Operation Costs

Both custom ADTs encapsulate their internal lists behind narrow interfaces. `PaymentQueue` (FIFO) processes due standing orders and retries using `_items: list[ScheduledPayment]` and a moving `_front: int` index rather than O(n) `list.pop(0)`. `UndoStack` (LIFO) stores applied `Transaction` objects in `_items: list[Transaction]` for `Bank.rollback_last()` and `--undo N`.

| ADT | Operations | Time Complexity | Empty Behaviour |
|---|---|---|---|
| `PaymentQueue` (FIFO) | `enqueue`, `dequeue`, `peek`, `is_empty`, `__len__` | **O(1)** each | `EmptyQueueError` |
| `UndoStack` (LIFO) | `push`, `pop`, `peek`, `is_empty`, `__len__` | **O(1)** each | `EmptyStackError` |

The trade-off in `PaymentQueue` is space: advancing `_front` keeps `dequeue()` strictly O(1), while previously dequeued slots stay allocated in `_items` for the duration of the run.

---

## (e) Testing Strategy & Real Bugs Caught

Our `unittest` suite contains **52 tests across 8 modules** (`test_money`, `test_accounts`, `test_transactions`, `test_queue`, `test_transfer_atomicity`, `test_fraud`, `test_files`, `test_simulation`). Each test builds an isolated bank, verifies exception families with `assertRaises`, checks atomic rollback and determinism across repeated seeds, and asserts the bank-wide invariant (`total == opening_deposits + money_in - money_out`, where internal transfers cancel out) via `AuditReport.check_invariant()` every day.

Two real bugs were caught and fixed during testing and audit:
1. **Inflated transfer stats on undo:** `Transfer.reverse()` initially called `Bank.transfer()` directly, incrementing `_transfers_tried` and `_transfers_done` whenever a transfer was rolled back. Adding `count_stats: bool = True` to `Bank.transfer()` and passing `count_stats=False` from `Transfer.reverse()` fixed the accounting without losing atomicity.
2. **Unbounded recursion on negative back-dating:** `InterestBearing._compound()` terminated only on `days == 0`, so a negative `days` argument to `backdated_interest(days)` would recurse until `RecursionError`. Validating `days < 0` with `TransactionError` eliminated the crash.

---

## (f) Limitations & Future Refactors

Three natural next improvements stand out: (1) compacting `PaymentQueue._items = _items[_front:]` whenever `_front` exceeds half the list length to keep amortized O(1) time with bounded memory on multi-year runs; (2) separating debt owed from deposit balances in `Customer.net_worth()` instead of summing `LoanAccount` repayments alongside deposits; and (3) adding a compliance review/unfreeze workflow or interactive query REPL on top of the locked core.
