"""ScheduledPayment, custom FIFO PaymentQueue ADT, and LIFO UndoStack ADT."""

from dataclasses import dataclass

from ledger.exceptions import EmptyQueueError, EmptyStackError
from ledger.money import Money
from ledger.transactions import Transaction


@dataclass(frozen=True)
class ScheduledPayment:
    """An immutable scheduled transfer due on a specific banking day."""

    from_iban: str
    to_iban: str
    amount: Money
    due_day: int
    attempts: int = 0

    def with_penalty(self, penalty: Money) -> "ScheduledPayment":
        """Return a new ScheduledPayment due the next day with penalty added."""
        return ScheduledPayment(
            from_iban=self.from_iban,
            to_iban=self.to_iban,
            amount=self.amount + penalty,
            due_day=self.due_day + 1,
            attempts=self.attempts + 1,
        )


class PaymentQueue:
    """FIFO Queue ADT backed by a list and front index (all operations O(1))."""

    def __init__(self) -> None:
        """Create an empty PaymentQueue."""
        # Advancing _front avoids list.pop(0), which would shift items in O(n).
        self._items: list[ScheduledPayment] = []
        self._front = 0

    def enqueue(self, payment: ScheduledPayment) -> None:
        """Add payment to the back of the queue. Cost: O(1)."""
        self._items.append(payment)

    def dequeue(self) -> ScheduledPayment:
        """Remove and return the front payment, or raise EmptyQueueError. Cost: O(1)."""
        if self.is_empty():
            raise EmptyQueueError("cannot dequeue from an empty PaymentQueue")
        payment = self._items[self._front]
        self._front += 1
        return payment

    def peek(self) -> ScheduledPayment:
        """Return the front payment without removing it, or raise EmptyQueueError. Cost: O(1)."""
        if self.is_empty():
            raise EmptyQueueError("cannot peek at an empty PaymentQueue")
        return self._items[self._front]

    def is_empty(self) -> bool:
        """Return True when no items remain ahead of _front. Cost: O(1)."""
        return self._front == len(self._items)

    def __len__(self) -> int:
        """Return the number of queued payments. Cost: O(1)."""
        return len(self._items) - self._front

    def __repr__(self) -> str:
        """Return a concise representation of this PaymentQueue."""
        return f"PaymentQueue(size={len(self)})"


class UndoStack:
    """LIFO Stack ADT storing applied transactions for rollback (all ops O(1))."""

    def __init__(self) -> None:
        """Create an empty UndoStack."""
        self._items: list[Transaction] = []

    def push(self, tx: Transaction) -> None:
        """Push an applied transaction onto the top of the stack. Cost: O(1)."""
        self._items.append(tx)

    def pop(self) -> Transaction:
        """Remove and return the top transaction, or raise EmptyStackError. Cost: O(1)."""
        if self.is_empty():
            raise EmptyStackError("cannot pop from an empty UndoStack")
        return self._items.pop()

    def peek(self) -> Transaction:
        """Return the top transaction without removing it, or raise EmptyStackError. Cost: O(1)."""
        if self.is_empty():
            raise EmptyStackError("cannot peek at an empty UndoStack")
        return self._items[-1]

    def is_empty(self) -> bool:
        """Return True if the stack has no transactions. Cost: O(1)."""
        return len(self._items) == 0

    def __len__(self) -> int:
        """Return the number of transactions on the stack. Cost: O(1)."""
        return len(self._items)

    def __repr__(self) -> str:
        """Return a concise representation of this UndoStack."""
        return f"UndoStack(size={len(self)})"
