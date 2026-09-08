"""Politica de precios de venta de un lead.

Vive aparte de `Category` y `Lead` porque ambos la necesitan: la categoria valida
su precio sugerido y el lead valida el precio que el admin le fija a mano.
"""

from __future__ import annotations

from app.domain.exceptions import CurrencyMismatchError, InvalidSalePriceError
from app.domain.value_objects import Money

MAX_SALE_PRICE_CENTS = 100_000
"""Tope de seguridad del precio de un lead (1.000 EUR en centimos).

No es una regla de negocio sino una red contra el error de tecleo: sin el, un cero
de mas convierte un lead de 5 EUR en uno de 500 EUR y el profesional se encuentra
el cargo cuando ya ha pagado.
"""


def assert_sellable_price(price: Money) -> None:
    """Valida que un importe pueda usarse como precio de venta de un contacto."""
    if price.amount_cents <= 0:
        raise InvalidSalePriceError("El precio del lead debe ser mayor que cero")
    if price.amount_cents > MAX_SALE_PRICE_CENTS:
        raise InvalidSalePriceError(
            f"El precio del lead no puede superar {MAX_SALE_PRICE_CENTS} centimos"
        )


def assert_same_currency(price: Money, reference: Money) -> None:
    """El precio de un lead no puede cambiar de divisa respecto a su oficio.

    Un lead en otra divisa abriria dos precios distintos para el mismo oficio y la
    sesion de checkout se crearia con una moneda que el resto del catalogo no usa.
    """
    if price.currency != reference.currency:
        raise CurrencyMismatchError(
            f"El precio debe estar en {reference.currency}, no en {price.currency}"
        )
