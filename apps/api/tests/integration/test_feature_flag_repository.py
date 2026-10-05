"""Feature flags contra Postgres, escritas con SQL como se haran a mano."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import FeatureFlag, FlagEnvironment
from app.infrastructure.adapters.db.repositories import SqlAlchemyFeatureFlagRepository

pytestmark = pytest.mark.integration


async def insert(session: AsyncSession, values: str) -> None:
    # Sin id ni fechas: los pone Postgres, como cuando alguien edita la tabla.
    await session.execute(
        text(
            "INSERT INTO feature_flags (name, version, description, environment, enabled) "
            f"VALUES {values}"
        )
    )


async def test_lists_the_flags_of_one_environment_by_name(session: AsyncSession) -> None:
    await insert(
        session,
        "('new-checkout', '1.4.0', 'Checkout en una pagina', 'dev', true), "
        "('new-checkout', '1.4.0', NULL, 'prod', false), "
        "('admin.reports', '1.5.0', NULL, 'dev', false)",
    )

    dev = await SqlAlchemyFeatureFlagRepository(session).list_for(FlagEnvironment.DEV)
    prod = await SqlAlchemyFeatureFlagRepository(session).list_for(FlagEnvironment.PROD)

    assert dev == [
        FeatureFlag("admin.reports", "1.5.0", FlagEnvironment.DEV, enabled=False),
        FeatureFlag(
            "new-checkout",
            "1.4.0",
            FlagEnvironment.DEV,
            enabled=True,
            description="Checkout en una pagina",
        ),
    ]
    assert [(f.name, f.enabled) for f in prod] == [("new-checkout", False)]


async def test_a_new_flag_starts_switched_off(session: AsyncSession) -> None:
    await session.execute(
        text("INSERT INTO feature_flags (name, version, environment) VALUES ('x', '1.0', 'dev')")
    )

    [flag] = await SqlAlchemyFeatureFlagRepository(session).list_for(FlagEnvironment.DEV)

    assert flag.enabled is False
