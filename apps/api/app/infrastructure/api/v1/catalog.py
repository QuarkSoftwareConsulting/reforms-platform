"""Endpoints publicos de catalogo."""

from __future__ import annotations

from fastapi import APIRouter

from app.infrastructure.api import serializers
from app.infrastructure.api.dependencies import ContainerDep, LocaleDep
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
