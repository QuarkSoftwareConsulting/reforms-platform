"""Cliente HTTP de test contra la app real.

Sustituye solo los tres adaptadores que salen de la maquina — Firebase, Stripe y
S3 — y deja el resto del sistema intacto: rutas, middlewares, casos de uso,
repositorios y Postgres. Asi los tests ejercitan el mismo camino que produccion.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.application.ports import AuthenticatedIdentity
from app.config import Settings
from app.domain.models import Category, Service
from app.domain.value_objects import Coordinates, Money
from app.infrastructure.adapters.clock import Uuid4Generator
from app.infrastructure.adapters.db.models import Base, CategoryRow, PostalCodeRow, ServiceRow
from app.infrastructure.api.dependencies import Infrastructure
from app.main import create_app
from tests.factories import BARCELONA, MADRID
from tests.fakes import (
    FakeClock,
    FakePaymentGateway,
    FakePhoneVerifier,
    FakeStorage,
    FakeTokenVerifier,
)

pytestmark = pytest.mark.integration

TRUNCATE_ORDER = (
    "processed_payment_events",
    "rate_limit_counters",
    "credit_entries",
    "professional_accounts",
    "subscription_prices",
    "purchase_reviews",
    "lead_purchases",
    "lead_consents",
    "lead_photos",
    "lead_services",
    "leads",
    "professional_categories",
    "professional_services",
    "professional_documents",
    "professional_work_photos",
    "professional_verification_events",
    "professionals",
    "user_role_events",
    "users",
    "services",
    "categories",
)

SEED_POSTAL_CODES = (
    ("28001", "Madrid", "Madrid", MADRID),
    ("28801", "Alcala de Henares", "Madrid", Coordinates(40.4818, -3.3644)),
    ("08001", "Barcelona", "Barcelona", BARCELONA),
)

CARPENTRY_SERVICES = (
    ("puertas", "Puertas", "Doors"),
    ("armarios", "Armarios a medida", "Fitted wardrobes"),
)

PRO_TOKEN = "token-profesional"
ADMIN_TOKEN = "token-admin"
PRO_UID = "fb-uid-professional"
ADMIN_UID = "fb-uid-admin"


@pytest.fixture(scope="session")
def api_settings() -> Settings:
    settings = Settings(environment="test")
    # La app de test apunta a la BD de integracion, no a la de desarrollo.
    settings.database_url = settings.test_database_url
    # Mensualidad inicial fija para no depender del .env de desarrollo.
    settings.stripe_topup_price_id = "price_test_config"
    settings.subscription_topup_cents = 1800
    return settings


@pytest_asyncio.fixture(scope="session")
async def api_engine(api_settings: Settings) -> AsyncIterator[AsyncEngine]:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(api_settings.database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # pragma: no cover
        await engine.dispose()
        pytest.skip(
            "Base de datos de test no disponible. Levantala con:\n"
            "  docker compose -f infra/docker-compose.yml up -d db-test\n"
            f"Detalle: {exc}"
        )
    yield engine
    await engine.dispose()


@pytest.fixture
def fake_gateway() -> FakePaymentGateway:
    return FakePaymentGateway()


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC))


@pytest.fixture
def fake_tokens() -> FakeTokenVerifier:
    return FakeTokenVerifier(
        {
            PRO_TOKEN: AuthenticatedIdentity(
                provider_uid=PRO_UID,
                email="pro@example.com",
                email_verified=True,
                display_name="Carpinteria Lopez",
            ),
            ADMIN_TOKEN: AuthenticatedIdentity(
                provider_uid=ADMIN_UID,
                email="admin@example.com",
                email_verified=True,
                is_admin_claim=True,
            ),
        }
    )


@pytest.fixture
def fake_phone_verifier() -> FakePhoneVerifier:
    return FakePhoneVerifier()


@pytest.fixture
def private_storage() -> FakeStorage:
    return FakeStorage(base_url="https://private.test/reforma-hub")


@pytest_asyncio.fixture
async def api(
    request: pytest.FixtureRequest,
    api_engine: AsyncEngine,
    api_settings: Settings,
    fake_gateway: FakePaymentGateway,
    fake_clock: FakeClock,
    fake_tokens: FakeTokenVerifier,
    fake_phone_verifier: FakePhoneVerifier,
    private_storage: FakeStorage,
) -> AsyncIterator[AsyncClient]:
    session_factory = async_sessionmaker(api_engine, expire_on_commit=False, autoflush=False)

    async with session_factory() as setup:
        await setup.execute(text(f"TRUNCATE {', '.join(TRUNCATE_ORDER)} RESTART IDENTITY CASCADE"))
        for code, city, province, point in SEED_POSTAL_CODES:
            await setup.merge(
                PostalCodeRow(
                    code=code,
                    country="ES",
                    city=city,
                    province=province,
                    location=f"SRID=4326;POINT({point.longitude} {point.latitude})",
                )
            )
        await setup.commit()

    app = create_app(api_settings)
    app.state.infrastructure = Infrastructure(
        settings=api_settings,
        engine=api_engine,
        session_factory=session_factory,
        payments=fake_gateway,
        storage=FakeStorage(),
        document_storage=private_storage,
        token_verifier=fake_tokens,
        clock=fake_clock,
        ids=Uuid4Generator(),
        # Como en produccion hoy, sin SMS; los tests marcados con `sms` lo activan.
        phone_verifier=(
            fake_phone_verifier if request.node.get_closest_marker("sms") is not None else None
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver/api/v1") as client:
        yield client


@pytest_asyncio.fixture
async def carpentry_category(api_engine: AsyncEngine, api: AsyncClient) -> Category:
    factory = async_sessionmaker(api_engine, expire_on_commit=False)
    row = CategoryRow(
        id=uuid4(),
        slug="carpinteria",
        name_es="Carpinteria",
        name_en="Carpentry",
        suggested_lead_price_cents=500,
        currency="EUR",
        active=True,
    )
    services = [
        ServiceRow(
            id=uuid4(),
            category_id=row.id,
            slug=slug,
            name_es=name_es,
            name_en=name_en,
            sort_order=index,
            active=True,
        )
        for index, (slug, name_es, name_en) in enumerate(CARPENTRY_SERVICES)
    ]
    async with factory() as session:
        session.add(row)
        await session.flush()
        session.add_all(services)
        await session.commit()
    return Category(
        id=row.id,
        slug=row.slug,
        name_es=row.name_es,
        name_en=row.name_en,
        suggested_lead_price=Money(row.suggested_lead_price_cents, row.currency),
        services=[
            Service(id=s.id, slug=s.slug, name_es=s.name_es, name_en=s.name_en, sort_order=i)
            for i, s in enumerate(services)
        ],
    )


@pytest.fixture
def pro_auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {PRO_TOKEN}"}


@pytest.fixture
def admin_auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}
