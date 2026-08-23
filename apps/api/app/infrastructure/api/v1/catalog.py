"""Endpoints publicos de catalogo."""

from __future__ import annotations

from fastapi import APIRouter

from app.infrastructure.api import serializers
from app.infrastructure.api.dependencies import ContainerDep, LocaleDep
from app.infrastructure.api.schemas.leads import CategoryOut

router = APIRouter(tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut], summary="Categorias de oficio activas")
async def list_categories(container: ContainerDep, locale: LocaleDep) -> list[CategoryOut]:
    categories = await container.list_categories.execute()
    return [serializers.category_out(category, locale) for category in categories]
