"""Repositorios de usuarios y perfiles profesionales."""

from __future__ import annotations

from typing import TypeVar
from uuid import UUID

from sqlalchemy import ColumnElement, Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.ports import ProfessionalRepositoryPort, UserRepositoryPort
from app.domain.exceptions import NotFoundError, ProfessionalNotFoundError
from app.domain.models import Professional, User, VerificationEvent, VerificationStatus
from app.infrastructure.adapters.db.mappers import (
    apply_professional,
    apply_user,
    professional_to_domain,
    user_to_domain,
    verification_event_to_domain,
)
from app.infrastructure.adapters.db.models import (
    ProfessionalCategoryRow,
    ProfessionalRow,
    ProfessionalVerificationEventRow,
    UserRow,
)


class SqlAlchemyUserRepository(UserRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> User:
        row = UserRow(id=user.id)
        apply_user(row, user)
        self._session.add(row)
        await self._session.flush()
        return user

    async def get(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserRow, user_id)
        return user_to_domain(row) if row is not None else None

    async def get_by_firebase_uid(self, firebase_uid: str) -> User | None:
        stmt = select(UserRow).where(UserRow.firebase_uid == firebase_uid)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return user_to_domain(row) if row is not None else None

    async def update(self, user: User) -> User:
        row = await self._session.get(UserRow, user.id)
        if row is None:
            raise NotFoundError("El usuario no existe")
        apply_user(row, user)
        await self._session.flush()
        return user


T = TypeVar("T", bound=tuple[object, ...])

# Todo lo que lee el mapeo a dominio: cargado de antemano para no caer en la carga
# perezosa, que en async falla con MissingGreenlet.
_PROFESSIONAL_RELATIONS = (
    selectinload(ProfessionalRow.categories),
    selectinload(ProfessionalRow.services),
    selectinload(ProfessionalRow.work_photos),
    selectinload(ProfessionalRow.documents),
)


class SqlAlchemyProfessionalRepository(ProfessionalRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, professional: Professional) -> Professional:
        row = ProfessionalRow(id=professional.id)
        apply_professional(row, professional)
        self._session.add(row)
        await self._session.flush()
        await self._replace_categories(professional)
        return professional

    async def update(self, professional: Professional) -> Professional:
        row = await self._load_row(ProfessionalRow.id == professional.id)
        if row is None:
            raise ProfessionalNotFoundError()
        apply_professional(row, professional)
        await self._session.flush()
        await self._replace_categories(professional)
        return professional

    def _admin_filters(
        self, stmt: Select[T], query: str | None, verification_status: VerificationStatus | None
    ) -> Select[T]:
        if query:
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    ProfessionalRow.business_name.ilike(pattern),
                    ProfessionalRow.legal_name.ilike(pattern),
                    ProfessionalRow.city.ilike(pattern),
                    ProfessionalRow.province.ilike(pattern),
                )
            )
        if verification_status is not None:
            stmt = stmt.where(ProfessionalRow.verification_status == verification_status)
        return stmt

    async def list_admin(
        self,
        *,
        query: str | None,
        limit: int,
        offset: int,
        verification_status: VerificationStatus | None = None,
    ) -> list[Professional]:
        stmt = self._admin_filters(
            select(ProfessionalRow).options(*_PROFESSIONAL_RELATIONS),
            query,
            verification_status,
        ).execution_options(populate_existing=True)
        # La cola de validacion se atiende por orden de llegada; el resto, lo reciente.
        order = (
            ProfessionalRow.submitted_at.asc()
            if verification_status is VerificationStatus.PENDING
            else ProfessionalRow.created_at.desc()
        )
        stmt = stmt.order_by(order).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [professional_to_domain(row) for row in rows]

    async def count_admin(
        self, *, query: str | None, verification_status: VerificationStatus | None = None
    ) -> int:
        stmt = self._admin_filters(
            select(func.count(ProfessionalRow.id)), query, verification_status
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def add_verification_event(self, event: VerificationEvent) -> None:
        self._session.add(
            ProfessionalVerificationEventRow(
                id=event.id,
                professional_id=event.professional_id,
                from_status=event.from_status,
                to_status=event.to_status,
                actor_user_id=event.actor_user_id,
                note=event.note,
                created_at=event.created_at,
            )
        )
        await self._session.flush()

    async def list_verification_events(self, professional_id: UUID) -> list[VerificationEvent]:
        stmt = (
            select(ProfessionalVerificationEventRow)
            .where(ProfessionalVerificationEventRow.professional_id == professional_id)
            .order_by(ProfessionalVerificationEventRow.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [verification_event_to_domain(row) for row in rows]

    async def count_all(self) -> int:
        return (await self._session.execute(select(func.count(ProfessionalRow.id)))).scalar_one()

    async def get(self, professional_id: UUID) -> Professional | None:
        row = await self._load_row(ProfessionalRow.id == professional_id)
        return professional_to_domain(row) if row is not None else None

    async def get_by_user_id(self, user_id: UUID) -> Professional | None:
        row = await self._load_row(ProfessionalRow.user_id == user_id)
        return professional_to_domain(row) if row is not None else None

    async def get_for_update(self, professional_id: UUID) -> Professional | None:
        # El bloqueo va en una consulta propia: Postgres no admite FOR UPDATE junto a
        # los OUTER JOIN que podria generar la carga de relaciones.
        locked = await self._session.execute(
            select(ProfessionalRow.id)
            .where(ProfessionalRow.id == professional_id)
            .with_for_update()
        )
        if locked.scalar_one_or_none() is None:
            return None
        return await self.get(professional_id)

    async def _load_row(self, condition: ColumnElement[bool]) -> ProfessionalRow | None:
        """Carga el perfil con sus oficios resueltos.

        `populate_existing` fuerza a aplicar el eager load incluso si la instancia
        ya estaba en la sesion; sin el, leer `categories` provocaria IO perezosa.
        """
        stmt = (
            select(ProfessionalRow)
            .where(condition)
            .options(*_PROFESSIONAL_RELATIONS)
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _replace_categories(self, professional: Professional) -> None:
        """Reescribe la tabla puente de oficios.

        Borrar e insertar es mas simple y barato que diferenciar conjuntos: son
        como maximo una decena de filas por profesional.
        """
        await self._session.execute(
            delete(ProfessionalCategoryRow).where(
                ProfessionalCategoryRow.professional_id == professional.id
            )
        )
        for category_id in professional.category_ids:
            self._session.add(
                ProfessionalCategoryRow(professional_id=professional.id, category_id=category_id)
            )
        await self._session.flush()
