"""Categoria de oficio y su precio sugerido por lead."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from app.domain.exceptions import ValidationError
from app.domain.models.pricing import assert_sellable_price
from app.domain.value_objects import Money

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(slots=True)
class Category:
    """Oficio (carpinteria, fontaneria...) con el precio de referencia de sus leads.

    `suggested_lead_price` NO es el precio de venta: es el que se aplica cuando el
    admin no ha fijado uno propio para un contacto concreto. El precio real de una
    venta lo resuelve `Lead.sale_price()`.
    """

    id: UUID
    slug: str
    name_es: str
    name_en: str
    suggested_lead_price: Money
    active: bool = True

    def __post_init__(self) -> None:
        self.slug = self.slug.strip().lower()
        if not _SLUG_RE.match(self.slug):
            raise ValidationError(f"Slug de categoria invalido: {self.slug!r}")
        assert_sellable_price(self.suggested_lead_price)

    def name(self, locale: str) -> str:
        return self.name_en if locale.lower().startswith("en") else self.name_es

    def change_suggested_lead_price(self, price: Money) -> None:
        """Actualiza el precio de referencia del oficio.

        Solo afecta a las ventas futuras sin precio propio: las compras ya creadas
        guardan su importe y los leads con precio fijado por el admin lo conservan.
        """
        assert_sellable_price(price)
        self.suggested_lead_price = price
