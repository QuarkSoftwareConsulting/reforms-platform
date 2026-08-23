"""Caso de uso: detalle de una solicitud.

Es el unico punto del sistema que puede devolver los datos de contacto, y solo si
existe una compra pagada del profesional que pregunta.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto import LeadDetail
from app.application.ports import (
    CategoryRepositoryPort,
    LeadRepositoryPort,
    ProfessionalRepositoryPort,
    PurchaseRepositoryPort,
)
from app.domain.exceptions import (
    CategoryNotFoundError,
    LeadNotFoundError,
    ProfessionalNotFoundError,
)
from app.domain.models import LeadStatus, PurchaseStatus


@dataclass(slots=True)
class GetLeadDetail:
    leads: LeadRepositoryPort
    purchases: PurchaseRepositoryPort
    categories: CategoryRepositoryPort
    professionals: ProfessionalRepositoryPort

    async def execute(self, *, lead_id: UUID, professional_id: UUID) -> LeadDetail:
        professional = await self.professionals.get(professional_id)
        if professional is None:
            raise ProfessionalNotFoundError()

        lead = await self.leads.get(lead_id)
        if lead is None:
            raise LeadNotFoundError()

        # Un lead retirado por el admin no debe seguir visible salvo que el
        # profesional ya lo hubiera comprado (necesita conservar su contacto).
        already_paid = await self.purchases.has_paid_purchase(lead_id, professional_id)
        if lead.status is LeadStatus.DISABLED and not already_paid:
            raise LeadNotFoundError()

        category = await self.categories.get(lead.category_id)
        if category is None:
            raise CategoryNotFoundError()

        purchases = [
            p
            for p in await self.purchases.list_for_professional(professional_id, limit=200)
            if p.lead_id == lead_id
        ]
        paid = next((p for p in purchases if p.status is PurchaseStatus.PAID), None)
        current = paid or next(iter(purchases), None)

        distance_km = professional.base_coordinates.distance_km_to(lead.location.coordinates)

        return LeadDetail(
            lead=lead.public_view(),
            category=category,
            price=category.lead_price,
            distance_km=round(distance_km, 1),
            contact=lead.contact_view(unlocked=True) if paid is not None else None,
            purchase=current,
        )
