"""Branch, Customer, and Bank domain classes for LEDGER."""

from collections.abc import Iterator

from ledger.accounts import (
    Account,
    CurrentAccount,
    LoanAccount,
    SavingsAccount,
    YouthSavingsAccount,
)
from ledger.exceptions import (
    ConfigError,
    EmptyStackError,
    LedgerError,
    RollbackError,
    TransactionError,
    UnknownAccountError,
)
from ledger.money import Money
from ledger.scheduler import UndoStack
from ledger.transactions import InterestCredit, Transaction, TransactionLog


class Branch:
    """Physical or regional bank branch."""

    def __init__(self, code: str, city: str) -> None:
        """Create a branch with a code and city name."""
        if not isinstance(code, str) or not code.strip():
            raise ConfigError("branch code must be a non-empty string")
        if not isinstance(city, str) or not city.strip():
            raise ConfigError("branch city must be a non-empty string")
        self._code = code.strip()
        self._city = city.strip()

    @property
    def code(self) -> str:
        """Unique branch code."""
        return self._code

    @property
    def city(self) -> str:
        """City where this branch operates."""
        return self._city

    def __repr__(self) -> str:
        """Return a readable branch summary."""
        return f"Branch(code={self._code!r}, city={self._city!r})"


class Customer:
    """Bank customer holding zero or more accounts."""

    def __init__(self, customer_id: str, name: str, branch: Branch) -> None:
        """Create a customer linked to a home branch."""
        if not isinstance(customer_id, str) or not customer_id.strip():
            raise ConfigError("customer_id must be a non-empty string")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError("customer name must be a non-empty string")
        if not isinstance(branch, Branch):
            raise ConfigError("branch must be a Branch instance")
        self._customer_id = customer_id.strip()
        self._name = name.strip()
        self._branch = branch
        self._accounts: list[Account] = []

    @property
    def customer_id(self) -> str:
        """Unique customer identifier."""
        return self._customer_id

    @property
    def name(self) -> str:
        """Full name of the customer."""
        return self._name

    @property
    def branch(self) -> Branch:
        """Customer's home branch."""
        return self._branch

    def add_account(self, account: Account) -> None:
        """Link an account to this customer without duplicating entries."""
        if not isinstance(account, Account):
            raise ConfigError("account must be an Account instance")
        if account not in self._accounts:
            self._accounts.append(account)

    def accounts(self) -> list[Account]:
        """Return a shallow copy of this customer's accounts."""
        return list(self._accounts)

    def joint_accounts(self) -> list[Account]:
        """Return all joint accounts held by this customer."""
        return [acc for acc in self._accounts if acc.is_joint()]

    def net_worth(self) -> Money:
        """Return total balance across all of this customer's accounts."""
        total = Money(0)
        for acc in self._accounts:
            total = total + acc.balance
        return total

    def __len__(self) -> int:
        """Return how many accounts this customer holds."""
        return len(self._accounts)

    def __repr__(self) -> str:
        """Return a concise customer summary."""
        return (
            f"Customer(id={self._customer_id!r}, "
            f"name={self._name!r}, accounts={len(self._accounts)})"
        )


class Bank:
    """Central ledger owning branches, accounts, transaction log, and undo stack."""

    def __init__(self, name: str) -> None:
        """Initialize an empty bank."""
        if not isinstance(name, str) or not name.strip():
            raise ConfigError("bank name must be a non-empty string")
        self._name = name.strip()
        self._accounts: dict[str, Account] = {}
        self._customers: dict[str, Customer] = {}
        self._branches: dict[str, Branch] = {}
        self._log = TransactionLog()
        self._undo = UndoStack()
        self._next_account = 1
        self._next_tx = 1
        self._opening_deposits = Money(0)
        self._transfers_tried = 0
        self._transfers_done = 0
        self._rollbacks = 0

    def _next_iban(self) -> str:
        """Generate the next sequential IBAN string."""
        iban = f"PK{self._next_account:06d}"
        self._next_account += 1
        return iban

    def _ensure_customer(self, customer: Customer) -> None:
        """Register a customer if not already present."""
        if not isinstance(customer, Customer):
            raise ConfigError("expected a Customer instance")
        if customer.customer_id not in self._customers:
            self.add_customer(customer)

    def open_branch(self, code: str, city: str) -> Branch:
        """Create and register a branch, or return the existing one for code."""
        branch = Branch(code, city)
        if branch.code not in self._branches:
            self._branches[branch.code] = branch
        return self._branches[branch.code]

    def add_customer(self, customer: Customer) -> None:
        """Register a new customer with the bank."""
        if not isinstance(customer, Customer):
            raise ConfigError("customer must be a Customer instance")
        if customer.customer_id in self._customers:
            raise ConfigError(f"duplicate customer id: {customer.customer_id}")
        if customer.branch.code not in self._branches:
            self._branches[customer.branch.code] = customer.branch
        self._customers[customer.customer_id] = customer

    def open_account(
        self,
        holders: list[Customer],
        kind: str,
        opening: Money,
    ) -> Account:
        """Open a single or joint account and credit any opening deposit."""
        if not holders:
            raise ConfigError("at least one holder is required")
        if not isinstance(kind, str) or not kind.strip():
            raise ConfigError("account kind must be a non-empty string")
        if not isinstance(opening, Money):
            raise ConfigError("opening deposit must be a Money instance")

        for holder in holders:
            self._ensure_customer(holder)

        iban = self._next_iban()
        primary_id = holders[0].customer_id
        normalized = kind.strip().lower()

        if normalized == "current":
            account: Account = CurrentAccount(iban, primary_id)
        elif normalized == "savings":
            account = SavingsAccount(iban, primary_id)
        elif normalized in ("youth", "youth_savings"):
            account = YouthSavingsAccount(iban, primary_id)
        else:
            raise ConfigError(f"unknown account kind: {kind}")

        for co_holder in holders[1:]:
            account.add_holder(co_holder.customer_id)

        if opening > Money(0):
            account.deposit(opening)
            self._opening_deposits = self._opening_deposits + opening

        self._accounts[iban] = account
        for holder in holders:
            holder.add_account(account)
        return account

    def open_loan(
        self,
        customer: Customer,
        principal: Money,
        instalment: Money,
    ) -> LoanAccount:
        """Open a loan account for a customer."""
        self._ensure_customer(customer)
        iban = self._next_iban()
        loan = LoanAccount(iban, customer.customer_id, principal, instalment)
        self._accounts[iban] = loan
        customer.add_account(loan)
        return loan

    def next_tx_id(self) -> int:
        """Issue the next monotonically increasing transaction ID."""
        tx_id = self._next_tx
        self._next_tx += 1
        return tx_id

    def transfer(
        self,
        from_iban: str,
        to_iban: str,
        amount: Money,
        count_stats: bool = True,
    ) -> None:
        """Move amount atomically from from_iban to to_iban."""
        if count_stats:
            self._transfers_tried += 1
        if from_iban == to_iban:
            raise TransactionError("cannot transfer to the same account")

        src = self[from_iban]
        dst = self[to_iban]

        src.withdraw(amount)
        try:
            dst.deposit(amount)
        except LedgerError:
            src.deposit(amount)
            if count_stats:
                self._rollbacks += 1
            raise

        if count_stats:
            self._transfers_done += 1

    def execute(self, tx: Transaction) -> bool:
        """Apply a transaction, logging success or rejection."""
        try:
            tx.apply(self)
        except LedgerError as exc:
            self._log.reject(tx, str(exc))
            return False
        self._log.append(tx)
        self._undo.push(tx)
        return True

    def rollback_last(self) -> Transaction:
        """Reverse the most recent applied transaction from the undo stack."""
        try:
            tx = self._undo.peek()
        except EmptyStackError as exc:
            raise RollbackError("no transactions available to roll back") from exc

        try:
            tx.reverse(self)
        except LedgerError as exc:
            raise RollbackError(f"cannot roll back tx #{tx.tx_id}: {exc}") from exc

        self._undo.pop()
        self._log.mark_reversed(tx)
        return tx

    def backdate_interest(
        self,
        iban: str,
        from_day: int,
        today: int,
    ) -> InterestCredit | None:
        """Credit recursive compound interest accrued between from_day and today."""
        account = self[iban]
        earned = account.backdated_interest(today - from_day)
        if earned == Money(0):
            return None
        tx = InterestCredit(
            tx_id=self.next_tx_id(),
            day=today,
            amount=earned,
            iban=iban,
            backdated_from=from_day,
        )
        return tx if self.execute(tx) else None

    def freeze(self, iban: str, reason: str) -> None:
        """Freeze the account identified by iban."""
        self[iban].freeze(reason)

    @property
    def log(self) -> TransactionLog:
        """Append-only transaction log for this bank."""
        return self._log

    @property
    def opening_deposits(self) -> Money:
        """Total opening balances credited when accounts were opened."""
        return self._opening_deposits

    def transfer_counts(self) -> tuple[int, int, int]:
        """Return (transfers_tried, transfers_done, rollbacks)."""
        return (self._transfers_tried, self._transfers_done, self._rollbacks)

    def customers(self) -> list[Customer]:
        """Return a list of all registered customers."""
        return list(self._customers.values())

    def __getitem__(self, iban: str) -> Account:
        """Look up an account by IBAN or raise UnknownAccountError."""
        if iban not in self._accounts:
            raise UnknownAccountError(iban)
        return self._accounts[iban]

    def __contains__(self, iban: object) -> bool:
        """Return True if iban belongs to an open account."""
        return iban in self._accounts

    def __len__(self) -> int:
        """Return the number of open accounts in this bank."""
        return len(self._accounts)

    def __iter__(self) -> Iterator[Account]:
        """Iterate over all open accounts."""
        return iter(self._accounts.values())

    def __repr__(self) -> str:
        """Return a concise bank summary."""
        return f"Bank(name={self._name!r}, accounts={len(self._accounts)})"