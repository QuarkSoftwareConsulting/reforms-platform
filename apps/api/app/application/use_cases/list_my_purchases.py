"""Caso de uso: historial "Mis contactos" del profesional."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto import PurchasedContact
from app.application.ports import (
    CategoryRepositoryPort,
    ClockPort,
    LeadRepositoryPort,
    PurchaseRepositoryPort,
)

MAX_PAGE_SIZE = 100


@dataclass(slots=True)
class ListMyPurchases:
    purchases: PurchaseRepositoryPort
    leads: LeadRepositoryPort
    categories: CategoryRepositoryPort
    clock: ClockPort

    async def execute(
        self, *, professional_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[PurchasedContact]:
        # Solo compras pagadas y pagos en curso, una por lead: los checkouts
        # abandonados o fallidos no desbloquean nada y repetian el lead.
        rows = await self.purchases.list_history_for_professional(
            professional_id,
            now=self.clock.now(),
            limit=min(limit, MAX_PAGE_SIZE),
            offset=max(offset, 0),
        )

        result: list[PurchasedContact] = []
        for purchase in rows:
            lead = await self.leads.get(purchase.lead_id)
            if lead is None:
                continue
            category = await self.categories.get(lead.category_id)
            if category is None:
                continue
            result.append(
                PurchasedContact(
                    purchase=purchase,
                    lead=lead,
                    category=category,
                    # Un pago en curso aun no desbloquea nada.
                    contact=lead.contact if purchase.unlocks_contact else None,
                )
            )
        return result
