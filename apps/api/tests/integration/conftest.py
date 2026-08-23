"""Fixtures de integracion: Postgres + PostGIS de verdad.

Usa la base `db-test` de docker-compose (puerto 5434, datos en tmpfs). Si no esta
levantada, los tests se omiten con un mensaje claro en vez de fallar en cascada.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.domain.models import Category, Professional, User, UserRole
from app.domain.value_objects import Coordinates, Email, Money, PhoneNumber, PostalCode
from app.infrastructure.adapters.db.models import Base, PostalCodeRow
from app.infrastructure.adapters.db.repositories import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyPostalCodeRepository,
    SqlAlchemyProcessedEventRepository,
    SqlAlchemyProfessionalRepository,
    SqlAlchemyPurchaseRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.adapters.db.session import SqlAlchemyUnitOfWork
from tests.factories import BARCELONA, MADRID

pytestmark = pytest.mark.integration

# Tablas a vaciar entre tests, en orden inverso de dependencias.
TRUNCATE_ORDER = (
    "processed_payment_events",
    "lead_purchases",
    "lead_consents",
    "lead_photos",
    "leads",
    "professional_categories",
    "professionals",
    "users",
    "categories",
)

SEED_POSTAL_CODES = (
    ("28001", "Madrid", "Madrid", MADRID),
    ("28801", "Alcala de Henares", "Madrid", Coordinates(40.4818, -3.3644)),
    ("08001", "Barcelona", "Barcelona", BARCELONA),
)


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    engine = create_async_engine(settings.test_database_url, poolclass=None)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # pragma: no cover - entorno sin la BD de test
        await engine.dispose()
        pytest.skip(
            "Base de datos de test no disponible. Levantala con:\n"
            "  docker compose -f infra/docker-compose.yml up -d db-test\n"
            f"Detalle: {exc}"
        )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        await session.execute(
            text(f"TRUNCATE {', '.join(TRUNCATE_ORDER)} RESTART IDENTITY CASCADE")
        )
        for code, city, province, point in SEED_POSTAL_CODES:
            await session.merge(
                PostalCodeRow(
                    code=code,
                    country="ES",
                    city=city,
                    province=province,
                    location=f"SRID=4326;POINT({point.longitude} {point.latitude})",
                )
            )
        await session.commit()
        yield session
        await session.rollback()


@pytest.fixture
def repos(session: AsyncSession) -> dict[str, object]:
    return {
        "leads": SqlAlchemyLeadRepository(session),
        "purchases": SqlAlchemyPurchaseRepository(session),
        "users": SqlAlchemyUserRepository(session),
        "professionals": SqlAlchemyProfessionalRepository(session),
        "categories": SqlAlchemyCategoryRepository(session),
        "postal_codes": SqlAlchemyPostalCodeRepository(session),
        "events": SqlAlchemyProcessedEventRepository(session),
        "uow": SqlAlchemyUnitOfWork(session),
    }


@pytest_asyncio.fixture
async def carpentry(session: AsyncSession) -> Category:
    from app.infrastructure.adapters.db.models import CategoryRow

    row = CategoryRow(
        id=uuid4(),
        slug="carpinteria",
        name_es="Carpinteria",
        name_en="Carpentry",
        lead_price_cents=500,
        currency="EUR",
        active=True,
    )
    session.add(row)
    await session.commit()
    return Category(
        id=row.id,
        slug=row.slug,
        name_es=row.name_es,
        name_en=row.name_en,
        lead_price=Money(row.lead_price_cents, row.currency),
    )


@pytest_asyncio.fixture
async def madrid_carpenter(session: AsyncSession, carpentry: Category) -> Professional:
    users = SqlAlchemyUserRepository(session)
    professionals = SqlAlchemyProfessionalRepository(session)

    user = await users.add(
        User(
            id=uuid4(),
            firebase_uid=f"fb-{uuid4().hex[:8]}",
            email=Email("pro@example.com"),
            role=UserRole.PROFESSIONAL,
            created_at=datetime.now(UTC),
        )
    )
    professional = await professionals.add(
        Professional(
            id=uuid4(),
            user_id=user.id,
            business_name="Carpinteria Lopez",
            phone=PhoneNumber("+34600111222"),
            base_postal_code=PostalCode("28001"),
            base_coordinates=MADRID,
            service_radius_km=25,
            created_at=datetime.now(UTC),
            city="Madrid",
            province="Madrid",
            category_ids={carpentry.id},
        )
    )
    await session.commit()
    return professional
