"""Objeto de valor Money: importe en centimos + divisa, sin aritmetica de coma flotante."""

from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_CURRENCIES = frozenset({"EUR", "USD", "GBP", "COP", "MXN"})
ZERO_DECIMAL_CURRENCIES = frozenset({"JPY", "KRW", "CLP"})


@dataclass(frozen=True, slots=True)
class Money:
    """Importe monetario inmutable.

    Se guarda siempre en la unidad minima (centimos) porque es la unidad que usa
    Stripe y evita cualquier error de redondeo en coma flotante.
    """

    amount_cents: int
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount_cents, int) or isinstance(self.amount_cents, bool):
            raise ValueError("amount_cents debe ser un entero de centimos")
        if self.amount_cents < 0:
            raise ValueError("amount_cents no puede ser negativo")
        normalized = self.currency.upper().strip()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError(f"Divisa invalida: {self.currency!r}")
        object.__setattr__(self, "currency", normalized)

    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls(0, currency)

    @classmethod
    def from_units(cls, units: float | int, currency: str) -> Money:
        """Crea un Money a partir de la unidad mayor (5.00 EUR -> 500 centimos)."""
        factor = 1 if currency.upper() in ZERO_DECIMAL_CURRENCIES else 100
        return cls(round(units * factor), currency)

    @property
    def units(self) -> float:
        factor = 1 if self.currency in ZERO_DECIMAL_CURRENCIES else 100
        return self.amount_cents / factor

    def _assert_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"No se pueden operar importes en divisas distintas: "
                f"{self.currency} y {other.currency}"
            )

    def __add__(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(self.amount_cents + other.amount_cents, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(self.amount_cents - other.amount_cents, self.currency)

    def __str__(self) -> str:
        return f"{self.units:.2f} {self.currency}"
