"""Catalogo contra Postgres: categorias con sus servicios, en el orden del catalogo."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.exceptions import CatalogItemInUseError, CatalogSlugTakenError
from app.domain.models import Category, Professional
from app.infrastructure.adapters.db.models import CategoryRow, ProfessionalCategoryRow, ServiceRow
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


async def test_featured_flag_and_image_are_persisted(
    session: AsyncSession, carpentry: Category
) -> None:
    repo = SqlAlchemyCategoryRepository(session)
    category = await repo.get(carpentry.id)
    assert category is not None
    service = category.services[0]
    key = f"catalog/services/{service.id}/0001/puertas.webp"
    category.edit_service(
        service.id,
        name_es=service.name_es,
        name_en=service.name_en,
        sort_order=service.sort_order,
        active=True,
        featured=True,
        image_key=key,
    )
    await repo.update(category)
    await session.commit()
    session.expunge_all()

    reloaded = await repo.get(carpentry.id)

    assert reloaded is not None
    assert reloaded.service(service.id).featured
    assert reloaded.service(service.id).image_key == key


async def test_deleting_a_service_a_lead_just_took_is_reported_as_in_use(
    session: AsyncSession, carpentry: Category
) -> None:
    # La carrera: el caso de uso comprobo que nadie lo usaba y un lead lo eligio justo
    # despues. Sin traducir la clave foranea, el admin veria un 500.
    from app.infrastructure.adapters.db.repositories import SqlAlchemyLeadRepository
    from tests.factories import make_lead

    service = carpentry.services[0]
    await SqlAlchemyLeadRepository(session).add(
        make_lead(category_id=carpentry.id, service_ids=[service.id])
    )
    await session.commit()

    with pytest.raises(CatalogItemInUseError):
        await SqlAlchemyCategoryRepository(session).delete_service(service.id)
    await session.rollback()


async def test_a_category_slug_taken_meanwhile_is_reported_as_taken(
    session: AsyncSession, carpentry: Category
) -> None:
    from app.domain.value_objects import Money

    twin = Category.create(
        id=uuid4(),
        name_es="Carpintería",
        name_en="Carpentry",
        suggested_lead_price=Money(700, "EUR"),
        sort_order=2,
    )

    with pytest.raises(CatalogSlugTakenError):
        await SqlAlchemyCategoryRepository(session).add(twin)
    await session.rollback()


async def test_a_service_slug_taken_meanwhile_is_reported_as_taken(
    session: AsyncSession, carpentry: Category
) -> None:
    # Dos admins anaden el mismo servicio a la vez: cada uno partio de su lectura.
    repo = SqlAlchemyCategoryRepository(session)
    first = await repo.get(carpentry.id)
    second = await repo.get(carpentry.id)
    assert first is not None
    assert second is not None
    first.add_service(id=uuid4(), name_es="Tarimas", name_en="Floors")
    second.add_service(id=uuid4(), name_es="Tarimas", name_en="Floors")
    await repo.update(first)
    await session.commit()

    with pytest.raises(CatalogSlugTakenError):
        await repo.update(second)
    await session.rollback()


async def test_a_category_is_found_by_one_of_its_services(
    session: AsyncSession, carpentry: Category
) -> None:
    repo = SqlAlchemyCategoryRepository(session)

    found = await repo.get_by_service(carpentry.services[1].id)

    assert found is not None
    assert found.id == carpentry.id
    assert [s.id for s in found.services] == [s.id for s in carpentry.services]
    assert await repo.get_by_service(uuid4()) is None


async def test_concurrent_edits_of_one_category_do_not_undo_each_other(
    engine: AsyncEngine, session: AsyncSession, carpentry: Category
) -> None:
    """`update` reescribe todos los servicios: sin bloqueo, la segunda edicion
    devolveria al primer servicio lo que leyo antes de que la primera confirmara."""
    first_service, second_service = carpentry.services[0].id, carpentry.services[1].id
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def rename(service_id: UUID, name: str, *, delay: float, hold: float) -> None:
        await asyncio.sleep(delay)
        async with factory() as s:
            repo = SqlAlchemyCategoryRepository(s)
            category = await repo.get_for_update(carpentry.id)
            assert category is not None
            await asyncio.sleep(hold)
            service = category.service(service_id)
            category.edit_service(
                service_id,
                name_es=name,
                name_en=service.name_en,
                sort_order=service.sort_order,
                active=service.active,
            )
            await repo.update(category)
            await s.commit()

    await asyncio.wait_for(
        asyncio.gather(
            rename(first_service, "Puertas nuevas", delay=0, hold=0.3),
            rename(second_service, "Armarios nuevos", delay=0.05, hold=0),
        ),
        timeout=10,
    )

    session.expunge_all()
    reloaded = await SqlAlchemyCategoryRepository(session).get(carpentry.id)
    assert reloaded is not None
    assert reloaded.service(first_service).name_es == "Puertas nuevas"
    assert reloaded.service(second_service).name_es == "Armarios nuevos"


async def test_a_category_being_added_to_a_profile_is_seen_before_deleting_it(
    engine: AsyncEngine, session: AsyncSession, madrid_carpenter: Professional
) -> None:
    """`professional_categories` es CASCADE: si el borrado no esperara al perfil que
    la esta eligiendo, se la quitaria en silencio en vez de responder que esta en uso."""
    from app.domain.value_objects import Money

    gardening = Category.create(
        id=uuid4(),
        name_es="Jardineria",
        name_en="Gardening",
        suggested_lead_price=Money(700, "EUR"),
        sort_order=2,
    )
    await SqlAlchemyCategoryRepository(session).add(gardening)
    await session.commit()
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    seen_in_use: list[bool] = []

    async def pick_it_in_the_profile() -> None:
        async with factory() as s:
            s.add(
                ProfessionalCategoryRow(
                    professional_id=madrid_carpenter.id, category_id=gardening.id
                )
            )
            await s.flush()
            await asyncio.sleep(0.3)
            await s.commit()

    async def try_to_delete_it() -> None:
        await asyncio.sleep(0.05)  # el perfil ya inserto, sin confirmar
        async with factory() as s:
            repo = SqlAlchemyCategoryRepository(s)
            assert await repo.get_for_update(gardening.id) is not None
            seen_in_use.append(await repo.is_in_use(gardening.id))
            await s.rollback()

    await asyncio.wait_for(asyncio.gather(pick_it_in_the_profile(), try_to_delete_it()), 10)

    assert seen_in_use == [True]
