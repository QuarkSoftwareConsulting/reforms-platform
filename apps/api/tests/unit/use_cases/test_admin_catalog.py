"""El admin gestiona el catalogo; lo usado se desactiva, solo lo no usado se borra."""

import pytest

from app.domain.exceptions import (
    CatalogItemInUseError,
    CatalogNameInvalidError,
    CatalogSlugTakenError,
    CategoryNotFoundError,
    FeaturedServiceNeedsImageError,
    InvalidSalePriceError,
    ServiceNotFoundError,
    ValidationError,
)
from app.domain.models import Category, Service
from app.domain.value_objects import Money
from tests.conftest import World
from tests.factories import make_lead

EUR5 = Money(500, "EUR")


async def new_category(world: World, name_es: str = "Jardinería", **kwargs: object) -> Category:
    values: dict[str, object] = {
        "name_es": name_es,
        "name_en": "Gardening",
        "suggested_lead_price": EUR5,
        "sort_order": None,
        **kwargs,
    }
    return await world.create_category.execute(**values)  # type: ignore[arg-type]


def with_service(world: World, category: Category, slug: str = "podas") -> Service:
    service = Service.create(
        id=world.ids.new_id(), name_es=slug.title(), name_en=slug, sort_order=1
    )
    category.services.append(service)
    return service


class TestCreateCategory:
    async def test_slug_comes_from_the_spanish_name(self, world: World) -> None:
        category = await new_category(world, "  Albañilería   y Reformas ")

        assert category.slug == "albanileria-y-reformas"
        assert category.name_es == "Albañilería y Reformas"
        assert world.categories.items[category.id] is category

    async def test_without_an_order_it_goes_last(self, world: World) -> None:
        world.add_category(slug="reformas", sort_order=7)
        category = await new_category(world)
        assert category.sort_order == 8

    async def test_a_name_already_used_is_rejected_even_if_deactivated(self, world: World) -> None:
        world.add_category(slug="jardineria", active=False)
        with pytest.raises(CatalogSlugTakenError):
            await new_category(world, "Jardinería")

    @pytest.mark.parametrize("name", ["", "   ", "¡¡!!", "x" * 121])
    async def test_invalid_names_are_rejected(self, world: World, name: str) -> None:
        with pytest.raises(CatalogNameInvalidError) as exc:
            await new_category(world, name)
        assert exc.value.details == {"min": 1, "max": 120}

    async def test_the_suggested_price_must_be_sellable(self, world: World) -> None:
        with pytest.raises(InvalidSalePriceError):
            await new_category(world, suggested_lead_price=Money(0, "EUR"))


class TestUpdateCategory:
    async def test_renames_without_changing_the_slug(self, world: World) -> None:
        category = world.add_category(slug="carpinteria")

        updated = await world.update_category.execute(
            category_id=category.id,
            name_es="Carpintería y ebanistería",
            name_en="Carpentry",
            suggested_price_cents=900,
            sort_order=3,
            active=False,
        )

        assert updated.slug == "carpinteria", "las URL siguen funcionando"
        assert updated.name_es == "Carpintería y ebanistería"
        assert updated.suggested_lead_price == Money(900, "EUR")
        assert updated.sort_order == 3
        assert not updated.active

    async def test_a_deactivated_category_leaves_the_public_catalog(self, world: World) -> None:
        category = world.add_category(slug="carpinteria")
        await world.update_category.execute(
            category_id=category.id,
            name_es="Carpintería",
            name_en="Carpentry",
            suggested_price_cents=500,
            sort_order=0,
            active=False,
        )

        assert await world.categories.list_active() == []
        assert [c.id for c in await world.list_catalog.execute()] == [category.id]

    async def test_unknown_category(self, world: World) -> None:
        with pytest.raises(CategoryNotFoundError):
            await world.update_category.execute(
                category_id=world.ids.new_id(),
                name_es="X",
                name_en="X",
                suggested_price_cents=500,
                sort_order=0,
                active=True,
            )


class TestDeleteCategory:
    async def test_an_unused_category_is_deleted_with_its_services(self, world: World) -> None:
        category = world.add_category(slug="carpinteria")
        with_service(world, category)

        await world.delete_category.execute(category_id=category.id)

        assert category.id not in world.categories.items

    async def test_a_category_with_leads_cannot_be_deleted(self, world: World) -> None:
        category = world.add_category(slug="carpinteria")
        lead = make_lead(category_id=category.id)
        world.leads.items[lead.id] = lead

        with pytest.raises(CatalogItemInUseError):
            await world.delete_category.execute(category_id=category.id)
        assert category.id in world.categories.items

    async def test_a_category_in_a_professional_profile_cannot_be_deleted(
        self, world: World
    ) -> None:
        category = world.add_category(slug="carpinteria")
        world.add_professional(category_ids={category.id})

        with pytest.raises(CatalogItemInUseError):
            await world.delete_category.execute(category_id=category.id)

    async def test_a_category_whose_service_is_used_cannot_be_deleted(self, world: World) -> None:
        category = world.add_category(slug="carpinteria")
        service = with_service(world, category)
        other = world.add_category(slug="reformas")
        world.add_professional(category_ids={other.id}, service_ids={service.id})

        with pytest.raises(CatalogItemInUseError):
            await world.delete_category.execute(category_id=category.id)


class TestServices:
    async def test_a_new_service_goes_last_with_its_own_slug(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        with_service(world, category, "podas")

        updated = await world.create_service.execute(
            category_id=category.id, name_es="Diseño de jardines", name_en="Garden design"
        )

        service = updated.services[-1]
        assert service.slug == "diseno-de-jardines"
        assert service.sort_order == 2
        assert service in updated.active_services

    async def test_the_same_name_twice_in_a_category_is_rejected(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        with_service(world, category, "podas")

        with pytest.raises(CatalogSlugTakenError):
            await world.create_service.execute(
                category_id=category.id, name_es="Podas", name_en="Pruning"
            )

    async def test_the_same_name_in_another_category_is_fine(self, world: World) -> None:
        with_service(world, world.add_category(slug="jardineria"), "podas")
        other = world.add_category(slug="reformas")

        updated = await world.create_service.execute(
            category_id=other.id, name_es="Podas", name_en="Pruning"
        )
        assert updated.services[-1].slug == "podas"

    async def test_editing_keeps_the_slug_and_can_deactivate(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        service = with_service(world, category, "podas")

        updated = await world.update_service.execute(
            category_id=category.id,
            service_id=service.id,
            name_es="Poda de árboles",
            name_en="Tree pruning",
            sort_order=5,
            active=False,
        )

        edited = updated.service(service.id)
        assert edited.slug == "podas"
        assert edited.name_es == "Poda de árboles"
        assert edited.sort_order == 5
        assert edited not in updated.active_services

    async def test_a_service_of_another_category_is_not_found(self, world: World) -> None:
        service = with_service(world, world.add_category(slug="jardineria"))
        other = world.add_category(slug="reformas")

        with pytest.raises(ServiceNotFoundError):
            await world.delete_service.execute(category_id=other.id, service_id=service.id)

    async def test_an_unused_service_is_deleted(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        service = with_service(world, category)

        await world.delete_service.execute(category_id=category.id, service_id=service.id)

        assert world.categories.items[category.id].services == []

    async def test_a_service_named_by_a_lead_cannot_be_deleted(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        service = with_service(world, category)
        lead = make_lead(category_id=category.id, service_ids=[service.id])
        world.leads.items[lead.id] = lead

        with pytest.raises(CatalogItemInUseError):
            await world.delete_service.execute(category_id=category.id, service_id=service.id)
        assert world.categories.items[category.id].services == [service]


async def feature(world: World, category: Category, service: Service, **kwargs: object):
    values: dict[str, object] = {
        "category_id": category.id,
        "service_id": service.id,
        "name_es": service.name_es,
        "name_en": service.name_en,
        "sort_order": service.sort_order,
        "active": True,
        "featured": True,
        "image_key": f"catalog/services/{service.id}/0001/podas.webp",
        **kwargs,
    }
    return await world.update_service.execute(**values)  # type: ignore[arg-type]


class TestFeaturedServices:
    async def test_a_featured_service_keeps_its_photo(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        service = with_service(world, category)

        updated = await feature(world, category, service)

        featured = updated.service(service.id)
        assert featured.featured
        assert featured.on_landing
        assert featured.image_key == f"catalog/services/{service.id}/0001/podas.webp"

    async def test_featuring_without_a_photo_is_rejected(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        service = with_service(world, category)

        with pytest.raises(FeaturedServiceNeedsImageError):
            await feature(world, category, service, image_key=None)
        assert not world.categories.items[category.id].service(service.id).featured

    async def test_a_photo_uploaded_for_another_service_is_rejected(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        service = with_service(world, category)
        other = with_service(world, category, "riegos")

        with pytest.raises(ValidationError):
            await feature(
                world, category, service, image_key=f"catalog/services/{other.id}/0001/x.webp"
            )

    async def test_a_deactivated_featured_service_leaves_the_landing(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        service = with_service(world, category)

        updated = await feature(world, category, service, active=False)

        assert not updated.service(service.id).on_landing


class TestCatalogImageUpload:
    async def test_the_key_carries_the_service_id(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        service = with_service(world, category)

        upload = await world.request_catalog_image_upload.execute(
            category_id=category.id,
            service_id=service.id,
            filename="podas.webp",
            content_type="image/webp",
            size_bytes=200_000,
        )

        assert upload.storage_key.startswith(f"catalog/services/{service.id}/")

    @pytest.mark.parametrize(
        ("content_type", "size"),
        [("image/heic", 1000), ("application/pdf", 1000), ("image/png", 6_000_000)],
    )
    async def test_unsuitable_files_are_rejected(
        self, world: World, content_type: str, size: int
    ) -> None:
        category = world.add_category(slug="jardineria")
        service = with_service(world, category)

        with pytest.raises(ValidationError):
            await world.request_catalog_image_upload.execute(
                category_id=category.id,
                service_id=service.id,
                filename="x",
                content_type=content_type,
                size_bytes=size,
            )

    async def test_a_service_of_another_category_cannot_get_an_upload(self, world: World) -> None:
        service = with_service(world, world.add_category(slug="jardineria"))
        other = world.add_category(slug="reformas")

        with pytest.raises(ServiceNotFoundError):
            await world.request_catalog_image_upload.execute(
                category_id=other.id,
                service_id=service.id,
                filename="x.webp",
                content_type="image/webp",
                size_bytes=10,
            )


class TestLandingServiceImage:
    async def test_resolves_the_current_url_of_a_featured_service(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        service = with_service(world, category)
        await feature(world, category, service)

        url = await world.landing_service_image.execute(service_id=service.id)

        assert url == f"https://cdn.test/reforma-hub/catalog/services/{service.id}/0001/podas.webp"

    async def test_a_service_that_is_not_on_the_landing_has_no_image(self, world: World) -> None:
        category = world.add_category(slug="jardineria")
        plain = with_service(world, category)
        hidden = with_service(world, category, "riegos")
        await feature(world, category, hidden, active=False)

        for service in (plain, hidden):
            with pytest.raises(ServiceNotFoundError):
                await world.landing_service_image.execute(service_id=service.id)

    async def test_a_deactivated_category_takes_its_services_off_the_landing(
        self, world: World
    ) -> None:
        category = world.add_category(slug="jardineria")
        service = with_service(world, category)
        await feature(world, category, service)
        category.active = False

        with pytest.raises(ServiceNotFoundError):
            await world.landing_service_image.execute(service_id=service.id)


class TestLandingName:
    async def test_the_card_uses_the_short_name_in_each_language(self, world: World) -> None:
        category = world.add_category(slug="reformas")
        service = with_service(world, category, "reformas-de-banos")

        updated = await feature(
            world, category, service, landing_name_es="  Baños ", landing_name_en="Bathrooms"
        )

        edited = updated.service(service.id)
        assert edited.landing_name("es") == "Baños"
        assert edited.landing_name("en") == "Bathrooms"

    async def test_without_a_short_name_the_service_name_is_used(self, world: World) -> None:
        category = world.add_category(slug="reformas")
        service = with_service(world, category, "pintores")

        updated = await feature(world, category, service, landing_name_es="   ")

        edited = updated.service(service.id)
        assert edited.landing_name_es is None
        assert edited.landing_name("es") == edited.name_es

    async def test_a_short_name_must_fit_the_card(self, world: World) -> None:
        category = world.add_category(slug="reformas")
        service = with_service(world, category, "pintores")

        with pytest.raises(CatalogNameInvalidError) as exc:
            await feature(world, category, service, landing_name_es="x" * 41)
        assert exc.value.details == {"min": 1, "max": 40}
