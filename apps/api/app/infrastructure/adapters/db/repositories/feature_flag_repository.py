"""Feature flags en Postgres (solo lectura: se cambian a mano en la tabla)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import FeatureFlagRepositoryPort
from app.domain.models import FeatureFlag, FlagEnvironment
from app.infrastructure.adapters.db.mappers import feature_flag_to_domain
from app.infrastructure.adapters.db.models import FeatureFlagRow


class SqlAlchemyFeatureFlagRepository(FeatureFlagRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for(self, environment: FlagEnvironment) -> list[FeatureFlag]:
        stmt = (
            select(FeatureFlagRow)
            .where(FeatureFlagRow.environment == environment)
            .order_by(FeatureFlagRow.name)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [feature_flag_to_domain(row) for row in rows]
