"""Feature flags: interruptores por entorno que el frontend lee al cargar.

No hay interfaz para cambiarlos: se activan y desactivan directamente en la tabla
`feature_flags`. Una flag que no existe para el entorno cuenta como apagada, asi que
lo nuevo nace oculto hasta que alguien lo enciende.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FlagEnvironment(StrEnum):
    DEV = "dev"
    PROD = "prod"

    @classmethod
    def for_deployment(cls, environment: str) -> FlagEnvironment:
        """Solo produccion lee las de `prod`; development, test y staging, las de `dev`.

        Ante la duda (un entorno que no reconocemos) se usan las de `dev`: es preferible
        que algo a medias no aparezca en produccion a que aparezca por error.
        """
        return cls.PROD if environment == "production" else cls.DEV


@dataclass(frozen=True, slots=True)
class FeatureFlag:
    name: str
    """Clave estable que usa el frontend (`new-checkout`, `admin.reports`)."""

    version: str
    """Version de la app en que se introdujo: dice cuando se puede retirar."""

    environment: FlagEnvironment
    enabled: bool
    description: str | None = None
