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


async def test_a_new_category_with_services_round_trips(session: AsyncSession) -> None:
    from app.domain.value_objects import Money

    repo = SqlAlchemyCategoryRepository(session)
    category = Category.create(
        id=uuid4(),
        name_es="Jardinería",
        name_en="Gardening",
        suggested_lead_price=Money(700, "EUR"),
        sort_order=9,
    )
    category.add_service(id=uuid4(), name_es="Podas", name_en="Pruning")
    await repo.add(category)
    await session.commit()
    session.expunge_all()

    loaded = await repo.get(category.id)

    assert loaded is not None
    assert loaded.slug == "jardineria"
    assert loaded.suggested_lead_price == Money(700, "EUR")
    assert [s.slug for s in loaded.services] == ["podas"]


async def test_update_adds_and_edits_services_and_get_sees_them(
    session: AsyncSession, carpentry: Category
) -> None:
    repo = SqlAlchemyCategoryRepository(session)
    category = await repo.get(carpentry.id)
    assert category is not None
    first = category.services[0]
    category.add_service(id=uuid4(), name_es="Tarimas", name_en="Floors")
    category.edit_service(
        first.id, name_es="Puertas a medida", name_en="Doors", sort_order=0, active=False
    )
    category.edit(name_es="Carpintería fina", name_en="Fine carpentry", sort_order=4, active=True)
    await repo.update(category)
    await session.commit()

    # En la misma sesion, sin vaciarla: `get` no puede devolver los servicios cacheados.
    reloaded = await repo.get(carpentry.id)

    assert reloaded is not None
    assert reloaded.name_es == "Carpintería fina"
    assert reloaded.slug == "carpinteria"
    assert [s.slug for s in reloaded.active_services] == ["armarios", "tarimas"]
    assert reloaded.service(first.id).name_es == "Puertas a medida"


async def test_list_all_includes_deactivated_categories(
    session: AsyncSession, carpentry: Category
) -> None:
    repo = SqlAlchemyCategoryRepository(session)
    category = await repo.get(carpentry.id)
    assert category is not None
    category.edit(name_es=category.name_es, name_en=category.name_en, sort_order=0, active=False)
    await repo.update(category)
    await session.commit()

    assert await repo.list_active() == []
    assert [c.slug for c in await repo.list_all()] == ["carpinteria"]


async def test_usage_follows_the_real_foreign_keys(
    session: AsyncSession, carpentry: Category, madrid_carpenter: object
) -> None:
    repo = SqlAlchemyCategoryRepository(session)
    # `madrid_carpenter` tiene la categoria en su perfil, pero ningun servicio.
    assert await repo.is_in_use(carpentry.id)
    assert not await repo.is_service_in_use(carpentry.services[0].id)


async def test_an_unused_category_is_deleted_with_its_services(
    session: AsyncSession, carpentry: Category
) -> None:
    repo = SqlAlchemyCategoryRepository(session)
    assert not await repo.is_in_use(carpentry.id)

    await repo.delete_service(carpentry.services[0].id)
    await repo.delete(carpentry.id)
    await session.commit()

    assert await repo.get(carpentry.id) is None
    assert await repo.list_all() == []


async def test_a_service_named_by_a_lead_is_in_use(
    session: AsyncSession, carpentry: Category
) -> None:
    from app.infrastructure.adapters.db.repositories import SqlAlchemyLeadRepository
    from tests.factories import make_lead

    service = carpentry.services[0]
    await SqlAlchemyLeadRepository(session).add(
        make_lead(category_id=carpentry.id, service_ids=[service.id])
    )
    await session.commit()

    repo = SqlAlchemyCategoryRepository(session)
    assert await repo.is_service_in_use(service.id)
    assert await repo.is_in_use(carpentry.id)
