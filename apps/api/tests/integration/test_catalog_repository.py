"""Catalogo contra Postgres: categorias con sus servicios, en el orden del catalogo."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Category
from app.infrastructure.adapters.db.models import CategoryRow, ServiceRow
from app.infrastructure.adapters.db.repositories import SqlAlchemyCategoryRepository


async def test_category_loads_all_its_services_in_order(
    session: AsyncSession, carpentry: Category
) -> None:
    session.add(
        ServiceRow(
            id=uuid4(),
            category_id=carpentry.id,
            slug="retirado",
            name_es="Retirado",
            name_en="Retired",
            sort_order=-1,
            active=False,
        )
    )
    await session.commit()
    session.expunge_all()

    loaded = await SqlAlchemyCategoryRepository(session).get(carpentry.id)

    assert loaded is not None
    # Carga tambien los retirados (los nombran leads antiguos) pero no los ofrece.
    assert [s.slug for s in loaded.services] == ["retirado", "puertas", "armarios"]
    assert [s.slug for s in loaded.active_services] == ["puertas", "armarios"]


async def test_active_categories_follow_catalog_order(
    session: AsyncSession, carpentry: Category
) -> None:
    for slug, order, active in (("zeta", 1, True), ("alfa", 2, True), ("vieja", 0, False)):
        session.add(
            CategoryRow(
                id=uuid4(),
                slug=slug,
                name_es=slug.title(),
                name_en=slug.title(),
                suggested_lead_price_cents=500,
                currency="EUR",
                active=active,
                sort_order=order,
            )
        )
    await session.commit()

    categories = await SqlAlchemyCategoryRepository(session).list_active()

    # carpinteria tiene orden 0; "vieja" esta inactiva y no sale.
    assert [c.slug for c in categories] == ["carpinteria", "zeta", "alfa"]
