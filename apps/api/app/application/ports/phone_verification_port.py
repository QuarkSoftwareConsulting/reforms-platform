"""Puerto de verificacion del telefono del cliente por SMS (F01).

El proveedor esta sin decidir (Twilio Verify, MessageBird, Vonage...). El nucleo solo
pide "manda un codigo a este movil" y "es bueno este codigo": generar, guardar,
caducar y limitar los codigos es cosa del proveedor, que ya lo hace mejor que
nosotros. Asi no guardamos codigos ni telefonos en nuestra base de datos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.value_objects import PhoneNumber


class PhoneVerificationPort(ABC):
    @abstractmethod
    async def send_code(self, phone: PhoneNumber) -> None:
        """Envia un codigo al movil.

        Lanza `TooManyVerificationAttemptsError` si se piden demasiados codigos y
        `PhoneVerificationUnavailableError` si el proveedor falla.
        """

    @abstractmethod
    async def confirm_code(self, phone: PhoneNumber, code: str) -> bool:
        """True si el codigo es el ultimo enviado a ese movil y no ha caducado.

        Un codigo confirmado se consume: no vale para una segunda publicacion.
        """
