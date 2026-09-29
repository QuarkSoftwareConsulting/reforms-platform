"""Zona de cobertura: donde se pueden publicar solicitudes.

En la Etapa 1 es solo la Comunidad de Madrid (CP 28xxx). Se expresa por prefijos de
CP porque en Espana los dos primeros digitos identifican la provincia, y asi ampliar
la zona es una cuestion de configuracion, no de codigo.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import PostalCodeNotCoveredError, ValidationError
from app.domain.value_objects import PostalCode

MADRID_PREFIX = "28"


@dataclass(frozen=True, slots=True)
class ServiceArea:
    postal_prefixes: frozenset[str]

    def __post_init__(self) -> None:
        if not self.postal_prefixes:
            raise ValidationError("La zona de cobertura necesita al menos un prefijo de CP")

    @classmethod
    def from_prefixes(cls, raw: str) -> ServiceArea:
        """Construye la zona desde la configuracion ("28" o "28,19,45")."""
        return cls(frozenset(p.strip() for p in raw.split(",") if p.strip()))

    def covers(self, postal_code: PostalCode) -> bool:
        return postal_code.value.startswith(tuple(self.postal_prefixes))

    def assert_covers(self, postal_code: PostalCode) -> None:
        if not self.covers(postal_code):
            raise PostalCodeNotCoveredError(
                f"El codigo postal {postal_code} esta fuera de la zona de cobertura"
            )


MADRID = ServiceArea(frozenset({MADRID_PREFIX}))
