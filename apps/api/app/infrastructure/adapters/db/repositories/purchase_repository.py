"""Repositorio de compras: es donde se cuentan las plazas de cada lead."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import PaidPurchaseMetrics, PurchaseRepositoryPort
from app.domain.exceptions import PurchaseNotFoundError
from app.domain.models import Purchase, PurchaseStatus
from app.infrastructure.adapters.db.mappers import apply_purchase, purchase_to_domain
from app.infrastructure.adapters.db.models import LeadPurchaseRow

# Estados que consumen una plaza del lead: la venta cerrada, la reembolsada (el
# dato ya se cedio) y la reserva que aun no ha caducado.
SLOT_OCCUPYING_STATUSES = (
    PurchaseStatus.PAID,
    PurchaseStatus.REFUNDED,
    PurchaseStatus.RESERVED,
)


class SqlAlchemyPurchaseRepository(PurchaseRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, purchase: Purchase) -> Purchase:
        row = LeadPurchaseRow(id=purchase.id)
        apply_purchase(row, purchase)
        self._session.add(row)
        await self._session.flush()
        return purchase

    async def update(self, purchase: Purchase) -> Purchase:
        row = await self._session.get(LeadPurchaseRow, purchase.id)
        if row is None:
            raise PurchaseNotFoundError()
        apply_purchase(row, purchase)
        await self._session.flush()
        return purchase

    async def get(self, purchase_id: UUID) -> Purchase | None:
        row = await self._session.get(LeadPurchaseRow, purchase_id)
        return purchase_to_domain(row) if row is not None else None

    async def get_by_checkout_session(self, session_id: str) -> Purchase | None:
        stmt = select(LeadPurchaseRow).where(
            LeadPurchaseRow.stripe_checkout_session_id == session_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return purchase_to_domain(row) if row is not None else None

    def _occupying_slot_clause(self, now: datetime) -> ColumnElement[bool]:
        """Una reserva solo ocupa plaza mientras su TTL siga vigente."""
        return or_(
            LeadPurchaseRow.status.in_([PurchaseStatus.PAID, PurchaseStatus.REFUNDED]),
            (LeadPurchaseRow.status == PurchaseStatus.RESERVED)
            & (LeadPurchaseRow.reserved_until.is_(None) | (LeadPurchaseRow.reserved_until > now)),
        )

    async def count_occupied_slots(self, lead_id: UUID, *, now: datetime) -> int:
        stmt = (
            select(func.count(LeadPurchaseRow.id))
            .where(LeadPurchaseRow.lead_id == lead_id)
            .where(self._occupying_slot_clause(now))
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def find_active_for_lead_and_professional(
        self, lead_id: UUID, professional_id: UUID, *, now: datetime
    ) -> Purchase | None:
        stmt = (
            select(LeadPurchaseRow)
            .where(
                LeadPurchaseRow.lead_id == lead_id,
                LeadPurchaseRow.professional_id == professional_id,
            )
            .where(self._occupying_slot_clause(now))
            .order_by(LeadPurchaseRow.created_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return purchase_to_domain(row) if row is not None else None

    async def list_for_professional(
        self, professional_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Purchase]:
        stmt = (
            select(LeadPurchaseRow)
            .where(LeadPurchaseRow.professional_id == professional_id)
            .order_by(LeadPurchaseRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [purchase_to_domain(row) for row in rows]

    async def list_expired_reservations(self, *, now: datetime, limit: int = 100) -> list[Purchase]:
        stmt = (
            select(LeadPurchaseRow)
            .where(
                LeadPurchaseRow.status == PurchaseStatus.RESERVED,
                LeadPurchaseRow.reserved_until.is_not(None),
                LeadPurchaseRow.reserved_until <= now,
            )
            .order_by(LeadPurchaseRow.reserved_until)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [purchase_to_domain(row) for row in rows]

    async def has_paid_purchase(self, lead_id: UUID, professional_id: UUID) -> bool:
        stmt = select(
            select(LeadPurchaseRow.id)
            .where(
                LeadPurchaseRow.lead_id == lead_id,
                LeadPurchaseRow.professional_id == professional_id,
                LeadPurchaseRow.status == PurchaseStatus.PAID,
            )
            .exists()
        )
        return bool((await self._session.execute(stmt)).scalar())

    async def list_for_lead(
        self, lead_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Purchase]:
        stmt = (
            select(LeadPurchaseRow)
            .where(LeadPurchaseRow.lead_id == lead_id)
            .order_by(LeadPurchaseRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [purchase_to_domain(row) for row in rows]

    async def paid_metrics(self) -> PaidPurchaseMetrics:
        base = LeadPurchaseRow.status == PurchaseStatus.PAID
        count_stmt = select(
            func.count(LeadPurchaseRow.id), func.count(func.distinct(LeadPurchaseRow.lead_id))
        ).where(base)
        count_row = (await self._session.execute(count_stmt)).one()
        revenue_stmt = (
            select(LeadPurchaseRow.currency, func.sum(LeadPurchaseRow.amount_cents))
            .where(base)
            .group_by(LeadPurchaseRow.currency)
        )
        revenue_rows = (await self._session.execute(revenue_stmt)).all()
        return PaidPurchaseMetrics(
            count=int(count_row[0] or 0),
            lead_count=int(count_row[1] or 0),
            revenue_by_currency={currency: int(amount) for currency, amount in revenue_rows},
        )
