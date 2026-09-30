"""Categoria de oficio, sus servicios y su precio sugerido por lead.

El catalogo tiene dos niveles (Etapa 1): categoria (Reformas, Instaladores...) y
servicio (Reformas de banos, Aerotermia...). El cliente elige una categoria y, de
forma opcional, los servicios que necesita de ella.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from app.domain.exceptions import InvalidServiceError, ValidationError
from app.domain.models.pricing import assert_sellable_price
from app.domain.value_objects import Money

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SERVICES_PER_LEAD = 10


@dataclass(frozen=True, slots=True)
class Service:
    """Servicio concreto dentro de una categoria."""

    id: UUID
    slug: str
    name_es: str
    name_en: str
    sort_order: int = 0
    active: bool = True

    def __post_init__(self) -> None:
        if not _SLUG_RE.match(self.slug):
            raise ValidationError(f"Slug de servicio invalido: {self.slug!r}")

    def name(self, locale: str) -> str:
        return self.name_en if locale.lower().startswith("en") else self.name_es


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
    sort_order: int = 0
    services: list[Service] = field(default_factory=list)
    """Todos, tambien los retirados: un lead antiguo sigue nombrando el suyo."""

    def __post_init__(self) -> None:
        self.slug = self.slug.strip().lower()
        if not _SLUG_RE.match(self.slug):
            raise ValidationError(f"Slug de categoria invalido: {self.slug!r}")
        assert_sellable_price(self.suggested_lead_price)

    def name(self, locale: str) -> str:
        return self.name_en if locale.lower().startswith("en") else self.name_es

    @property
    def active_services(self) -> list[Service]:
        """Los que se ofrecen hoy en el formulario, en el orden del catalogo."""
        return sorted((s for s in self.services if s.active), key=lambda s: s.sort_order)

    def resolve_services(self, service_ids: Sequence[UUID]) -> list[Service]:
        """Valida los servicios que el cliente eligio para esta categoria.

        Quita duplicados conservando el orden. Rechaza servicios de otra categoria o
        retirados del catalogo: el profesional filtra por ellos y un servicio ajeno
        haria aparecer la solicitud donde no toca.
        """
        unique = list(dict.fromkeys(service_ids))
        if len(unique) > MAX_SERVICES_PER_LEAD:
            raise ValidationError(f"Maximo {MAX_SERVICES_PER_LEAD} servicios por solicitud")
        offered = {s.id: s for s in self.active_services}
        missing = [sid for sid in unique if sid not in offered]
        if missing:
            raise InvalidServiceError(
                f"Servicios que no pertenecen a la categoria {self.slug}: {missing}"
            )
        return [offered[sid] for sid in unique]

    def services_named(self, service_ids: Sequence[UUID]) -> list[Service]:
        """Los servicios de un lead, en su orden, aunque hoy esten retirados."""
        by_id = {s.id: s for s in self.services}
        return [by_id[sid] for sid in service_ids if sid in by_id]

    def change_suggested_lead_price(self, price: Money) -> None:
        """Actualiza el precio de referencia del oficio.

        Solo afecta a las ventas futuras sin precio propio: las compras ya creadas
        guardan su importe y los leads con precio fijado por el admin lo conservan.
        """
        assert_sellable_price(price)
        self.suggested_lead_price = price
