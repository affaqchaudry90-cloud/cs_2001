"""Domain exception hierarchy for LEDGER."""


class LedgerError(Exception):
    """Base exception for all LEDGER domain errors."""

    def __repr__(self) -> str:
        """Return a concise representation of this error."""
        return f"{type(self).__name__}({str(self)!r})"


class AccountError(LedgerError):
    """Base exception for account-level failures."""


class InsufficientFundsError(AccountError):
    """Raised when a withdrawal exceeds available funds."""

    def __init__(self, balance: "Money", amount: "Money") -> None:
        """Record available balance and requested amount."""
        self._balance = balance
        self._amount = amount
        super().__init__(f"insufficient funds: have {balance}, need {amount}")

    @property
    def balance(self) -> "Money":
        """Available balance when the withdrawal failed."""
        return self._balance

    @property
    def amount(self) -> "Money":
        """Requested withdrawal amount."""
        return self._amount 

    def __repr__(self) -> str:
        """Return a readable error summary."""
        return f"InsufficientFundsError({self._balance!r}, {self._amount!r})"


class FrozenAccountError(AccountError):
    """Raised when transacting on a frozen account."""

    def __init__(self, iban: str, reason: str) -> None:
        """Record the frozen IBAN and freeze reason."""
        self._iban = iban
        self._reason = reason
        super().__init__(f"{iban} is frozen ({reason})")

    @property
    def iban(self) -> str:
        """IBAN of the frozen account."""
        return self._iban

    @property
    def reason(self) -> str:
        """Reason the account was frozen."""
        return self._reason

    def __repr__(self) -> str:
        """Return a readable error summary."""
        return f"FrozenAccountError({self._iban!r}, {self._reason!r})"


class UnknownAccountError(AccountError):
    """Raised when an IBAN does not exist in the bank."""

    def __init__(self, iban: str) -> None:
        """Record the missing IBAN."""
        self._iban = iban
        super().__init__(f"no account found for {iban}")

    @property
    def iban(self) -> str:
        """The IBAN that was not found."""
        return self._iban

    def __repr__(self) -> str:
        """Return a readable error summary."""
        return f"UnknownAccountError({self._iban!r})"


class WithdrawalLimitError(AccountError):
    """Raised when a withdrawal exceeds a per-transaction cap."""

    def __init__(self, amount: "Money", limit: "Money") -> None:
        """Record requested amount and configured limit."""
        self._amount = amount
        self._limit = limit
        super().__init__(f"{amount} exceeds withdrawal cap of {limit}")

    @property
    def amount(self) -> "Money":
        """Requested withdrawal amount."""
        return self._amount

    @property
    def limit(self) -> "Money":
        """Maximum single-withdrawal limit."""
        return self._limit

    def __repr__(self) -> str:
        """Return a readable error summary."""
        return f"WithdrawalLimitError({self._amount!r}, {self._limit!r})"


class TransactionError(LedgerError):
    """Base exception for invalid transactions or rollbacks."""


class NegativeAmountError(TransactionError):
    """Raised when a negative monetary value is constructed."""


class RollbackError(TransactionError):
    """Raised when reversing the last transaction fails."""


class FraudError(LedgerError):
    """Base exception for fraud detection alerts."""


class SuspiciousActivityError(FraudError):
    """Raised when a transaction triggers a fraud rule."""

    def __init__(self, iban: str, rule_name: str, tx_id: int) -> None:
        """Record flagged IBAN, triggered rule, and transaction ID."""
        self._iban = iban
        self._rule_name = rule_name
        self._tx_id = tx_id
        super().__init__(f"{rule_name} flagged {iban} on tx #{tx_id}")

    @property
    def iban(self) -> str:
        """Flagged account IBAN."""
        return self._iban

    @property
    def rule_name(self) -> str:
        """Name of the triggered rule."""
        return self._rule_name

    @property
    def tx_id(self) -> int:
        """ID of the offending transaction."""
        return self._tx_id

    def __repr__(self) -> str:
        """Return a readable error summary."""
        return (
            f"SuspiciousActivityError({self._iban!r}, "
            f"{self._rule_name!r}, {self._tx_id!r})"
        )


class ConfigError(LedgerError):
    """Raised on invalid CLI flags, parameters, or CSV data."""


class EmptyQueueError(LedgerError):
    """Raised when reading from an empty PaymentQueue."""


class EmptyStackError(LedgerError):
    """Raised when reading from an empty UndoStack."""

