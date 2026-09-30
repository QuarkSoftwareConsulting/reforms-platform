"""Zona de cobertura de la Etapa 1: solo la Comunidad de Madrid."""

import pytest

from app.domain.exceptions import PostalCodeNotCoveredError, ValidationError
from app.domain.models import MADRID, ServiceArea
from app.domain.value_objects import PostalCode


@pytest.mark.parametrize("code", ["28001", "28223", "28500", "28991"])
def test_madrid_covers_every_28xxx_code(code: str) -> None:
    assert MADRID.covers(PostalCode(code))
    MADRID.assert_covers(PostalCode(code))


@pytest.mark.parametrize("code", ["08001", "19001", "45001", "02800"])
def test_madrid_rejects_codes_from_other_provinces(code: str) -> None:
    # 02800 empieza por 0 y contiene "28": se compara el prefijo, no la subcadena.
    assert not MADRID.covers(PostalCode(code))
    with pytest.raises(PostalCodeNotCoveredError):
        MADRID.assert_covers(PostalCode(code))


def test_area_is_built_from_configuration() -> None:
    area = ServiceArea.from_prefixes(" 28, 19 ,")
    assert area.postal_prefixes == frozenset({"28", "19"})
    assert area.covers(PostalCode("19001"))


def test_area_needs_at_least_one_prefix() -> None:
    with pytest.raises(ValidationError):
        ServiceArea.from_prefixes(" , ")
