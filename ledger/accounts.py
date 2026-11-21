""".      Account hierarchy and interest mixin for LEDGER   """

from abc import ABC, abstractmethod

from ledger.exceptions import (
    ConfigError,
    FrozenAccountError,
    InsufficientFundsError,
    TransactionError,
    WithdrawalLimitError,
)
from ledger.money import Money


def _require_text(value: str, field: str) -> str:
    """Validate and strip a required non-empty string field."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field} must be a non-empty string")
    return value.strip()


class InterestBearing:
    """Mixin adding daily and recursive back-dated interest."""

    RATE: float = 0.0

    @property
    def annual_rate(self) -> float:
        """Annual interest rate for this account."""
        return self.RATE

    def daily_interest(self) -> Money:
        """Return one day of interest on the current balance."""
        return Money(round(self.balance.paisa * self.annual_rate / 365))

    def backdated_interest(self, days: int) -> Money:
        """Return compounded interest earned over a past number of days."""
        if days < 0:
            raise TransactionError("back-dated days cannot be negative")
        base = self.balance.paisa
        return Money(self._compound(base, days) - base)

    def _compound(self, paisa: int, days: int) -> int:
        """Recursively compound daily interest for the remaining days."""
        if days == 0:
            return paisa
        next_paisa = paisa + round(paisa * self.annual_rate / 365)
        return self._compound(next_paisa, days - 1)


class Account(ABC):
    """Abstract base class shared by all bank accounts."""

    def __init__(self, iban: str, holder_id: str) -> None:
        """Initialize an active account with a zero balance."""
        self._iban = _require_text(iban, "iban")
        self._holder_ids: list[str] = [_require_text(holder_id, "holder_id")]
        self._balance: Money = Money(0)
        self._freeze_reason: str | None = None

    def _validate_tx(self, amount: Money) -> None:
        """Reject transactions on frozen accounts or with zero amounts."""
        if self._freeze_reason is not None:
            raise FrozenAccountError(self._iban, self._freeze_reason)
        if amount == Money(0):
            raise TransactionError("transaction amount must be positive")

    def add_holder(self, customer_id: str) -> None:
        """Add another holder to turn this into a joint account."""
        cid = _require_text(customer_id, "customer_id")
        if cid not in self._holder_ids:
            self._holder_ids.append(cid)

    def is_joint(self) -> bool:
        """Return True when multiple holders share this account."""
        return len(self._holder_ids) > 1

    def freeze(self, reason: str) -> None:
        """Freeze this account and store the reason."""
        self._freeze_reason = reason

    def deposit(self, amount: Money) -> None:
        """Credit a positive amount to the account."""
        self._validate_tx(amount)
        self._balance = self._balance + amount
        assert self._balance >= Money(0)

    def withdraw(self, amount: Money) -> None:
        """Debit a permitted amount from the account."""
        self._validate_tx(amount)
        if self.can_withdraw(amount):
            self._balance = self._balance - amount
            assert self._balance >= Money(0)
        else:
            raise InsufficientFundsError(self._balance, amount)

    def daily_interest(self) -> Money:
        """Default zero interest for non-interest-bearing accounts."""
        return Money(0)

    def backdated_interest(self, days: int) -> Money:
        """Default zero back-dated interest for standard accounts."""
        if days < 0:
            raise TransactionError("back-dated days cannot be negative")
        return Money(0)

    @abstractmethod
    def can_withdraw(self, amount: Money) -> bool:
        """Return True if withdrawing amount obeys account rules."""

    @abstractmethod
    def monthly_fee(self) -> Money:
        """Return the monthly fee charged to this account."""

    @property
    def iban(self) -> str:
        """Unique account IBAN."""
        return self._iban

    @property
    def holders(self) -> tuple[str, ...]:
        """Immutable tuple of holder customer IDs."""
        return tuple(self._holder_ids)

    @property
    def balance(self) -> Money:
        """Current account balance."""
        return self._balance

    @property
    def is_frozen(self) -> bool:
        """Return True if the account is currently frozen."""
        return self._freeze_reason is not None

    @property
    def frozen_reason(self) -> str:
        """Reason for the freeze, or an empty string if active."""
        return self._freeze_reason or ""

    def __eq__(self, other: object) -> bool:
        """Accounts are equal when their IBANs match."""
        if not isinstance(other, Account):
            return NotImplemented
        return self._iban == other._iban

    def __hash__(self) -> int:
        """Hash accounts by IBAN."""
        return hash(self._iban)

    def __lt__(self, other: object) -> bool:
        """Order accounts by balance."""
        if not isinstance(other, Account):
            return NotImplemented
        return self._balance < other._balance

    def __repr__(self) -> str:
        """Return a concise debug representation."""
        return f"{type(self).__name__}(iban={self._iban!r}, balance={self._balance!r})"

    def __str__(self) -> str:
        """Return a readable account summary."""
        status = " [FROZEN]" if self.is_frozen else ""
        return f"{type(self).__name__} {self._iban}: {self._balance}{status}"


class CurrentAccount(Account):
    """Checking account with a flat Rs 150 monthly fee."""

    FEE: Money = Money(15_000)

    def can_withdraw(self, amount: Money) -> bool:
        """Allow withdrawing up to the full available balance."""
        return self._balance >= amount

    def monthly_fee(self) -> Money:
        """Return the Rs 150 monthly maintenance fee."""
        return self.FEE


class SavingsAccount(InterestBearing, Account):
    """Interest-bearing savings account with a Rs 500 minimum balance."""

    RATE: float = 0.08
    MIN_BALANCE: Money = Money(50_000)

    def can_withdraw(self, amount: Money) -> bool:
        """Require at least MIN_BALANCE to remain after debiting."""
        return self._balance >= amount + self.MIN_BALANCE

    def monthly_fee(self) -> Money:
        """No monthly fee on savings accounts."""
        return Money(0)


class YouthSavingsAccount(SavingsAccount):
    """Student savings account with 10% interest and a Rs 5,000 withdrawal cap."""

    RATE: float = 0.10
    MIN_BALANCE: Money = Money(0)
    MAX_WITHDRAWAL: Money = Money(500_000)

    def can_withdraw(self, amount: Money) -> bool:
        """Check balance rules and single-withdrawal cap."""
        return super().can_withdraw(amount) and amount <= self.MAX_WITHDRAWAL

    def withdraw(self, amount: Money) -> None:
        """Enforce active state and per-withdrawal cap before debiting."""
        self._validate_tx(amount)
        if amount > self.MAX_WITHDRAWAL:
            raise WithdrawalLimitError(amount, self.MAX_WITHDRAWAL)
        super().withdraw(amount)


class LoanAccount(Account):
    """Loan account whose balance records total principal repaid."""

    def __init__(
        self,
        iban: str,
        holder_id: str,
        principal: Money,
        instalment: Money,
    ) -> None:
        """Validate loan principal and instalment schedule."""
        super().__init__(iban, holder_id)
        if principal == Money(0) or instalment == Money(0):
            raise ConfigError("loan principal and instalment must be positive")
        if instalment > principal:
            raise ConfigError("instalment cannot exceed principal")
        self._principal = principal
        self._instalment = instalment

    @property
    def principal(self) -> Money:
        """Original loan principal."""
        return self._principal

    @property
    def instalment(self) -> Money:
        """Monthly scheduled instalment."""
        return self._instalment

    def remaining(self) -> Money:
        """Return unpaid principal left on this loan."""
        return self._principal - self._balance

    def is_paid_off(self) -> bool:
        """Return True once the entire principal has been repaid."""
        return self.remaining() == Money(0)

    def deposit(self, amount: Money) -> None:
        """Accept a repayment that does not exceed the remaining balance."""
        self._validate_tx(amount)
        if amount > self.remaining():
            raise TransactionError("repayment exceeds remaining loan balance")
        super().deposit(amount)

    def can_withdraw(self, amount: Money) -> bool:
        """Loan accounts never permit withdrawals."""
        return False

    def monthly_fee(self) -> Money:
        """No monthly fee on loan accounts."""
        return Money(0)