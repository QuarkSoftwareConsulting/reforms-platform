"""Repositorios de catalogo: categorias, codigos postales y eventos procesados."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Delete, delete, exists, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import (
    CategoryRepositoryPort,
    PostalCodeInfo,
    PostalCodeRepositoryPort,
    ProcessedEventRepositoryPort,
)
from app.domain.exceptions import (
    CatalogItemInUseError,
    CatalogSlugTakenError,
    CategoryNotFoundError,
)
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

FOREIGN_KEY_VIOLATION = "23503"
SLUG_CONSTRAINTS = frozenset({"uq_categories_slug", "uq_services_category_slug"})


def _driver_error(exc: IntegrityError) -> object:
    # asyncpg llega envuelto en el adaptador DBAPI de SQLAlchemy; su error va en la causa.
    return getattr(exc.orig, "__cause__", None) or exc.orig


def _sqlstate(exc: IntegrityError) -> str | None:
    value = getattr(_driver_error(exc), "sqlstate", None)
    return value if isinstance(value, str) else None


def _constraint_name(exc: IntegrityError) -> str | None:
    value = getattr(_driver_error(exc), "constraint_name", None)
    return value if isinstance(value, str) else None


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

    async def get_for_update(self, category_id: UUID) -> Category | None:
        # Bloqueo en una consulta propia y recarga despues, como con los perfiles: la
        # fila se lee ya con lo que confirmo quien tenia el bloqueo.
        locked = await self._session.execute(
            select(CategoryRow.id).where(CategoryRow.id == category_id).with_for_update()
        )
        if locked.scalar_one_or_none() is None:
            return None
        return await self.get(category_id)

    async def get_by_service(self, service_id: UUID) -> Category | None:
        stmt = select(CategoryRow).join(ServiceRow).where(ServiceRow.id == service_id)
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
        await self._flush()
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
        await self._delete_restricted(
            delete(ServiceRow).where(ServiceRow.category_id == category_id),
            delete(CategoryRow).where(CategoryRow.id == category_id),
        )

    async def delete_service(self, service_id: UUID) -> None:
        await self._delete_restricted(delete(ServiceRow).where(ServiceRow.id == service_id))

    async def _delete_restricted(self, *statements: Delete) -> None:
        """Borra lo que el caso de uso comprobo que nadie usa.

        Un lead que elige un servicio entre la comprobacion y el borrado no bloquea la
        categoria: lo para la clave foranea RESTRICT de `lead_services` y se responde
        lo mismo que si la comprobacion lo hubiera visto. Los oficios de un perfil
        (`professional_categories`) son CASCADE: a esos los cubre el bloqueo de
        `get_for_update`, que espera a que se confirme el perfil antes de comprobar.
        """
        try:
            for statement in statements:
                await self._session.execute(statement)
        except IntegrityError as exc:
            if _sqlstate(exc) == FOREIGN_KEY_VIOLATION:
                raise CatalogItemInUseError() from exc
            raise
        # Sin esto, la sesion seguiria devolviendo la fila borrada desde su cache.
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
            service_row.featured = service.featured
            service_row.image_key = service.image_key
            service_row.landing_name_es = service.landing_name_es
            service_row.landing_name_en = service.landing_name_en
        await self._flush()

    async def _flush(self) -> None:
        """Escribe ya, para que un slug repetido llegue como su error y no como un 500.

        El caso de uso compara el slug con lo que leyo; dos altas simultaneas con el
        mismo nombre pasan las dos esa comprobacion y solo la restriccion unica las ve.
        """
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if _constraint_name(exc) in SLUG_CONSTRAINTS:
                raise CatalogSlugTakenError() from exc
            raise


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
