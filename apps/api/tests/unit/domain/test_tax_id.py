"""NIF, NIE y CIF: se valida el control para que un error de tecleo no llegue a factura."""

import pytest

from app.domain.value_objects import TaxId, TaxIdKind


@pytest.mark.parametrize(
    ("raw", "kind", "normalized"),
    [
        ("12345678Z", TaxIdKind.DNI, "12345678Z"),
        ("12.345.678-z", TaxIdKind.DNI, "12345678Z"),
        ("X1234567L", TaxIdKind.NIE, "X1234567L"),
        ("y 1234567 x", TaxIdKind.NIE, "Y1234567X"),
        ("B12345674", TaxIdKind.CIF, "B12345674"),
        ("Q2826000H", TaxIdKind.CIF, "Q2826000H"),
    ],
)
def test_accepts_valid_ids(raw: str, kind: TaxIdKind, normalized: str) -> None:
    tax_id = TaxId(raw)
    assert tax_id.kind is kind
    assert tax_id.value == normalized


@pytest.mark.parametrize(
    "raw",
    [
        "12345678A",  # letra de control incorrecta
        "X1234567A",
        "B12345670",  # digito de control incorrecto
        "B1234567D",  # una sociedad limitada lleva control numerico
        "Q2826000A",  # un organismo lleva control con letra
        "1234",
        "",
    ],
)
def test_rejects_invalid_ids(raw: str) -> None:
    with pytest.raises(ValueError):
        TaxId(raw)


def test_only_a_cif_is_a_company() -> None:
    assert TaxId("B12345674").is_company
    assert not TaxId("12345678Z").is_company
