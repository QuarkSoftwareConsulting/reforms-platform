from uuid import uuid4

import pytest

from app.domain.exceptions import ProfessionalProfileIncompleteError, ValidationError
from tests.factories import ALCALA, BARCELONA, MADRID, make_category, make_professional


def test_covers_location_inside_radius() -> None:
    pro = make_professional(base_coordinates=MADRID, service_radius_km=35)
    assert pro.covers(ALCALA) is True


def test_does_not_cover_location_outside_radius() -> None:
    pro = make_professional(base_coordinates=MADRID, service_radius_km=25)
    assert pro.covers(ALCALA) is False
    assert pro.covers(BARCELONA) is False


@pytest.mark.parametrize("radius", [0, -5, 301])
def test_invalid_service_radius_rejected(radius: int) -> None:
    with pytest.raises(ValidationError):
        make_professional(service_radius_km=radius)


def test_professional_without_categories_cannot_browse() -> None:
    pro = make_professional(category_ids=set())
    assert pro.is_ready_to_browse is False
    with pytest.raises(ProfessionalProfileIncompleteError):
        pro.assert_ready_to_browse()


def test_serves_category() -> None:
    category_id = uuid4()
    pro = make_professional(category_ids={category_id})
    assert pro.serves_category(category_id) is True
    assert pro.serves_category(uuid4()) is False


def test_empty_business_name_rejected() -> None:
    with pytest.raises(ValidationError):
        make_professional(business_name="  ")


def test_category_name_is_localized() -> None:
    category = make_category()
    assert category.name("es") == "Carpinteria"
    assert category.name("en-US") == "Carpentry"


def test_category_slug_must_be_kebab_case() -> None:
    with pytest.raises(ValidationError):
        make_category(slug="Carpinteria Fina")


def test_category_price_must_be_positive() -> None:
    from app.domain.value_objects import Money

    with pytest.raises(ValidationError):
        make_category(suggested_lead_price=Money(0, "EUR"))
