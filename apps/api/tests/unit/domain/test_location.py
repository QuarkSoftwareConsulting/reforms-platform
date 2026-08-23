import pytest

from app.domain.value_objects import Coordinates, PostalCode
from tests.factories import ALCALA, BARCELONA, MADRID


def test_distance_madrid_barcelona_is_about_505_km() -> None:
    assert MADRID.distance_km_to(BARCELONA) == pytest.approx(505, abs=10)


def test_distance_is_symmetric_and_zero_to_itself() -> None:
    assert MADRID.distance_km_to(MADRID) == pytest.approx(0)
    assert MADRID.distance_km_to(ALCALA) == pytest.approx(ALCALA.distance_km_to(MADRID))


@pytest.mark.parametrize(("lat", "lon"), [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_out_of_range_coordinates_rejected(lat: float, lon: float) -> None:
    with pytest.raises(ValueError):
        Coordinates(lat, lon)


def test_postal_code_is_normalized() -> None:
    assert PostalCode(" 28001 ").value == "28001"
    assert PostalCode("sw1a  1aa").value == "SW1A 1AA"


@pytest.mark.parametrize("code", ["", "1", "28", "!!!!!", "a" * 12])
def test_invalid_postal_code_rejected(code: str) -> None:
    with pytest.raises(ValueError):
        PostalCode(code)
