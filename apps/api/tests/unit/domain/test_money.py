import pytest

from app.domain.value_objects import Money


def test_from_units_converts_to_cents() -> None:
    assert Money.from_units(5, "eur") == Money(500, "EUR")
    assert Money.from_units(5.05, "EUR").amount_cents == 505


def test_units_property_round_trips() -> None:
    assert Money(500, "EUR").units == 5.0


def test_currency_is_normalized_to_uppercase() -> None:
    assert Money(500, "usd").currency == "USD"


def test_zero_decimal_currency_does_not_scale() -> None:
    assert Money.from_units(500, "JPY").amount_cents == 500
    assert Money(500, "JPY").units == 500


@pytest.mark.parametrize(
    ("cents", "currency"),
    [(-1, "EUR"), (100, "EU"), (100, "EUROS"), (100, "E1R")],
)
def test_invalid_money_is_rejected(cents: int, currency: str) -> None:
    with pytest.raises(ValueError):
        Money(cents, currency)


def test_float_cents_rejected() -> None:
    with pytest.raises(ValueError, match="entero de centimos"):
        Money(5.5, "EUR")  # type: ignore[arg-type]


def test_arithmetic_requires_matching_currency() -> None:
    assert Money(500, "EUR") + Money(250, "EUR") == Money(750, "EUR")
    with pytest.raises(ValueError, match="divisas distintas"):
        Money(500, "EUR") + Money(500, "USD")


def test_str_renders_units_and_currency() -> None:
    assert str(Money(500, "EUR")) == "5.00 EUR"
