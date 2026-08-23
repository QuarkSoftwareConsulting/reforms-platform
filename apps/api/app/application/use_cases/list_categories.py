"""Caso de uso: catalogo publico de oficios."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports import CategoryRepositoryPort
from app.domain.models import Category


@dataclass(slots=True)
class ListCategories:
    categories: CategoryRepositoryPort

    async def execute(self) -> list[Category]:
        return sorted(await self.categories.list_active(), key=lambda c: c.name_es)
