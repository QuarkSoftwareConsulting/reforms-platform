"""Identificador fiscal espanol: NIF de persona (DNI), NIE o CIF de empresa.

Se valida la letra o el digito de control: un NIF mal tecleado no llega a la
factura (Fase 5) ni a la cola de validacion del admin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_DNI_RE = re.compile(r"^(\d{8})([A-Z])$")
_NIE_RE = re.compile(r"^([XYZ])(\d{7})([A-Z])$")
_CIF_RE = re.compile(r"^([ABCDEFGHJNPQRSUVW])(\d{7})([0-9A-J])$")
_CIF_LETTER_CONTROL = "PQRSNW"
_CIF_DIGIT_CONTROL = "ABEH"


class TaxIdKind(StrEnum):
    DNI = "dni"
    NIE = "nie"
    CIF = "cif"


def _dni_letter(number: int) -> str:
    return _DNI_LETTERS[number % 23]


def _cif_control(digits: str) -> tuple[str, str]:
    """Devuelve el control del CIF en sus dos formas: (digito, letra)."""
    total = 0
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == 0:  # posiciones impares (1, 3, 5, 7): se doblan
            doubled = value * 2
            total += doubled // 10 + doubled % 10
        else:
            total += value
    control = (10 - total % 10) % 10
    return str(control), "JABCDEFGHI"[control]


@dataclass(frozen=True, slots=True)
class TaxId:
    value: str
    kind: TaxIdKind = field(init=False)

    def __post_init__(self) -> None:
        normalized = re.sub(r"[\s.\-]", "", self.value).upper()
        object.__setattr__(self, "value", normalized)
        kind = self._detect_kind()
        if kind is None:
            raise ValueError(f"Identificador fiscal invalido: {self.value!r}")
        object.__setattr__(self, "kind", kind)

    def _detect_kind(self) -> TaxIdKind | None:
        if match := _DNI_RE.match(self.value):
            number, letter = match.groups()
            return TaxIdKind.DNI if _dni_letter(int(number)) == letter else None
        if match := _NIE_RE.match(self.value):
            prefix, number, letter = match.groups()
            full = int(str("XYZ".index(prefix)) + number)
            return TaxIdKind.NIE if _dni_letter(full) == letter else None
        if match := _CIF_RE.match(self.value):
            organization, digits, control = match.groups()
            digit, letter = _cif_control(digits)
            if organization in _CIF_LETTER_CONTROL:
                valid = control == letter
            elif organization in _CIF_DIGIT_CONTROL:
                valid = control == digit
            else:
                valid = control in {digit, letter}
            return TaxIdKind.CIF if valid else None
        return None

    @property
    def is_company(self) -> bool:
        return self.kind is TaxIdKind.CIF

    def __str__(self) -> str:
        return self.value
