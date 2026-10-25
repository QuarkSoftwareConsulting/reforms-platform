"""Casos de uso de precios (solo admin).

El precio de un contacto lo decide el admin. La categoria aporta un precio
sugerido, que es el que se cobra mientras nadie fije otro para ese lead concreto.

`SetLeadPrice` toma el lead con `SELECT ... FOR UPDATE` a proposito: es el mismo
bloqueo que usa `StartLeadPurchase`, asi que un cambio de precio no puede colarse
entre la lectura del precio y la creacion de la compra. O la compra se crea con el
precio viejo, o con el nuevo, nunca con uno intermedio.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto import LeadPricing
from app.application.ports import (
    CategoryRepositoryPort,
    LeadRepositoryPort,
    UnitOfWork,
)
from app.domain.exceptions import CategoryNotFoundError, LeadNotFoundError
from app.domain.models import Category, Lead
from app.domain.value_objects import Money


def _pricing(lead: Lead, category: Category) -> LeadPricing:
    return LeadPricing(
        lead_id=lead.id,
        category=category,
        suggested_price=category.suggested_lead_price,
        sale_price=lead.sale_price(suggested=category.suggested_lead_price),
        is_custom=lead.has_custom_price,
    )


@dataclass(slots=True)
class GetLeadPricing:
    """Lo que el admin necesita ver antes de decidir: sugerido y precio actual."""

    leads: LeadRepositoryPort
    categories: CategoryRepositoryPort

    async def execute(self, *, lead_id: UUID) -> LeadPricing:
        lead = await self.leads.get(lead_id)
        if lead is None:
            raise LeadNotFoundError()
        category = await self.categories.get(lead.category_id)
        if category is None:
            raise CategoryNotFoundError()
        return _pricing(lead, category)


@dataclass(slots=True)
class SetLeadPrice:
    """Fija el precio de venta de un contacto concreto.

    `price=None` borra el precio propio y devuelve el lead al precio sugerido de su
    categoria.
    """

    leads: LeadRepositoryPort
    categories: CategoryRepositoryPort
    uow: UnitOfWork

    async def execute(self, *, lead_id: UUID, price: Money | None) -> LeadPricing:
        async with self.uow:
            lead = await self.leads.get_for_update(lead_id)
            if lead is None:
                raise LeadNotFoundError()

            category = await self.categories.get(lead.category_id)
            if category is None:
                raise CategoryNotFoundError()

            lead.set_price_override(price, suggested=category.suggested_lead_price)
            lead = await self.leads.update(lead)

        return _pricing(lead, category)
