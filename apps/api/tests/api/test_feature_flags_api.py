"""`GET /feature-flags`: lo que lee el frontend al cargar."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


async def test_returns_the_flags_of_its_environment_without_auth(
    api: AsyncClient, api_engine: AsyncEngine
) -> None:
    async with api_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO feature_flags (name, version, description, environment, enabled) "
                "VALUES ('new-checkout', '1.4.0', 'nota interna', 'dev', true), "
                "('admin.reports', '1.5.0', NULL, 'dev', false), "
                "('new-checkout', '1.4.0', NULL, 'prod', false), "
                "('prod-only', '1.4.0', NULL, 'prod', true)"
            )
        )

    response = await api.get("/feature-flags")

    assert response.status_code == 200
    # Los tests corren con ENVIRONMENT=test: leen las flags de dev, nunca las de prod.
    assert response.json() == {"flags": {"admin.reports": False, "new-checkout": True}}
    # La version y la descripcion son para quien edita la tabla, no para la web.
    assert "nota interna" not in response.text
    assert response.headers["cache-control"] == "public, max-age=60"


async def test_without_flags_everything_is_off(api: AsyncClient) -> None:
    response = await api.get("/feature-flags")

    assert response.json() == {"flags": {}}
