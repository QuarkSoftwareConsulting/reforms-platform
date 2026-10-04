"""Texto crudo del usuario a value objects, con errores de dominio.

Los value objects lanzan `ValueError` porque el nucleo no conoce HTTP ni `DomainError`
con codigo. Sin esta capa, un telefono o un CP mal escritos llegaban al usuario como un
500 ("algo ha ido mal") en vez de un 422 que diga que campo corregir.
"""

from __future__ import annotations

from app.domain.exceptions import InvalidEmailError, InvalidPhoneError, InvalidPostalCodeError
from app.domain.value_objects import Email, PhoneNumber, PostalCode


def parse_postal_code(raw: str) -> PostalCode:
    try:
        return PostalCode(raw)
    except ValueError as exc:
        raise InvalidPostalCodeError() from exc


def parse_phone(raw: str) -> PhoneNumber:
    try:
        return PhoneNumber(raw)
    except ValueError as exc:
        raise InvalidPhoneError() from exc


def parse_email(raw: str) -> Email:
    try:
        return Email(raw)
    except ValueError as exc:
        raise InvalidEmailError() from exc
