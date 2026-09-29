"""Puerto del limitador de frecuencia: cuantas veces se ha hecho algo en una ventana.

Hoy lo usa el SMS de verificacion: cada envio cuesta dinero al proveedor, y un bot
que pide codigos a numeros de tarificacion especial ("SMS pumping") lo convierte en
fraude contra nosotros. El proveedor ya limita por telefono; esto limita por origen,
que es lo que el atacante no puede rotar tan facil. Tiene que ser compartido entre
instancias del API: un limite en memoria se multiplica por cada instancia.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta


class RateLimiterPort(ABC):
    @abstractmethod
    async def allow(self, key: str, *, limit: int, window: timedelta, now: datetime) -> bool:
        """Cuenta un intento de `key` y dice si cabe en `limit` por `window`.

        El intento cuenta aunque se rechace: insistir no abre hueco antes.
        """
