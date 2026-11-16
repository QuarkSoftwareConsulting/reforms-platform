"""Verificacion del movil con Twilio Verify (API REST v2).

Twilio genera, caduca y limita los codigos; nosotros solo pedimos "manda uno" y
"es bueno este". Se habla con la API por HTTP directo (httpx) en vez de con el SDK de
Twilio: el SDK es sincrono y bloquearia el event loop, y asi el adaptador real se
prueba sin credenciales con un transporte simulado (AGENTS.md 7.3).

Autenticacion basica con una API Key (SID `SK...` + secreto). Verify no lleva el
Account SID en la URL, asi que no hace falta.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.application.ports import PhoneVerificationPort
from app.domain.exceptions import (
    PhoneVerificationUnavailableError,
    TooManyVerificationAttemptsError,
)
from app.domain.value_objects import PhoneNumber

logger = logging.getLogger(__name__)

VERIFY_BASE_URL = "https://verify.twilio.com/v2"
TIMEOUT_SECONDS = 10.0

# Codigos de error de Twilio (https://www.twilio.com/docs/api/errors).
# 60203: demasiados envios al mismo numero; 20429: demasiadas peticiones a la API.
_TOO_MANY_SENDS = {60203, 20429}


def to_e164(phone: PhoneNumber) -> str:
    """Twilio exige E.164 y Verify identifica la verificacion por el `To` exacto.

    El formulario admite "611223344", "0034611223344" o "+34611223344": sin
    normalizar, enviar con un formato y confirmar con otro daria siempre "codigo malo".
    """
    value = phone.value
    if phone.is_spanish_mobile:
        return f"+34{value[-9:]}"
    if value.startswith("00"):
        return f"+{value[2:]}"
    return value if value.startswith("+") else f"+{value}"


def _twilio_code(response: httpx.Response) -> int | None:
    try:
        body = response.json()
    except ValueError:
        return None
    code = body.get("code") if isinstance(body, dict) else None
    return code if isinstance(code, int) else None


@dataclass(slots=True)
class TwilioPhoneVerifier(PhoneVerificationPort):
    api_key_sid: str
    api_key_secret: str
    service_sid: str
    # Solo para tests: un `httpx.MockTransport` en lugar de la red.
    transport: httpx.AsyncBaseTransport | None = None

    async def send_code(self, phone: PhoneNumber) -> None:
        response = await self._post("Verifications", {"To": to_e164(phone), "Channel": "sms"})
        if response.is_success:
            return
        code = _twilio_code(response)
        if response.status_code == 429 or code in _TOO_MANY_SENDS:
            raise TooManyVerificationAttemptsError()
        # Nunca el telefono completo en el log (AGENTS.md 4.4).
        logger.error(
            "twilio_verify_envio_fallido: telefono=%s status=%s codigo=%s",
            phone.masked,
            response.status_code,
            code,
        )
        raise PhoneVerificationUnavailableError()

    async def confirm_code(self, phone: PhoneNumber, code: str) -> bool:
        response = await self._post("VerificationCheck", {"To": to_e164(phone), "Code": code})
        if response.is_success:
            body = response.json()
            return isinstance(body, dict) and body.get("status") == "approved"
        # 404: no hay verificacion pendiente (caducada, ya aprobada o agotados los
        # intentos). 429: demasiados intentos con ese codigo. 400: codigo con formato
        # invalido. Para el usuario los tres son "ese codigo no vale, pide otro".
        if response.status_code in {400, 404, 429}:
            return False
        logger.error(
            "twilio_verify_comprobacion_fallida: telefono=%s status=%s codigo=%s",
            phone.masked,
            response.status_code,
            _twilio_code(response),
        )
        raise PhoneVerificationUnavailableError()

    async def _post(self, resource: str, data: dict[str, str]) -> httpx.Response:
        url = f"{VERIFY_BASE_URL}/Services/{self.service_sid}/{resource}"
        try:
            # Un cliente por llamada: son pocas peticiones y asi no hay que cerrar
            # nada al apagar el proceso.
            async with httpx.AsyncClient(
                auth=(self.api_key_sid, self.api_key_secret),
                timeout=TIMEOUT_SECONDS,
                transport=self.transport,
            ) as client:
                return await client.post(url, data=data)
        except httpx.HTTPError as exc:
            logger.error("twilio_verify_sin_respuesta: %s", type(exc).__name__)
            raise PhoneVerificationUnavailableError() from exc
