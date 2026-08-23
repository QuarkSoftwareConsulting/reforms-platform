"""Caso de uso: explorador de solicitudes para el profesional.

Devuelve siempre proyecciones publicas (`LeadPublicView`): es imposible que un
endpoint del explorador filtre datos de contacto por descuido.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto import LeadListItem, LeadListResult
from app.application.ports import (
    CategoryRepositoryPort,
    LeadRepositoryPort,
    LeadSearchFilters,
    ProfessionalRepositoryPort,
)
from app.domain.exceptions import ProfessionalNotFoundError

MAX_PAGE_SIZE = 50


@dataclass(slots=True)
class ListLeads:
    leads: LeadRepositoryPort
    categories: CategoryRepositoryPort
    professionals: ProfessionalRepositoryPort

    async def execute(
        self,
        *,
        professional_id: UUID,
        category_ids: set[UUID] | None = None,
        radius_km: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> LeadListResult:
        professional = await self.professionals.get(professional_id)
        if professional is None:
            raise ProfessionalNotFoundError()
        professional.assert_ready_to_browse()

        # El profesional solo puede filtrar dentro de los oficios que declaro.
        selected = (
            category_ids & professional.category_ids if category_ids else professional.category_ids
        )
        if not selected:
            return LeadListResult(items=[], total=0, limit=limit, offset=offset)

        filters = LeadSearchFilters(
            category_ids=selected,
            center=professional.base_coordinates,
            radius_km=min(radius_km or professional.service_radius_km, 300),
            limit=min(limit, MAX_PAGE_SIZE),
            offset=max(offset, 0),
        )

        rows = await self.leads.search(filters, requester_professional_id=professional_id)
        total = await self.leads.count(filters)

        categories = {c.id: c for c in await self.categories.get_many(selected)}
        items = [
            LeadListItem(
                lead=row.lead.public_view(),
                category=categories[row.lead.category_id],
                price=categories[row.lead.category_id].lead_price,
                distance_km=row.distance_km,
                already_purchased=row.purchased_by_requester,
            )
            for row in rows
            if row.lead.category_id in categories
        ]
        return LeadListResult(items=items, total=total, limit=filters.limit, offset=filters.offset)
