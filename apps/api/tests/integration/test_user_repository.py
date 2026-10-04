"""Roles contra Postgres real: el bloqueo de admins, el directorio y la serie diaria."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.ports import AdminUserFilters
from app.application.use_cases import ChangeUserRole
from app.domain.exceptions import LastAdminError
from app.domain.models import Category, Lead, Professional, User, UserRole
from app.domain.value_objects import Email
from app.infrastructure.adapters.clock import SystemClock, Uuid4Generator
from app.infrastructure.adapters.db.repositories import (
    SqlAlchemyLeadRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.adapters.db.session import SqlAlchemyUnitOfWork
from tests.factories import make_lead

pytestmark = pytest.mark.integration


async def add_user(session: AsyncSession, email: str, role: UserRole) -> User:
    user = await SqlAlchemyUserRepository(session).add(
        User(
            id=uuid4(),
            firebase_uid=f"fb-{email}",
            email=Email(email),
            role=role,
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
    )
    await session.commit()
    return user


class SlowUserRepository(SqlAlchemyUserRepository):
    """Ensancha la ventana de carrera: espera tras bloquear la fila objetivo.

    Sin la pausa, la primera transaccion termina antes de que la segunda empiece y el
    test pasaria aunque `lock_admins` no bloqueara nada (comprobado quitando el
    `FOR UPDATE`).
    """

    async def get_for_update(self, user_id: UUID) -> User | None:
        user = await super().get_for_update(user_id)
        await asyncio.sleep(0.3)
        return user


async def test_two_admins_demoting_each_other_leave_one_admin(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    """Con Postgres real: `lock_admins` serializa las dos degradaciones.

    Bloqueando solo la fila objetivo, cada transaccion bloquearia una fila distinta,
    veria "queda el otro admin" y la plataforma se quedaria sin ninguno.
    """
    first = await add_user(session, "first@example.com", UserRole.ADMIN)
    second = await add_user(session, "second@example.com", UserRole.ADMIN)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def demote(target: UUID, actor: UUID) -> None:
        async with factory() as own:
            await ChangeUserRole(
                users=SlowUserRepository(own),
                clock=SystemClock(),
                ids=Uuid4Generator(),
                uow=SqlAlchemyUnitOfWork(own),
            ).execute(user_id=target, role=UserRole.PROFESSIONAL, actor_user_id=actor)

    results = await asyncio.wait_for(
        asyncio.gather(
            demote(second.id, first.id), demote(first.id, second.id), return_exceptions=True
        ),
        timeout=10,
    )

    assert sum(isinstance(result, LastAdminError) for result in results) == 1, results
    remaining = await SqlAlchemyUserRepository(session).list_admin(
        AdminUserFilters(role=UserRole.ADMIN)
    )
    assert len(remaining) == 1


async def test_directory_joins_profile_for_search_and_status(
    session: AsyncSession, madrid_carpenter: Professional
) -> None:
    users = SqlAlchemyUserRepository(session)
    await add_user(session, "admin@example.com", UserRole.ADMIN)

    by_business = await users.list_admin(AdminUserFilters(query=madrid_carpenter.business_name))
    pending = await users.count_admin(
        AdminUserFilters(verification_status=madrid_carpenter.verification_status)
    )

    assert [user.id for user in by_business] == [madrid_carpenter.user_id]
    assert pending == 1
    assert await users.count_admin(AdminUserFilters()) == 2
    assert (await users.get_by_email(" ADMIN@example.com ")) is not None


async def test_daily_counts_cut_days_in_madrid_time(
    session: AsyncSession, carpentry: Category
) -> None:
    """23:30 UTC del 28-feb son las 00:30 del 1-mar en Madrid: cuenta en marzo."""
    leads = SqlAlchemyLeadRepository(session)
    late_night = datetime(2026, 2, 28, 23, 30, tzinfo=UTC)
    lead: Lead = make_lead(category_id=carpentry.id, created_at=late_night)
    await leads.add(lead)
    await session.commit()

    rows = await leads.daily_created(
        start=late_night - timedelta(days=1), end=late_night + timedelta(days=1), tz="Europe/Madrid"
    )

    assert [(row.day, row.count) for row in rows] == [(date(2026, 3, 1), 1)]
