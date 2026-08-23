"""Repositorios de catalogo: categorias, codigos postales y eventos procesados."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import (
    CategoryRepositoryPort,
    PostalCodeInfo,
    PostalCodeRepositoryPort,
    ProcessedEventRepositoryPort,
)
from app.domain.models import Category
from app.domain.value_objects import PostalCode
from app.infrastructure.adapters.db.mappers import category_to_domain, postal_code_to_domain
from app.infrastructure.adapters.db.models import (
    CategoryRow,
    PostalCodeRow,
    ProcessedPaymentEventRow,
)


class SqlAlchemyCategoryRepository(CategoryRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[Category]:
        stmt = select(CategoryRow).where(CategoryRow.active.is_(True)).order_by(CategoryRow.name_es)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [category_to_domain(row) for row in rows]

    async def get(self, category_id: UUID) -> Category | None:
        row = await self._session.get(CategoryRow, category_id)
        return category_to_domain(row) if row is not None else None

    async def get_by_slug(self, slug: str) -> Category | None:
        stmt = select(CategoryRow).where(CategoryRow.slug == slug)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return category_to_domain(row) if row is not None else None

    async def get_many(self, category_ids: set[UUID]) -> list[Category]:
        if not category_ids:
            return []
        stmt = select(CategoryRow).where(CategoryRow.id.in_(category_ids))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [category_to_domain(row) for row in rows]


class SqlAlchemyPostalCodeRepository(PostalCodeRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, code: PostalCode) -> PostalCodeInfo | None:
        row = await self._session.get(PostalCodeRow, code.value)
        return postal_code_to_domain(row) if row is not None else None


class SqlAlchemyProcessedEventRepository(ProcessedEventRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def mark_processed(
        self, event_id: str, event_type: str, payload: dict[str, object]
    ) -> bool:
        """Inserta el evento y dice si es nuevo.

        `ON CONFLICT DO NOTHING` deja que la clave primaria haga de cerrojo: si dos
        entregas del mismo evento llegan en paralelo, solo una inserta fila y solo
        esa procesa el pago.
        """
        stmt = (
            insert(ProcessedPaymentEventRow)
            .values(event_id=event_id, event_type=event_type, payload=payload)
            .on_conflict_do_nothing(index_elements=[ProcessedPaymentEventRow.event_id])
            .returning(ProcessedPaymentEventRow.event_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
