"""Repositorios de usuarios y perfiles profesionales."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.ports import ProfessionalRepositoryPort, UserRepositoryPort
from app.domain.exceptions import NotFoundError, ProfessionalNotFoundError
from app.domain.models import Professional, User
from app.infrastructure.adapters.db.mappers import (
    apply_professional,
    apply_user,
    professional_to_domain,
    user_to_domain,
)
from app.infrastructure.adapters.db.models import (
    ProfessionalCategoryRow,
    ProfessionalRow,
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

    async def list_admin(self, *, query: str | None, limit: int, offset: int) -> list[Professional]:
        stmt = (
            select(ProfessionalRow)
            .options(selectinload(ProfessionalRow.categories))
            .execution_options(populate_existing=True)
        )
        if query:
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    ProfessionalRow.business_name.ilike(pattern),
                    ProfessionalRow.city.ilike(pattern),
                    ProfessionalRow.province.ilike(pattern),
                )
            )
        stmt = stmt.order_by(ProfessionalRow.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [professional_to_domain(row) for row in rows]

    async def count_admin(self, *, query: str | None) -> int:
        stmt = select(func.count(ProfessionalRow.id))
        if query:
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    ProfessionalRow.business_name.ilike(pattern),
                    ProfessionalRow.city.ilike(pattern),
                    ProfessionalRow.province.ilike(pattern),
                )
            )
        return (await self._session.execute(stmt)).scalar_one()

    async def count_all(self) -> int:
        return (await self._session.execute(select(func.count(ProfessionalRow.id)))).scalar_one()

    async def get(self, professional_id: UUID) -> Professional | None:
        row = await self._load_row(ProfessionalRow.id == professional_id)
        return professional_to_domain(row) if row is not None else None

    async def get_by_user_id(self, user_id: UUID) -> Professional | None:
        row = await self._load_row(ProfessionalRow.user_id == user_id)
        return professional_to_domain(row) if row is not None else None

    async def _load_row(self, condition: ColumnElement[bool]) -> ProfessionalRow | None:
        """Carga el perfil con sus oficios resueltos.

        `populate_existing` fuerza a aplicar el eager load incluso si la instancia
        ya estaba en la sesion; sin el, leer `categories` provocaria IO perezosa.
        """
        stmt = (
            select(ProfessionalRow)
            .where(condition)
            .options(selectinload(ProfessionalRow.categories))
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
