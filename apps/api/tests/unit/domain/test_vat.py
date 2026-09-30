"""Desglose del IVA de los precios publicados (IVA incluido)."""

import pytest

from app.domain.models import VAT_RATE_PERCENT, vat_breakdown
from app.domain.value_objects import Money


def test_general_rate_is_21_percent() -> None:
    assert VAT_RATE_PERCENT == 21


@pytest.mark.parametrize(
    ("total", "net", "vat"),
    [(500, 413, 87), (1800, 1488, 312), (121, 100, 21), (1, 1, 0)],
)
def test_splits_a_vat_included_price(total: int, net: int, vat: int) -> None:
    breakdown = vat_breakdown(Money(total, "EUR"))
    assert breakdown.net == Money(net, "EUR")
    assert breakdown.vat == Money(vat, "EUR")
    assert breakdown.rate_percent == 21


def test_net_plus_vat_always_matches_the_total() -> None:
    # Redondear base y cuota por separado descuadraria algun centimo en este rango.
    for total in range(1, 3000):
        breakdown = vat_breakdown(Money(total, "EUR"))
        assert breakdown.net.amount_cents + breakdown.vat.amount_cents == total, total
