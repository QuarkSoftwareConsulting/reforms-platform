"""Casos de uso del backoffice: inventario, metricas y soporte."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from app.application.dto import (
    AdminLeadItem,
    AdminLeadListResult,
    AdminMetrics,
    AdminProfessionalItem,
    AdminProfessionalListResult,
    AdminPurchaseItem,
    AdminPurchaseListResult,
    AdminPurchaseQuery,
    DailyMetricsPoint,
    MetricsTimeseries,
)
from app.application.ports import (
    AdminLeadFilters,
    AdminPurchaseFilters,
    CategoryRepositoryPort,
    ClockPort,
    CreditLedgerRepositoryPort,
    IdGeneratorPort,
    LeadRepositoryPort,
    ProfessionalAccountRepositoryPort,
    ProfessionalRepositoryPort,
    PurchaseRepositoryPort,
    PurchaseReviewRepositoryPort,
    UnitOfWork,
)
from app.domain.exceptions import LeadNotFoundError, PurchaseNotFoundError, ValidationError
from app.domain.models import Category, Lead, Professional, PurchaseReview, VerificationStatus

MAX_PAGE_SIZE = 100
BUSINESS_TIMEZONE = "Europe/Madrid"
"""Donde se cortan los dias del panel: el negocio opera en la Comunidad de Madrid."""
DEFAULT_TIMESERIES_DAYS = 30
MAX_TIMESERIES_DAYS = 366


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
    accounts: ProfessionalAccountRepositoryPort
    ledger: CreditLedgerRepositoryPort
    clock: ClockPort

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
            active_accounts=await self.accounts.count_active(now=self.clock.now()),
            topup_revenue_by_currency=await self.ledger.topup_totals(),
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
    accounts: ProfessionalAccountRepositoryPort
    clock: ClockPort

    async def execute(
        self,
        *,
        query: str | None,
        limit: int,
        offset: int,
        verification_status: VerificationStatus | None = None,
    ) -> AdminProfessionalListResult:
        """Con `verification_status=PENDING` es la cola de validacion."""
        normalized_limit = min(max(limit, 1), MAX_PAGE_SIZE)
        normalized_offset = max(offset, 0)
        rows = await self.professionals.list_admin(
            query=query,
            limit=normalized_limit,
            offset=normalized_offset,
            verification_status=verification_status,
        )
        categories = {
            category.id: category
            for category in await self.categories.get_many(
                {category_id for professional in rows for category_id in professional.category_ids}
            )
        }
        accounts = await self.accounts.get_many({professional.id for professional in rows})
        now = self.clock.now()
        return AdminProfessionalListResult(
            items=[
                AdminProfessionalItem(
                    professional=professional,
                    categories=[
                        categories[category_id]
                        for category_id in professional.category_ids
                        if category_id in categories
                    ],
                    account=accounts.get(professional.id),
                    account_active=(
                        professional.id in accounts and accounts[professional.id].is_active(now)
                    ),
                )
                for professional in rows
            ],
            total=await self.professionals.count_admin(
                query=query, verification_status=verification_status
            ),
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


@dataclass(slots=True)
class ListAdminPurchases:
    """Todas las compras: quien compro que, cuando y por cuanto. Sin PII del cliente."""

    purchases: PurchaseRepositoryPort
    leads: LeadRepositoryPort
    categories: CategoryRepositoryPort
    professionals: ProfessionalRepositoryPort
    reviews: PurchaseReviewRepositoryPort

    timezone: str = BUSINESS_TIMEZONE

    async def execute(self, query: AdminPurchaseQuery) -> AdminPurchaseListResult:
        if query.from_day and query.to_day and query.from_day > query.to_day:
            raise ValidationError("La fecha inicial debe ser anterior a la final")
        zone = ZoneInfo(self.timezone)
        normalized = AdminPurchaseFilters(
            status=query.status,
            professional_id=query.professional_id,
            created_from=_day_start(query.from_day, zone) if query.from_day else None,
            # El dia final entra entero: el limite es la medianoche siguiente, exclusiva.
            created_to=(
                _day_start(query.to_day + timedelta(days=1), zone) if query.to_day else None
            ),
            limit=min(max(query.limit, 1), MAX_PAGE_SIZE),
            offset=max(query.offset, 0),
        )
        purchases = await self.purchases.list_admin(normalized)
        leads: dict[UUID, Lead | None] = {}
        professionals: dict[UUID, Professional | None] = {}
        for purchase in purchases:
            if purchase.lead_id not in leads:
                leads[purchase.lead_id] = await self.leads.get(purchase.lead_id)
            if purchase.professional_id not in professionals:
                professionals[purchase.professional_id] = await self.professionals.get(
                    purchase.professional_id
                )
        categories: dict[UUID, Category] = {
            category.id: category
            for category in await self.categories.get_many(
                {lead.category_id for lead in leads.values() if lead is not None}
            )
        }
        items: list[AdminPurchaseItem] = []
        for purchase in purchases:
            lead = leads[purchase.lead_id]
            items.append(
                AdminPurchaseItem(
                    purchase=purchase,
                    professional=professionals[purchase.professional_id],
                    review_count=len(await self.reviews.list_for_purchase(purchase.id)),
                    # Vista publica: el admin no necesita el contacto para auditar ventas.
                    lead=lead.public_view() if lead is not None else None,
                    category=categories.get(lead.category_id) if lead is not None else None,
                )
            )
        return AdminPurchaseListResult(
            items=items,
            total=await self.purchases.count_admin(normalized),
            limit=normalized.limit,
            offset=normalized.offset,
        )


@dataclass(slots=True)
class GetMetricsTimeseries:
    """Actividad diaria del marketplace para las graficas del dashboard.

    Los dias se cortan en la zona horaria del negocio, no en UTC: una compra a las
    00:30 de Madrid cuenta en ese dia aunque en UTC sea el anterior.
    """

    leads: LeadRepositoryPort
    purchases: PurchaseRepositoryPort
    ledger: CreditLedgerRepositoryPort
    clock: ClockPort
    timezone: str = BUSINESS_TIMEZONE

    async def execute(self, *, start: date | None, end: date | None) -> MetricsTimeseries:
        zone = ZoneInfo(self.timezone)
        last = end or self.clock.now().astimezone(zone).date()
        first = start or last - timedelta(days=DEFAULT_TIMESERIES_DAYS - 1)
        if first > last:
            raise ValidationError("La fecha inicial debe ser anterior a la final")
        if (last - first).days + 1 > MAX_TIMESERIES_DAYS:
            raise ValidationError(f"El rango maximo es de {MAX_TIMESERIES_DAYS} dias")
        range_start = _day_start(first, zone)
        range_end = _day_start(last + timedelta(days=1), zone)

        leads = {
            row.day: row
            for row in await self.leads.daily_created(
                start=range_start, end=range_end, tz=self.timezone
            )
        }
        paid = {
            row.day: row
            for row in await self.purchases.daily_paid(
                start=range_start, end=range_end, tz=self.timezone
            )
        }
        topups = {
            row.day: row
            for row in await self.ledger.daily_topups(
                start=range_start, end=range_end, tz=self.timezone
            )
        }
        points: list[DailyMetricsPoint] = []
        day = first
        while day <= last:
            lead_row, paid_row, topup_row = leads.get(day), paid.get(day), topups.get(day)
            points.append(
                DailyMetricsPoint(
                    day=day,
                    leads_created=lead_row.count if lead_row else 0,
                    paid_purchases=paid_row.count if paid_row else 0,
                    revenue_by_currency=dict(paid_row.amount_by_currency) if paid_row else {},
                    topups=topup_row.count if topup_row else 0,
                    topup_revenue_by_currency=(
                        dict(topup_row.amount_by_currency) if topup_row else {}
                    ),
                )
            )
            day += timedelta(days=1)
        return MetricsTimeseries(start=first, end=last, timezone=self.timezone, points=points)


def _day_start(day: date, zone: ZoneInfo) -> datetime:
    """Medianoche de `day` en `zone`, con zona: nunca un instante sin zona horaria."""
    return datetime.combine(day, time.min, tzinfo=zone)
