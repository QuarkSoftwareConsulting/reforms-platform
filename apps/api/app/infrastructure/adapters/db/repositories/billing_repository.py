"""Repositorios de la mensualidad: cuentas, libro de saldo e historial de precios."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import (
    CreditLedgerRepositoryPort,
    ProfessionalAccountRepositoryPort,
    SubscriptionPriceRepositoryPort,
)
from app.domain.exceptions import ProfessionalAccountNotFoundError
from app.domain.models import (
    RENEWAL_GRACE,
    CreditEntry,
    CreditEntryKind,
    ProfessionalAccount,
    SubscriptionPrice,
    SubscriptionStatus,
)
from app.infrastructure.adapters.db.mappers import (
    account_to_domain,
    apply_account,
    credit_entry_to_domain,
    subscription_price_to_domain,
)
from app.infrastructure.adapters.db.models import (
    CreditEntryRow,
    ProfessionalAccountRow,
    SubscriptionPriceRow,
)


class SqlAlchemyProfessionalAccountRepository(ProfessionalAccountRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, account: ProfessionalAccount) -> ProfessionalAccount:
        row = ProfessionalAccountRow(professional_id=account.professional_id)
        apply_account(row, account)
        self._session.add(row)
        await self._session.flush()
        return account

    async def update(self, account: ProfessionalAccount) -> ProfessionalAccount:
        row = await self._session.get(ProfessionalAccountRow, account.professional_id)
        if row is None:
            raise ProfessionalAccountNotFoundError()
        apply_account(row, account)
        await self._session.flush()
        return account

    async def get(self, professional_id: UUID) -> ProfessionalAccount | None:
        # `populate_existing`: si la fila ya esta en la sesion (p. ej. tras un
        # bloqueo anterior en la misma peticion) se relee de la BD en vez de
        # devolver el saldo cacheado.
        stmt = (
            select(ProfessionalAccountRow)
            .where(ProfessionalAccountRow.professional_id == professional_id)
            .execution_options(populate_existing=True)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return account_to_domain(row) if row is not None else None

    async def get_for_update(self, professional_id: UUID) -> ProfessionalAccount | None:
        stmt = (
            select(ProfessionalAccountRow)
            .where(ProfessionalAccountRow.professional_id == professional_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return account_to_domain(row) if row is not None else None

    async def get_by_customer_for_update(self, customer_id: str) -> ProfessionalAccount | None:
        stmt = (
            select(ProfessionalAccountRow)
            .where(ProfessionalAccountRow.stripe_customer_id == customer_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return account_to_domain(row) if row is not None else None

    async def get_many(self, professional_ids: set[UUID]) -> dict[UUID, ProfessionalAccount]:
        if not professional_ids:
            return {}
        stmt = select(ProfessionalAccountRow).where(
            ProfessionalAccountRow.professional_id.in_(professional_ids)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {row.professional_id: account_to_domain(row) for row in rows}

    async def count_active(self, *, now: datetime) -> int:
        # Misma regla que `ProfessionalAccount.is_active`, expresada en SQL.
        stmt = select(func.count()).where(
            ProfessionalAccountRow.subscription_status == SubscriptionStatus.ACTIVE,
            or_(
                ProfessionalAccountRow.current_period_end.is_(None),
                ProfessionalAccountRow.current_period_end > now - RENEWAL_GRACE,
            ),
        )
        return (await self._session.execute(stmt)).scalar_one()


class SqlAlchemyCreditLedgerRepository(CreditLedgerRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_if_absent(self, entry: CreditEntry) -> bool:
        """Inserta el movimiento; la restriccion unica (kind, source_ref) hace de cerrojo.

        Igual que `processed_payment_events`: si dos transacciones intentan abonar la
        misma factura, solo una inserta fila y solo esa toca el saldo.
        """
        stmt = (
            insert(CreditEntryRow)
            .values(
                id=entry.id,
                professional_id=entry.professional_id,
                kind=entry.kind,
                amount_cents=entry.amount.amount_cents,
                currency=entry.amount.currency,
                source_ref=entry.source_ref,
                note=entry.note,
                created_by_user_id=entry.created_by_user_id,
                created_at=entry.created_at,
            )
            .on_conflict_do_nothing(constraint="uq_credit_entries_kind_source_ref")
            .returning(CreditEntryRow.id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_for_professional(
        self, professional_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[CreditEntry]:
        stmt = (
            select(CreditEntryRow)
            .where(CreditEntryRow.professional_id == professional_id)
            .order_by(CreditEntryRow.created_at.desc(), CreditEntryRow.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [credit_entry_to_domain(row) for row in rows]

    async def latest_topup(self, professional_id: UUID) -> CreditEntry | None:
        stmt = (
            select(CreditEntryRow)
            .where(
                CreditEntryRow.professional_id == professional_id,
                CreditEntryRow.kind == CreditEntryKind.TOPUP,
            )
            .order_by(CreditEntryRow.created_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return credit_entry_to_domain(row) if row is not None else None

    async def first_topup(self, professional_id: UUID) -> CreditEntry | None:
        stmt = (
            select(CreditEntryRow)
            .where(
                CreditEntryRow.professional_id == professional_id,
                CreditEntryRow.kind == CreditEntryKind.TOPUP,
            )
            .order_by(CreditEntryRow.created_at.asc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return credit_entry_to_domain(row) if row is not None else None

    async def topup_totals(self) -> dict[str, int]:
        stmt = (
            select(CreditEntryRow.currency, func.sum(CreditEntryRow.amount_cents))
            .where(CreditEntryRow.kind == CreditEntryKind.TOPUP)
            .group_by(CreditEntryRow.currency)
        )
        rows = (await self._session.execute(stmt)).all()
        return {currency: int(total) for currency, total in rows}


class SqlAlchemySubscriptionPriceRepository(SubscriptionPriceRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, price: SubscriptionPrice) -> SubscriptionPrice:
        self._session.add(
            SubscriptionPriceRow(
                id=price.id,
                amount_cents=price.amount.amount_cents,
                currency=price.amount.currency,
                stripe_price_id=price.stripe_price_id,
                created_by_user_id=price.created_by_user_id,
                created_at=price.created_at,
            )
        )
        await self._session.flush()
        return price

    async def current(self) -> SubscriptionPrice | None:
        stmt = (
            select(SubscriptionPriceRow).order_by(SubscriptionPriceRow.created_at.desc()).limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return subscription_price_to_domain(row) if row is not None else None
