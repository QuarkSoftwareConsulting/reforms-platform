"""Catalogo de dos niveles: una categoria y los servicios que ofrece."""

from uuid import uuid4

import pytest

from app.domain.exceptions import InvalidServiceError, ValidationError
from app.domain.models import MAX_SERVICES_PER_LEAD, Service
from tests.factories import make_category


def service(slug: str, *, sort_order: int = 0, active: bool = True) -> Service:
    return Service(
        id=uuid4(),
        slug=slug,
        name_es=slug.title(),
        name_en=slug.title(),
        sort_order=sort_order,
        active=active,
    )


class TestServices:
    def test_active_services_follow_catalog_order_and_skip_retired_ones(self) -> None:
        second, first, retired = (
            service("b", sort_order=2),
            service("a", sort_order=1),
            service("c", sort_order=0, active=False),
        )
        category = make_category(services=[second, retired, first])
        assert category.active_services == [first, second]

    def test_resolves_chosen_services_in_order_without_duplicates(self) -> None:
        a, b = service("a"), service("b")
        category = make_category(services=[a, b])
        assert category.resolve_services([b.id, a.id, b.id]) == [b, a]

    def test_no_services_is_valid(self) -> None:
        assert make_category(services=[service("a")]).resolve_services([]) == []

    def test_rejects_a_service_from_another_category(self) -> None:
        other = make_category(slug="fontaneria", services=[service("x")])
        category = make_category(services=[service("a")])
        with pytest.raises(InvalidServiceError):
            category.resolve_services([other.services[0].id])

    def test_rejects_a_retired_service(self) -> None:
        retired = service("a", active=False)
        with pytest.raises(InvalidServiceError):
            make_category(services=[retired]).resolve_services([retired.id])

    def test_caps_the_number_of_services(self) -> None:
        many = [service(f"s{i}") for i in range(MAX_SERVICES_PER_LEAD + 1)]
        with pytest.raises(ValidationError):
            make_category(services=many).resolve_services([s.id for s in many])

    def test_a_retired_service_keeps_naming_old_leads(self) -> None:
        retired = service("a", active=False)
        category = make_category(services=[retired])
        assert category.services_named([retired.id, uuid4()]) == [retired]

    def test_service_name_follows_locale(self) -> None:
        item = Service(id=uuid4(), slug="aerotermia", name_es="Aerotermia", name_en="Heat pumps")
        assert item.name("en") == "Heat pumps"
        assert item.name("es") == "Aerotermia"
