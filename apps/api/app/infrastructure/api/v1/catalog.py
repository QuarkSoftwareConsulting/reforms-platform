"""Endpoints publicos de catalogo."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse

from app.infrastructure.api import serializers
from app.infrastructure.api.dependencies import ContainerDep, LocaleDep
from app.infrastructure.api.schemas.billing import PublicSubscriptionPriceOut
from app.infrastructure.api.schemas.leads import CatalogCategoryOut

router = APIRouter(tags=["catalog"])


@router.get(
    "/categories",
    response_model=list[CatalogCategoryOut],
    summary="Categorias activas con sus servicios",
)
async def list_categories(container: ContainerDep, locale: LocaleDep) -> list[CatalogCategoryOut]:
    categories = await container.list_categories.execute()
    return [serializers.catalog_category_out(category, locale) for category in categories]


@router.get(
    "/subscription-price",
    response_model=PublicSubscriptionPriceOut,
    summary="Mensualidad vigente, para anunciarla en la landing",
)
async def public_subscription_price(container: ContainerDep) -> PublicSubscriptionPriceOut:
    current = await container.pricing.current()
    return PublicSubscriptionPriceOut(
        amount=serializers.money_out(current.amount) if current is not None else None
    )


# Menos que lo que dura una URL firmada de GCS (15 min): la redireccion cacheada nunca
# apunta a una URL ya caducada.
SERVICE_IMAGE_CACHE_SECONDS = 300


@router.get(
    "/catalog/services/{service_id}/image",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    summary="Foto de un servicio destacado (redirige a una URL vigente del bucket)",
)
async def landing_service_image(service_id: UUID, container: ContainerDep) -> RedirectResponse:
    """La landing se cachea un dia: enlaza esta URL estable, no la firmada del bucket."""
    url = await container.landing_service_image.execute(service_id=service_id)
    return RedirectResponse(
        url,
        status_code=status.HTTP_302_FOUND,
        headers={"Cache-Control": f"public, max-age={SERVICE_IMAGE_CACHE_SECONDS}"},
    )
