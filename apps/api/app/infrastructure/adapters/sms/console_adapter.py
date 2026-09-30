"""Verificacion por SMS de desarrollo: el "SMS" es una linea en el log del API.

Existe para poder recorrer el formulario completo en local mientras no haya proveedor
de SMS contratado. Imita lo que hara el proveedor real (Twilio Verify y similares):
codigo de 6 cifras, caducidad, limite de envios y de intentos, y consumo al aprobarlo.
`Settings` impide usarlo fuera de development y test.

Los codigos viven en memoria del proceso: con varias replicas o tras un reinicio se
pierden, lo que en desarrollo da igual y en produccion no se permite.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.application.ports import ClockPort, PhoneVerificationPort
from app.domain.exceptions import TooManyVerificationAttemptsError
from app.domain.value_objects import PhoneNumber

logger = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=10)
SEND_WINDOW = timedelta(minutes=15)
MAX_SENDS_PER_WINDOW = 5
MAX_CHECKS_PER_CODE = 5


@dataclass(slots=True)
class _Pending:
    code: str
    expires_at: datetime
    checks: int = 0


@dataclass(slots=True)
class ConsolePhoneVerifier(PhoneVerificationPort):
    clock: ClockPort
    _pending: dict[str, _Pending] = field(default_factory=dict)
    _sends: dict[str, list[datetime]] = field(default_factory=dict)

    async def send_code(self, phone: PhoneNumber) -> None:
        now = self.clock.now()
        recent = [at for at in self._sends.get(phone.value, []) if now - at < SEND_WINDOW]
        if len(recent) >= MAX_SENDS_PER_WINDOW:
            raise TooManyVerificationAttemptsError()
        self._sends[phone.value] = [*recent, now]

        code = f"{secrets.randbelow(1_000_000):06d}"
        self._pending[phone.value] = _Pending(code=code, expires_at=now + CODE_TTL)
        # Nunca el telefono completo en el log (AGENTS.md 4.4): basta el enmascarado.
        logger.warning("sms_verificacion_dev: telefono=%s codigo=%s", phone.masked, code)

    async def confirm_code(self, phone: PhoneNumber, code: str) -> bool:
        pending = self._pending.get(phone.value)
        if pending is None or self.clock.now() >= pending.expires_at:
            return False
        pending.checks += 1
        if pending.checks > MAX_CHECKS_PER_CODE:
            # Sin este tope, 6 cifras se adivinan por fuerza bruta.
            del self._pending[phone.value]
            return False
        if not secrets.compare_digest(pending.code, code):
            return False
        del self._pending[phone.value]
        return True
