"""Caso de uso: historial "Mis contactos" del profesional."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto import PurchasedContact
from app.application.ports import (
    CategoryRepositoryPort,
    LeadRepositoryPort,
    PurchaseRepositoryPort,
)

MAX_PAGE_SIZE = 100


@dataclass(slots=True)
class ListMyPurchases:
    purchases: PurchaseRepositoryPort
    leads: LeadRepositoryPort
    categories: CategoryRepositoryPort

    async def execute(
        self, *, professional_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[PurchasedContact]:
        rows = await self.purchases.list_for_professional(
            professional_id, limit=min(limit, MAX_PAGE_SIZE), offset=max(offset, 0)
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
                    # Una compra reservada o caducada no desbloquea nada.
                    contact=lead.contact if purchase.unlocks_contact else None,
                )
            )
        return result
