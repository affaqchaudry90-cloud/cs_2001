"""Immutable integer-paisa Money value object."""

from dataclasses import dataclass
from functools import total_ordering

from ledger.exceptions import NegativeAmountError


@total_ordering
@dataclass(frozen=True)
class Money:
    """Immutable currency amount stored as non-negative integer paisa."""

    paisa: int

    def __post_init__(self) -> None:

        """Ensure paisa is a non-negative int (rejecting bool)."""

        if isinstance(self.paisa, bool) or not isinstance(self.paisa, int):
            raise TypeError(f"expected int paisa, got {type(self.paisa).__name__}")
        
        if self.paisa < 0:
            raise NegativeAmountError(f"negative paisa not allowed: {self.paisa}")

    @classmethod
    def from_rupees(cls, rupees: float) -> "Money":
        """Convert a numeric rupee value to Money rounded to whole paisa."""

        if isinstance(rupees, bool) or not isinstance(rupees, (int, float)):
            
            raise TypeError(f"expected numeric rupees, got {type(rupees).__name__}")
        
        return cls(round(rupees * 100))

    def __add__(self, other: "Money") -> "Money":
        """Return the sum of two Money objects."""

        if not isinstance(other, Money):

            return NotImplemented
        
        return Money(self.paisa + other.paisa)

    def __sub__(self, other: "Money") -> "Money":
        """Return the difference of two Money objects."""

        if not isinstance(other, Money):

            return NotImplemented
        
        if other.paisa > self.paisa:
            raise NegativeAmountError("subtraction would produce a negative amount")
        return Money(self.paisa - other.paisa)

    def __mul__(self, factor: float) -> "Money":
        """Scale this amount by a non-negative number."""

        if isinstance(factor, bool) or not isinstance(factor, (int, float)):
            return NotImplemented
        
        if factor < 0:
            raise NegativeAmountError(f"cannot scale by negative factor: {factor}")
        return Money(round(self.paisa * factor))

    def __lt__(self, other: "Money") -> bool:
        """Compare two Money objects by paisa."""

        if not isinstance(other, Money):

            return NotImplemented
        
        return self.paisa < other.paisa

    def __str__(self) -> str:

        """Format amount properly."""
        rupees = self.paisa // 100

        rem = self.paisa % 100

        return f"Rs {rupees:,}.{rem:02d}"