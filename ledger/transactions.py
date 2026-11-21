"""Frozen Transaction hierarchy, append-only TransactionLog, and LogIterator."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

from ledger.exceptions import TransactionError
from ledger.money import Money


@dataclass(frozen=True)
class Transaction(ABC):
    """Abstract immutable record of a single banking transaction."""

    tx_id: int
    day: int
    amount: Money

    def __post_init__(self) -> None:
        """Validate that day >= 1 and amount > Money(0)."""
        if self.day < 1:
            raise TransactionError(f"transaction day must be >= 1, got {self.day}")
        if self.amount == Money(0):
            raise TransactionError("transaction amount must be positive")

    # "Bank" in quotes: bank.py imports this file, so we cannot import it back.
    @abstractmethod
    def apply(self, bank: "Bank") -> None:
        """Apply this transaction to the given bank."""
        ...

    @abstractmethod
    def reverse(self, bank: "Bank") -> None:
        """Undo this transaction on the given bank."""
        ...

    @abstractmethod
    def sender(self) -> str | None:
        """Return the IBAN money leaves, or None if entering from outside."""
        ...

    @abstractmethod
    def receiver(self) -> str | None:
        """Return the IBAN money enters, or None if leaving the bank."""
        ...

    def accounts(self) -> tuple[str, ...]:
        """Return a tuple containing whichever of sender() and receiver() exist."""
        ibans = []
        src = self.sender()
        dst = self.receiver()
        if src is not None:
            ibans.append(src)
        if dst is not None:
            ibans.append(dst)
        return tuple(ibans)


@dataclass(frozen=True)
class Deposit(Transaction):
    """External deposit adding money to one account."""

    iban: str

    def apply(self, bank: "Bank") -> None:
        """Deposit amount into self.iban."""
        bank[self.iban].deposit(self.amount)

    def reverse(self, bank: "Bank") -> None:
        """Withdraw amount back out of self.iban."""
        bank[self.iban].withdraw(self.amount)

    def sender(self) -> None:
        """Return None because deposits arrive from outside the bank."""
        return None

    def receiver(self) -> str:
        """Return the IBAN receiving the deposit."""
        return self.iban


@dataclass(frozen=True)
class Withdrawal(Transaction):
    """Cash or card withdrawal removing money from one account."""

    iban: str

    def apply(self, bank: "Bank") -> None:
        """Withdraw amount from self.iban."""
        bank[self.iban].withdraw(self.amount)

    def reverse(self, bank: "Bank") -> None:
        """Deposit amount back into self.iban."""
        bank[self.iban].deposit(self.amount)

    def sender(self) -> str:
        """Return the IBAN money leaves."""
        return self.iban

    def receiver(self) -> None:
        """Return None because withdrawals leave the bank."""
        return None


@dataclass(frozen=True)
class Transfer(Transaction):
    """Atomic transfer moving money from from_iban to to_iban."""

    from_iban: str
    to_iban: str

    def __post_init__(self) -> None:
        """Validate base fields and reject self-transfers."""
        super().__post_init__()
        if self.from_iban == self.to_iban:
            raise TransactionError("cannot transfer to the same account")

    def apply(self, bank: "Bank") -> None:
        """Transfer amount from from_iban to to_iban atomically."""
        bank.transfer(self.from_iban, self.to_iban, self.amount)

    def reverse(self, bank: "Bank") -> None:
        """Transfer amount back from to_iban to from_iban without inflating transfer stats."""
        bank.transfer(self.to_iban, self.from_iban, self.amount, count_stats=False)

    def sender(self) -> str:
        """Return the source IBAN."""
        return self.from_iban

    def receiver(self) -> str:
        """Return the destination IBAN."""
        return self.to_iban


@dataclass(frozen=True)
class FeeCharge(Transaction):
    """Bank fee charged to one account."""

    iban: str
    reason: str

    def apply(self, bank: "Bank") -> None:
        """Withdraw the fee from self.iban."""
        bank[self.iban].withdraw(self.amount)

    def reverse(self, bank: "Bank") -> None:
        """Refund the fee back into self.iban."""
        bank[self.iban].deposit(self.amount)

    def sender(self) -> str:
        """Return the IBAN paying the fee."""
        return self.iban

    def receiver(self) -> None:
        """Return None because fee revenue leaves customer accounts."""
        return None


@dataclass(frozen=True)
class InterestCredit(Transaction):
    """Interest credited to an InterestBearing account."""

    iban: str
    backdated_from: int | None = None

    def apply(self, bank: "Bank") -> None:
        """Deposit interest into self.iban."""
        bank[self.iban].deposit(self.amount)

    def reverse(self, bank: "Bank") -> None:
        """Withdraw interest back out of self.iban."""
        bank[self.iban].withdraw(self.amount)

    def sender(self) -> None:
        """Return None because interest enters from the bank."""
        return None

    def receiver(self) -> str:
        """Return the IBAN receiving the interest."""
        return self.iban


class LogIterator:
    """Custom iterator over a snapshot copy of TransactionLog entries.

    An iterator keeps its own position (_index) and delivers one item per
    next() call until nothing is left, then raises StopIteration.
    """

    def __init__(self, entries: list[Transaction]) -> None:
        """Store a copy of entries and start the index at 0."""
        # Copying the list means later appends to the log do not disturb a loop.
        self._entries = list(entries)
        self._index = 0

    def __iter__(self) -> "LogIterator":
        """Return self so this iterator works directly in for-loops."""
        return self

    def __next__(self) -> Transaction:
        """Return the next Transaction or raise StopIteration at the end."""
        if self._index >= len(self._entries):
            raise StopIteration
        entry = self._entries[self._index]
        self._index += 1
        return entry

    def __repr__(self) -> str:
        """Return a readable representation of this iterator."""
        return f"LogIterator(index={self._index}, total={len(self._entries)})"


class TransactionLog:
    """Append-only record of applied, rejected, and reversed transactions."""

    def __init__(self) -> None:
        """Create an empty transaction log."""
        self._entries: list[Transaction] = []
        self._rejected: list[tuple[Transaction, str]] = []
        self._reversed: list[Transaction] = []

    def append(self, tx: Transaction) -> None:
        """Record an applied transaction."""
        self._entries.append(tx)

    def reject(self, tx: Transaction, reason: str) -> None:
        """Record a refused transaction together with its failure reason."""
        self._rejected.append((tx, reason))

    def mark_reversed(self, tx: Transaction) -> None:
        """Mark an applied transaction as reversed."""
        self._reversed.append(tx)

    def between(self, start: int, end: int) -> Iterator[Transaction]:
        """Yield applied transactions whose day falls in [start, end]."""
        for tx in self._entries:
            if start <= tx.day <= end:
                yield tx

    def effective(self) -> Iterator[Transaction]:
        """Yield applied transactions that have not been reversed."""
        for tx in self._entries:
            if tx not in self._reversed:
                yield tx

    def rejected(self) -> list[tuple[Transaction, str]]:
        """Return a copy of the rejected (transaction, reason) list."""
        return list(self._rejected)

    def __getitem__(self, day: int | slice) -> list[Transaction]:
        """Return applied entries for a single day or an inclusive day slice."""
        if isinstance(day, int):
            # log[5] means "everything on day 5"
            return list(self.between(day, day))
        if isinstance(day, slice):
            # log[3:5] means "days 3 to 5"; Python passes a slice with .start and .stop
            return list(self.between(day.start, day.stop))
        raise TypeError(f"log index must be int or slice, got {type(day).__name__}")

    def __len__(self) -> int:
        """Return the number of applied transactions in the log."""
        return len(self._entries)

    def __iter__(self) -> LogIterator:
        """Return a fresh LogIterator over applied entries."""
        return LogIterator(self._entries)

    def __repr__(self) -> str:
        """Return a concise summary of log counts."""
        return f"TransactionLog(applied={len(self._entries)}, rejected={len(self._rejected)})"
