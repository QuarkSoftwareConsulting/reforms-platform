"""Caso de uso: pedir el SMS que verifica el movil del cliente antes de publicar.

El cliente publica como invitado (sin cuenta), asi que el SMS es lo unico que prueba
que el telefono que vendemos existe y es suyo. Mientras no haya proveedor de SMS el
puerto no se configura y la verificacion queda desactivada: `required=False` le dice
al formulario que publique sin pedir codigo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.application.parsing import parse_phone
from app.application.ports import ClockPort, PhoneVerificationPort, RateLimiterPort, UnitOfWork
from app.domain.exceptions import (
    PhoneNotMobileError,
    TooManyVerificationAttemptsError,
)
from app.domain.value_objects import PhoneNumber


@dataclass(frozen=True, slots=True)
class PhoneVerificationStart:
    required: bool
    """False si la verificacion por SMS esta desactivada en este entorno."""


def parse_mobile(raw: str) -> PhoneNumber:
    phone = parse_phone(raw)
    if not phone.is_spanish_mobile:
        raise PhoneNotMobileError()
    return phone


@dataclass(frozen=True, slots=True)
class OriginLimit:
    """Tope de envios por origen (IP) y ventana, con lo necesario para contarlos.

    Va junto para que no se pueda cablear a medias: o se limita del todo o no.
    """

    limiter: RateLimiterPort
    clock: ClockPort
    uow: UnitOfWork
    limit: int
    window: timedelta


@dataclass(slots=True)
class StartPhoneVerification:
    verifier: PhoneVerificationPort | None
    origin_limit: OriginLimit | None = None

    async def execute(self, phone: str, *, origin: str | None = None) -> PhoneVerificationStart:
        """`origin` identifica de donde viene la peticion (la IP, tomada del servidor)."""
        if self.verifier is None:
            return PhoneVerificationStart(required=False)
        mobile = parse_mobile(phone)
        # Despues de validar el movil (un numero invalido no gasta SMS ni cupo) y
        # antes de enviar: el intento cuenta aunque el proveedor falle.
        if origin is not None and self.origin_limit is not None:
            await self._count(self.origin_limit, origin)
        await self.verifier.send_code(mobile)
        return PhoneVerificationStart(required=True)

    @staticmethod
    async def _count(limit: OriginLimit, origin: str) -> None:
        # Transaccion propia: el contador se confirma aunque el envio falle despues.
        async with limit.uow:
            allowed = await limit.limiter.allow(
                f"sms-origin:{origin}",
                limit=limit.limit,
                window=limit.window,
                now=limit.clock.now(),
            )
        if not allowed:
            raise TooManyVerificationAttemptsError()
