"""Simulated CustomerAgent hierarchy for LEDGER."""

from abc import ABC, abstractmethod
import random

from ledger.bank import Bank, Customer
from ledger.money import Money
from ledger.transactions import Deposit, Transaction, Transfer, Withdrawal


class CustomerAgent(ABC):
    """Abstract simulated customer that generates daily transactions."""

    def __init__(
        self,
        customer: Customer,
        iban: str,
        shops: list[str],
        rng: random.Random,
    ) -> None:
        """Link this agent to its customer, main IBAN, shop list, and RNG."""
        self._customer = customer
        self._iban = iban
        # Keep our own copy so outside edits to the list do not affect this agent.
        self._shops = list(shops)
        self._rng = rng

    @property
    def customer(self) -> Customer:
        """Return the Customer this agent acts for."""
        return self._customer

    @property
    def is_fraudster(self) -> bool:
        """Return False for legitimate customer agents."""
        return False

    @abstractmethod
    def act(self, day: int, bank: Bank) -> list[Transaction]:
        """Generate zero or more Transactions for the given banking day."""
        ...

    def __repr__(self) -> str:
        """Return a readable summary of this agent."""
        return f"{type(self).__name__}({self._customer.customer_id!r}, iban={self._iban!r})"


class SalariedAgent(CustomerAgent):
    """Salaried customer with monthly payday, rent, and everyday purchases."""

    def __init__(
        self,
        customer: Customer,
        iban: str,
        shops: list[str],
        rng: random.Random,
    ) -> None:
        """Initialize a salaried agent with random salary, payday, and rent."""
        super().__init__(customer, iban, shops, rng)
        self._salary = Money.from_rupees(self._rng.randint(75_000, 140_000))
        self._payday = self._rng.randint(1, 28)
        self._rent = Money.from_rupees(self._rng.randint(15_000, 30_000))




    def act(self, day: int, bank: Bank) -> list[Transaction]:
        """Emit salary, rent, and daily spending transactions."""
        txs: list[Transaction] = []
        available = bank[self._iban].balance

        if day % 30 == self._payday:
            txs.append(Deposit(bank.next_tx_id(), day, self._salary, self._iban))
            available = available + self._salary

        rent_day = (self._payday + 1) % 30
        if day % 30 == rent_day and self._shops and available >= self._rent:
            shop = self._rng.choice(self._shops)
            txs.append(Transfer(bank.next_tx_id(), day, self._rent, self._iban, shop))
            available = available - self._rent

        num_purchases = self._rng.randint(0, 2)
        for _ in range(num_purchases):
            amount = Money.from_rupees(self._rng.randint(500, 6_000))
            if available < amount:
                continue
            if self._shops:
                shop = self._rng.choice(self._shops)
                txs.append(Transfer(bank.next_tx_id(), day, amount, self._iban, shop))
            else:
                txs.append(Withdrawal(bank.next_tx_id(), day, amount, self._iban))
            available = available - amount
        return txs





class StudentAgent(CustomerAgent):
    """Student customer receiving bi-weekly allowance and making small purchases."""

    def __init__(
        self,
        customer: Customer,
        iban: str,
        shops: list[str],
        rng: random.Random,
    ) -> None:
        """Initialize a student agent with a random bi-weekly allowance."""
        super().__init__(customer, iban, shops, rng)
        self._allowance = Money.from_rupees(self._rng.randint(12_000, 22_000))

    def act(self, day: int, bank: Bank) -> list[Transaction]:
        """Emit allowance deposits and small daily purchases."""
        txs: list[Transaction] = []
        available = bank[self._iban].balance

        if day % 14 == 1:
            txs.append(Deposit(bank.next_tx_id(), day, self._allowance, self._iban))
            available = available + self._allowance

        # About 1 day in 25, attempt a spend over the Rs 5,000 youth limit.
        if self._rng.random() < 0.04:
            big_spend = Money.from_rupees(self._rng.randint(5_200, 6_200))
            if available >= big_spend:
                txs.append(Withdrawal(bank.next_tx_id(), day, big_spend, self._iban))
            return txs

        num_purchases = self._rng.randint(0, 2)
        for _ in range(num_purchases):
            amount = Money.from_rupees(self._rng.randint(200, 2_400))
            if available < amount:
                continue
            if self._shops:
                shop = self._rng.choice(self._shops)
                txs.append(Transfer(bank.next_tx_id(), day, amount, self._iban, shop))
            else:
                txs.append(Withdrawal(bank.next_tx_id(), day, amount, self._iban))
            available = available - amount
        return txs




class MerchantAgent(CustomerAgent):
    """Merchant depositing daily sales and withdrawing operating cash."""

    def __init__(
        self,
        customer: Customer,
        iban: str,
        shops: list[str],
        rng: random.Random,
    ) -> None:
        """Initialize a merchant agent with random daily sales."""
        super().__init__(customer, iban, shops, rng)
        self._daily_sales = Money.from_rupees(self._rng.randint(15_000, 50_000))




    def act(self, day: int, bank: Bank) -> list[Transaction]:
        """Emit daily sales deposits and occasional cash withdrawals."""
        txs: list[Transaction] = []
        available = bank[self._iban].balance

        # Merchants never transfer to other customers, preventing false round-trips.
        txs.append(Deposit(bank.next_tx_id(), day, self._daily_sales, self._iban))
        available = available + self._daily_sales

        if self._rng.random() < 0.75:
            cash_out = Money.from_rupees(self._rng.randint(4_000, 30_000))
            if available >= cash_out:
                txs.append(Withdrawal(bank.next_tx_id(), day, cash_out, self._iban))
        return txs




class FraudsterAgent(CustomerAgent):
    """Adversarial agent executing velocity, large-transfer, or round-trip attacks."""

    def __init__(
        self,
        customer: Customer,
        iban: str,
        shops: list[str],
        rng: random.Random,
        mules: list[str],
        strategy: str,
        attack_day: int,
    ) -> None:
        """Initialize a fraudster agent with mule IBANs, attack strategy, and start day."""
        super().__init__(customer, iban, shops, rng)
        self._mules = list(mules)
        self._strategy = strategy
        self._attack_day = attack_day




    @property
    def is_fraudster(self) -> bool:
        """Return True because this agent is a simulated fraudster."""
        return True




    def _velocity_attack(self, day: int, bank: Bank) -> list[Transaction]:
        """Emit a burst of 8 withdrawals in one day to test VelocityRule."""
        txs: list[Transaction] = []
        needed = Money.from_rupees(35_000)
        if bank[self._iban].balance < needed:
            txs.append(Deposit(bank.next_tx_id(), day, needed, self._iban))
        for _ in range(8):
            amount = Money.from_rupees(self._rng.randint(1_500, 3_500))
            txs.append(Withdrawal(bank.next_tx_id(), day, amount, self._iban))
        return txs




    def _large_attack(self, day: int, bank: Bank) -> list[Transaction]:
        """Emit a single Rs 295,000 transfer to a mule to test LargeAmountRule."""
        txs: list[Transaction] = []
        transfer_amount = Money.from_rupees(295_000)
        if bank[self._iban].balance < transfer_amount:
            top_up = Money.from_rupees(300_000)
            txs.append(Deposit(bank.next_tx_id(), day, top_up, self._iban))
        target = self._mules[0]
        txs.append(Transfer(bank.next_tx_id(), day, transfer_amount, self._iban, target))
        return txs




    def _round_trip_attack(self, day: int, bank: Bank) -> list[Transaction]:
        """Move Rs 45,000 around main -> mule 1 -> mule 2 -> main on the same day."""
        txs: list[Transaction] = []
        amount = Money.from_rupees(45_000)
        if bank[self._iban].balance < amount:
            top_up = Money.from_rupees(50_000)
            txs.append(Deposit(bank.next_tx_id(), day, top_up, self._iban))
        mule_one = self._mules[0]
        mule_two = self._mules[1]
        txs.append(Transfer(bank.next_tx_id(), day, amount, self._iban, mule_one))
        txs.append(Transfer(bank.next_tx_id(), day, amount, mule_one, mule_two))
        txs.append(Transfer(bank.next_tx_id(), day, amount, mule_two, self._iban))
        return txs




    def act(self, day: int, bank: Bank) -> list[Transaction]:
        """Blend in before attack_day, then run the configured fraud strategy."""
        if day < self._attack_day:
            if day % 7 == 1:
                amount = Money.from_rupees(self._rng.randint(20_000, 40_000))
                return [Deposit(bank.next_tx_id(), day, amount, self._iban)]
            return []

        if (day - self._attack_day) % 10 != 0:
            return []

        if self._strategy == "velocity":
            return self._velocity_attack(day, bank)
        if self._strategy == "large":
            return self._large_attack(day, bank)
        if self._strategy == "round_trip":
            return self._round_trip_attack(day, bank)
        return []
