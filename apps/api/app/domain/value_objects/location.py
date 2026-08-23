"""Objetos de valor geograficos: coordenada y codigo postal."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088

# Espana usa 5 digitos; se admiten 4-10 alfanumericos para no bloquear la expansion
# internacional (UK y Canada usan codigos con letras).
_POSTAL_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 \-]{2,9}$")


@dataclass(frozen=True, slots=True)
class Coordinates:
    """Punto geografico en WGS84 (EPSG:4326)."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"Latitud fuera de rango: {self.latitude}")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"Longitud fuera de rango: {self.longitude}")

    def distance_km_to(self, other: Coordinates) -> float:
        """Distancia ortodromica (haversine) en kilometros.

        Se usa solo para presentacion y para tests del dominio; el filtrado real
        por radio lo hace PostGIS con ST_DWithin sobre indices GIST.
        """
        lat1, lon1, lat2, lon2 = map(
            math.radians, (self.latitude, self.longitude, other.latitude, other.longitude)
        )
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass(frozen=True, slots=True)
class PostalCode:
    """Codigo postal normalizado (mayusculas, sin espacios sobrantes)."""

    value: str

    def __post_init__(self) -> None:
        normalized = " ".join(self.value.upper().split())
        if not _POSTAL_CODE_RE.match(normalized):
            raise ValueError(f"Codigo postal invalido: {self.value!r}")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
