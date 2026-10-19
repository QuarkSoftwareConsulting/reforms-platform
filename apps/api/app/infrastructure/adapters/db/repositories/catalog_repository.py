"""Repositorios de catalogo: categorias, codigos postales y eventos procesados."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import (
    CategoryRepositoryPort,
    PostalCodeInfo,
    PostalCodeRepositoryPort,
    ProcessedEventRepositoryPort,
)
from app.domain.exceptions import CategoryNotFoundError
from app.domain.models import Category, Service
from app.domain.value_objects import PostalCode
from app.infrastructure.adapters.db.mappers import (
    apply_category,
    category_to_domain,
    postal_code_to_domain,
)
from app.infrastructure.adapters.db.models import (
    CategoryRow,
    LeadRow,
    LeadServiceRow,
    PostalCodeRow,
    ProcessedPaymentEventRow,
    ProfessionalCategoryRow,
    ProfessionalServiceRow,
    ServiceRow,
)


class SqlAlchemyCategoryRepository(CategoryRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[Category]:
        # El orden lo fija el catalogo (el del documento del cliente), no el alfabeto.
        stmt = (
            select(CategoryRow)
            .where(CategoryRow.active.is_(True))
            .order_by(CategoryRow.sort_order, CategoryRow.name_es)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [category_to_domain(row) for row in rows]

    async def list_all(self) -> list[Category]:
        stmt = select(CategoryRow).order_by(CategoryRow.sort_order, CategoryRow.name_es)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [category_to_domain(row) for row in rows]

    async def get(self, category_id: UUID) -> Category | None:
        row = await self._load_row(category_id)
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

    async def add(self, category: Category) -> Category:
        row = CategoryRow(id=category.id, services=[])
        apply_category(row, category)
        self._session.add(row)
        await self._session.flush()
        await self._sync_services(row, category.services)
        return category

    async def update(self, category: Category) -> Category:
        row = await self._load_row(category.id)
        if row is None:
            raise CategoryNotFoundError()
        apply_category(row, category)
        await self._sync_services(row, category.services)
        return category

    async def delete(self, category_id: UUID) -> None:
        # Los servicios primero: su clave foranea es RESTRICT.
        await self._session.execute(delete(ServiceRow).where(ServiceRow.category_id == category_id))
        await self._session.execute(delete(CategoryRow).where(CategoryRow.id == category_id))
        # Sin esto, la sesion seguiria devolviendo la fila borrada desde su cache.
        self._session.expire_all()

    async def delete_service(self, service_id: UUID) -> None:
        await self._session.execute(delete(ServiceRow).where(ServiceRow.id == service_id))
        self._session.expire_all()

    async def is_in_use(self, category_id: UUID) -> bool:
        service_ids = select(ServiceRow.id).where(ServiceRow.category_id == category_id)
        stmt = select(
            or_(
                exists().where(LeadRow.category_id == category_id),
                exists().where(ProfessionalCategoryRow.category_id == category_id),
                exists().where(LeadServiceRow.service_id.in_(service_ids)),
                exists().where(ProfessionalServiceRow.service_id.in_(service_ids)),
            )
        )
        return bool((await self._session.execute(stmt)).scalar())

    async def is_service_in_use(self, service_id: UUID) -> bool:
        stmt = select(
            or_(
                exists().where(LeadServiceRow.service_id == service_id),
                exists().where(ProfessionalServiceRow.service_id == service_id),
            )
        )
        return bool((await self._session.execute(stmt)).scalar())

    async def _load_row(self, category_id: UUID) -> CategoryRow | None:
        # `session.get` devolveria la fila cacheada sin recargar sus servicios (AGENTS.md).
        stmt = (
            select(CategoryRow)
            .where(CategoryRow.id == category_id)
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _sync_services(self, row: CategoryRow, services: list[Service]) -> None:
        """Crea los servicios nuevos y actualiza los existentes; no borra ninguno."""
        by_id = {service_row.id: service_row for service_row in row.services}
        for service in services:
            service_row = by_id.get(service.id)
            if service_row is None:
                service_row = ServiceRow(id=service.id, category_id=row.id, slug=service.slug)
                self._session.add(service_row)
            service_row.name_es = service.name_es
            service_row.name_en = service.name_en
            service_row.sort_order = service.sort_order
            service_row.active = service.active
        await self._session.flush()


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
