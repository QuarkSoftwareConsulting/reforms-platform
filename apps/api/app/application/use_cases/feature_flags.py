"""Caso de uso: las feature flags del entorno en el que corre el API."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports import FeatureFlagRepositoryPort
from app.domain.models import FeatureFlag, FlagEnvironment


@dataclass(slots=True)
class ListFeatureFlags:
    """El entorno no lo elige quien pregunta: lo fija el despliegue.

    Asi la web de produccion nunca puede pedir (ni ver) las flags de dev.
    """

    flags: FeatureFlagRepositoryPort
    environment: FlagEnvironment

    async def execute(self) -> list[FeatureFlag]:
        return await self.flags.list_for(self.environment)
