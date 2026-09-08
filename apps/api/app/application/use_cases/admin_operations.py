"""Casos de uso del backoffice: inventario, metricas y soporte."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto import (
    AdminLeadItem,
    AdminLeadListResult,
    AdminMetrics,
    AdminProfessionalItem,
    AdminProfessionalListResult,
    AdminPurchaseItem,
)
from app.application.ports import (
    AdminLeadFilters,
    CategoryRepositoryPort,
    ClockPort,
    IdGeneratorPort,
    LeadRepositoryPort,
    ProfessionalRepositoryPort,
    PurchaseRepositoryPort,
    PurchaseReviewRepositoryPort,
    UnitOfWork,
)
from app.domain.exceptions import LeadNotFoundError, PurchaseNotFoundError
from app.domain.models import Lead, PurchaseReview

MAX_PAGE_SIZE = 100


@dataclass(slots=True)
class ListAdminLeads:
    """Lista solicitudes para operar el marketplace sin exponer PII del cliente."""

    leads: LeadRepositoryPort
    categories: CategoryRepositoryPort

    async def execute(self, filters: AdminLeadFilters) -> AdminLeadListResult:
        normalized = AdminLeadFilters(
            category_id=filters.category_id,
            status=filters.status,
            source=filters.source,
            limit=min(max(filters.limit, 1), MAX_PAGE_SIZE),
            offset=max(filters.offset, 0),
        )
        leads = await self.leads.search_admin(normalized)
        total = await self.leads.count_admin(normalized)
        category_ids = {lead.category_id for lead in leads}
        categories = {
            category.id: category for category in await self.categories.get_many(category_ids)
        }
        items = [
            AdminLeadItem(
                lead=lead.public_view(),
                category=categories[lead.category_id],
                price=lead.sale_price(suggested=categories[lead.category_id].suggested_lead_price),
                status=lead.status,
                source=lead.source,
                purchases_count=lead.purchases_count,
                max_purchases=lead.max_purchases,
            )
            for lead in leads
            if lead.category_id in categories
        ]
        return AdminLeadListResult(
            items=items, total=total, limit=normalized.limit, offset=normalized.offset
        )


@dataclass(slots=True)
class ChangeLeadAvailability:
    """Retira o vuelve a publicar un lead sin tocar sus plazas ya vendidas."""

    leads: LeadRepositoryPort
    uow: UnitOfWork

    async def execute(self, *, lead_id: UUID, publish: bool) -> Lead:
        async with self.uow:
            lead = await self.leads.get_for_update(lead_id)
            if lead is None:
                raise LeadNotFoundError()
            if publish:
                lead.republish()
            else:
                lead.disable()
            return await self.leads.update(lead)


@dataclass(slots=True)
class GetAdminMetrics:
    """Resume el estado actual del marketplace sin mezclar monedas."""

    leads: LeadRepositoryPort
    purchases: PurchaseRepositoryPort
    professionals: ProfessionalRepositoryPort

    async def execute(self) -> AdminMetrics:
        lead_counts = await self.leads.dashboard_counts()
        purchase_metrics = await self.purchases.paid_metrics()
        return AdminMetrics(
            leads_total=lead_counts.total,
            leads_published=lead_counts.published,
            leads_exhausted=lead_counts.exhausted,
            leads_disabled=lead_counts.disabled,
            leads_organic=lead_counts.organic,
            leads_admin=lead_counts.admin,
            professionals_total=await self.professionals.count_all(),
            paid_purchases=purchase_metrics.count,
            paid_leads=purchase_metrics.lead_count,
            revenue_by_currency=purchase_metrics.revenue_by_currency,
        )


@dataclass(slots=True)
class ListLeadPurchasesForAdmin:
    """Devuelve compras y profesional asociado, nunca el contacto del cliente."""

    purchases: PurchaseRepositoryPort
    professionals: ProfessionalRepositoryPort
    reviews: PurchaseReviewRepositoryPort

    async def execute(self, *, lead_id: UUID, limit: int, offset: int) -> list[AdminPurchaseItem]:
        purchases = await self.purchases.list_for_lead(
            lead_id, limit=min(max(limit, 1), MAX_PAGE_SIZE), offset=max(offset, 0)
        )
        result: list[AdminPurchaseItem] = []
        for purchase in purchases:
            result.append(
                AdminPurchaseItem(
                    purchase=purchase,
                    professional=await self.professionals.get(purchase.professional_id),
                    review_count=len(await self.reviews.list_for_purchase(purchase.id)),
                )
            )
        return result


@dataclass(slots=True)
class ListAdminProfessionals:
    """Directorio de profesionales de consulta, sin modificar cuentas ni roles."""

    professionals: ProfessionalRepositoryPort
    categories: CategoryRepositoryPort

    async def execute(
        self, *, query: str | None, limit: int, offset: int
    ) -> AdminProfessionalListResult:
        normalized_limit = min(max(limit, 1), MAX_PAGE_SIZE)
        normalized_offset = max(offset, 0)
        rows = await self.professionals.list_admin(
            query=query, limit=normalized_limit, offset=normalized_offset
        )
        categories = {
            category.id: category
            for category in await self.categories.get_many(
                {category_id for professional in rows for category_id in professional.category_ids}
            )
        }
        return AdminProfessionalListResult(
            items=[
                AdminProfessionalItem(
                    professional=professional,
                    categories=[
                        categories[category_id]
                        for category_id in professional.category_ids
                        if category_id in categories
                    ],
                )
                for professional in rows
            ],
            total=await self.professionals.count_admin(query=query),
            limit=normalized_limit,
            offset=normalized_offset,
        )


@dataclass(slots=True)
class MarkPurchaseForReview:
    """Registra una nota de soporte sin alterar el pago ni liberar una plaza."""

    purchases: PurchaseRepositoryPort
    reviews: PurchaseReviewRepositoryPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork

    async def execute(self, *, purchase_id: UUID, admin_user_id: UUID, note: str) -> PurchaseReview:
        async with self.uow:
            if await self.purchases.get(purchase_id) is None:
                raise PurchaseNotFoundError()
            review = PurchaseReview(
                id=self.ids.new_id(),
                purchase_id=purchase_id,
                reviewed_by_user_id=admin_user_id,
                note=note,
                created_at=self.clock.now(),
            )
            return await self.reviews.add(review)
