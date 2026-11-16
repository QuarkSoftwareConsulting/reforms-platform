"""Endpoint publico de feature flags."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.infrastructure.api.dependencies import ContainerDep
from app.infrastructure.api.schemas.feature_flags import FeatureFlagsOut

router = APIRouter(tags=["feature-flags"])

# Para una CDN delante del API: la web las pide en cada carga de pagina (sin cache del
# navegador), y asi esas peticiones no llegan todas a la BD. Es el retraso maximo entre
# cambiar una flag y verlo en la web cuando hay CDN.
CACHE_SECONDS = 300


@router.get(
    "/feature-flags",
    response_model=FeatureFlagsOut,
    summary="Feature flags del entorno del despliegue",
)
async def list_feature_flags(container: ContainerDep, response: Response) -> FeatureFlagsOut:
    # Publico: la landing tambien las lee. Solo expone nombres y si estan activas.
    flags = await container.list_feature_flags.execute()
    response.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    return FeatureFlagsOut(flags={flag.name: flag.enabled for flag in flags})
