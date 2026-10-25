"""Endpoint publico de feature flags."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.infrastructure.api.dependencies import ContainerDep
from app.infrastructure.api.schemas.feature_flags import FeatureFlagsOut

router = APIRouter(tags=["feature-flags"])

# El frontend las cachea 5 min (ISR de Next); el navegador y una CDN, lo mismo. Es el
# retraso maximo entre cambiar una flag en la BD y verlo en la web. No es menor porque
# el layout las pide en todas las paginas: fija cada cuanto se regeneran todas.
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
