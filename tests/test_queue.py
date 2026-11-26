"""Unit tests for ScheduledPayment, PaymentQueue, and UndoStack."""

import unittest

from ledger.exceptions import EmptyQueueError, EmptyStackError
from ledger.money import Money
from ledger.scheduler import PaymentQueue, ScheduledPayment, UndoStack
from ledger.transactions import Deposit


class TestScheduledPayment(unittest.TestCase):
    """Tests for immutable ScheduledPayment penalty behavior."""

    def test_with_penalty_returns_new_payment(self) -> None:
        """Applying a penalty adds the fee, shifts due_day, and keeps original unchanged."""
        original = ScheduledPayment("PK000001", "PK000002", Money.from_rupees(2_000), 4)
        retried = original.with_penalty(Money.from_rupees(250))

        self.assertEqual(retried.amount, Money.from_rupees(2_250))
        self.assertEqual(retried.due_day, 5)
        self.assertEqual(retried.attempts, 1)
        self.assertEqual(original.amount, Money.from_rupees(2_000))
        self.assertEqual(original.due_day, 4)
        self.assertEqual(original.attempts, 0)

    def test_chained_penalties_accumulate(self) -> None:
        """Repeated penalties keep incrementing attempts and due_day."""
        p0 = ScheduledPayment("PK000001", "PK000003", Money.from_rupees(1_000), 10)
        p2 = p0.with_penalty(Money.from_rupees(100)).with_penalty(Money.from_rupees(100))

        self.assertEqual(p2.amount, Money.from_rupees(1_200))
        self.assertEqual(p2.due_day, 12)
        self.assertEqual(p2.attempts, 2)


class TestPaymentQueue(unittest.TestCase):
    """Tests for FIFO PaymentQueue operations."""

    def test_empty_queue_raises(self) -> None:
        """Empty queue reports length 0 and refuses dequeue and peek."""
        queue = PaymentQueue()
        self.assertTrue(queue.is_empty())
        self.assertEqual(len(queue), 0)

        with self.assertRaises(EmptyQueueError):
            queue.dequeue()
        with self.assertRaises(EmptyQueueError):
            queue.peek()

    def test_fifo_order_and_peek(self) -> None:
        """Items leave in first-in, first-out order and peek does not remove."""
        queue = PaymentQueue()
        p1 = ScheduledPayment("PK000001", "PK000002", Money.from_rupees(500), 1)
        p2 = ScheduledPayment("PK000001", "PK000003", Money.from_rupees(750), 2)
        p3 = ScheduledPayment("PK000002", "PK000003", Money.from_rupees(900), 3)

        queue.enqueue(p1)
        queue.enqueue(p2)
        queue.enqueue(p3)

        self.assertFalse(queue.is_empty())
        self.assertEqual(len(queue), 3)
        self.assertEqual(queue.peek(), p1)
        self.assertEqual(len(queue), 3)

        self.assertEqual(queue.dequeue(), p1)
        self.assertEqual(queue.dequeue(), p2)
        self.assertEqual(queue.dequeue(), p3)
        self.assertTrue(queue.is_empty())

    def test_interleaved_enqueue_and_dequeue(self) -> None:
        """Queue stays accurate when enqueues and dequeues are mixed."""
        queue = PaymentQueue()
        p1 = ScheduledPayment("PK000001", "PK000002", Money.from_rupees(100), 1)
        p2 = ScheduledPayment("PK000001", "PK000002", Money.from_rupees(200), 2)
        p3 = ScheduledPayment("PK000001", "PK000002", Money.from_rupees(300), 3)

        queue.enqueue(p1)
        queue.enqueue(p2)
        self.assertEqual(queue.dequeue(), p1)
        queue.enqueue(p3)

        self.assertEqual(len(queue), 2)
        self.assertEqual(queue.dequeue(), p2)
        self.assertEqual(queue.dequeue(), p3)
        self.assertTrue(queue.is_empty())


class TestUndoStack(unittest.TestCase):
    """Tests for LIFO UndoStack operations."""

    def test_empty_stack_raises(self) -> None:
        """Empty stack reports length 0 and refuses pop and peek."""
        stack = UndoStack()
        self.assertTrue(stack.is_empty())
        self.assertEqual(len(stack), 0)

        with self.assertRaises(EmptyStackError):
            stack.pop()
        with self.assertRaises(EmptyStackError):
            stack.peek()

    def test_lifo_order_and_peek(self) -> None:
        """Transactions pop in reverse order and peek leaves them on top."""
        stack = UndoStack()
        tx1 = Deposit(1, 1, Money.from_rupees(400), "PK000001")
        tx2 = Deposit(2, 1, Money.from_rupees(800), "PK000001")
        tx3 = Deposit(3, 2, Money.from_rupees(1_200), "PK000002")

        stack.push(tx1)
        stack.push(tx2)
        stack.push(tx3)

        self.assertFalse(stack.is_empty())
        self.assertEqual(len(stack), 3)
        self.assertEqual(stack.peek(), tx3)
        self.assertEqual(len(stack), 3)

        self.assertEqual(stack.pop(), tx3)
        self.assertEqual(stack.pop(), tx2)
        self.assertEqual(stack.pop(), tx1)
        self.assertTrue(stack.is_empty())

    def test_reuse_after_emptying(self) -> None:
        """Stack works normally when refilled after being emptied."""
        stack = UndoStack()
        first = Deposit(10, 1, Money.from_rupees(300), "PK000001")
        second = Deposit(11, 2, Money.from_rupees(600), "PK000001")

        stack.push(first)
        self.assertEqual(stack.pop(), first)
        self.assertTrue(stack.is_empty())

        stack.push(second)
        self.assertEqual(len(stack), 1)
        self.assertEqual(stack.pop(), second)


if __name__ == "__main__":
    unittest.main()