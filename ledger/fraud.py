"""Rule-based FraudMonitor and polymorphic fraud rules for LEDGER."""

from abc import ABC, abstractmethod

from ledger.bank import Bank
from ledger.exceptions import ConfigError, SuspiciousActivityError
from ledger.money import Money
from ledger.transactions import Transaction, TransactionLog


class Rule(ABC):
    """Abstract base class for polymorphic fraud-detection rules."""

    @property
    def name(self) -> str:
        """Return the class name of this rule."""
        return type(self).__name__

    @abstractmethod
    def check(self, tx: Transaction, log: TransactionLog) -> bool:
        """Return True if tx breaks this rule given the transaction log."""
        ...

    def __repr__(self) -> str:
        """Return a readable representation of this rule."""
        return f"{self.name}()"


class VelocityRule(Rule):
    """Flags an account making at least max_per_day outgoing transactions in one day."""

    def __init__(self, max_per_day: int = 6) -> None:
        """Create a velocity rule with the given daily outgoing limit."""
        if max_per_day < 1:
            raise ConfigError(f"max_per_day must be at least 1, got {max_per_day}")
        self._max_per_day = max_per_day

    def check(self, tx: Transaction, log: TransactionLog) -> bool:
        """Return True if tx's sender hit max_per_day outgoing transactions today."""
        sender = tx.sender()
        if sender is None:
            return False
        count = 0
        for entry in log.between(tx.day, tx.day):
            if entry.sender() == sender:
                count += 1
        return count >= self._max_per_day

    def __repr__(self) -> str:
        """Return a readable representation showing max_per_day."""
        return f"VelocityRule(max_per_day={self._max_per_day})"




class LargeAmountRule(Rule):
    """Flags any outgoing transaction whose amount meets or exceeds threshold."""

    def __init__(self, threshold: Money = Money.from_rupees(250_000)) -> None:
        """Create a large-amount rule with the given Money threshold."""
        self._threshold = threshold

    def check(self, tx: Transaction, log: TransactionLog) -> bool:
        """Return True if tx has a sender and tx.amount >= threshold."""
        return tx.sender() is not None and tx.amount >= self._threshold

    def __repr__(self) -> str:
        """Return a readable representation showing the amount threshold."""
        return f"LargeAmountRule(threshold={self._threshold})"





class RoundTripRule(Rule):
    """Recursively traces same-day transfer chains to detect round-trip cycles."""

    def __init__(self, max_depth: int = 4) -> None:
        """Create a round-trip cycle detector bounded by max_depth hops."""
        if max_depth < 1:
            raise ConfigError(f"max_depth must be at least 1, got {max_depth}")
        self._max_depth = max_depth

    def check(self, tx: Transaction, log: TransactionLog) -> bool:
        """Return True if tx closes a same-day transfer cycle back to its sender."""
        sender = tx.sender()
        receiver = tx.receiver()
        if sender is None or receiver is None:
            return False
        edges = self._edges(tx.day, log)
        # Starting where money went, check if transfers lead back to where it came from.
        return self._trace(receiver, sender, edges, self._max_depth, set())

    def _edges(self, day: int, log: TransactionLog) -> dict[str, list[str]]:
        """Build a sender -> list of receivers map for all transfers on day."""
        edges: dict[str, list[str]] = {}
        for entry in log.between(day, day):
            src = entry.sender()
            dst = entry.receiver()
            if src is not None and dst is not None:
                if src not in edges:
                    edges[src] = []
                edges[src].append(dst)
        return edges

    def _trace(
        self,
        current: str,
        target: str,
        edges: dict[str, list[str]],
        depth: int,
        seen: set[str],
    ) -> bool:
        """Recursively check whether target is reachable from current within depth hops."""
        if current == target:
            return True
        if depth == 0 or current in seen:
            return False
        # Remembering visited IBANs stops infinite loops if another cycle exists.
        seen.add(current)
        for nxt in edges.get(current, []):
            if self._trace(nxt, target, edges, depth - 1, seen):
                return True
        return False

    def __repr__(self) -> str:
        """Return a readable representation showing max_depth."""
        return f"RoundTripRule(max_depth={self._max_depth})"





class FraudMonitor:
    """Streams each day's TransactionLog through every Rule and freezes hits."""

    def __init__(self, rules: list[Rule]) -> None:
        """Create a FraudMonitor owning the given list of rules."""
        self._rules = list(rules)
        self._flagged: dict[str, str] = {}



    def scan(self, day: int, bank: Bank) -> list[str]:
        """Check today's transactions; freeze every account that breaks a rule."""
        frozen_today: list[str] = []
        # Stream today's entries lazily and freeze each flagged account once.
        for tx in bank.log.between(day, day):
            try:
                self._check(tx, bank.log)
            except SuspiciousActivityError as error:
                if error.iban not in self._flagged:
                    bank.freeze(error.iban, str(error))
                    self._flagged[error.iban] = str(error)
                    frozen_today.append(error.iban)
        return frozen_today



    def _check(self, tx: Transaction, log: TransactionLog) -> None:
        """Test tx against every rule; raise SuspiciousActivityError on first match."""
        for rule in self._rules:
            if rule.check(tx, log):
                sender = tx.sender()
                iban = sender if sender is not None else tx.accounts()[0]
                raise SuspiciousActivityError(iban, rule.name, tx.tx_id)



    def flagged(self) -> dict[str, str]:
        """Return a copy of the {iban: reason} dictionary of flagged accounts."""
        return dict(self._flagged)




    def __repr__(self) -> str:
        """Return a concise summary of this FraudMonitor."""
        return f"FraudMonitor(rules={len(self._rules)}, flagged={len(self._flagged)})"
