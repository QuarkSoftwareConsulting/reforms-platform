"""Caso de uso: pedir el SMS que verifica el movil del cliente antes de publicar.

El cliente publica como invitado (sin cuenta), asi que el SMS es lo unico que prueba
que el telefono que vendemos existe y es suyo. Mientras no haya proveedor de SMS el
puerto no se configura y la verificacion queda desactivada: `required=False` le dice
al formulario que publique sin pedir codigo.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports import PhoneVerificationPort
from app.domain.exceptions import PhoneNotMobileError, ValidationError
from app.domain.value_objects import PhoneNumber


@dataclass(frozen=True, slots=True)
class PhoneVerificationStart:
    required: bool
    """False si la verificacion por SMS esta desactivada en este entorno."""


def parse_mobile(raw: str) -> PhoneNumber:
    try:
        phone = PhoneNumber(raw)
    except ValueError as exc:
        raise ValidationError("Telefono invalido") from exc
    if not phone.is_spanish_mobile:
        raise PhoneNotMobileError()
    return phone


@dataclass(slots=True)
class StartPhoneVerification:
    verifier: PhoneVerificationPort | None

    async def execute(self, phone: str) -> PhoneVerificationStart:
        if self.verifier is None:
            return PhoneVerificationStart(required=False)
        await self.verifier.send_code(parse_mobile(phone))
        return PhoneVerificationStart(required=True)
