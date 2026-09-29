"""Verificacion por SMS falsa: el codigo siempre es FAKE_CODE y se puede inspeccionar."""

from __future__ import annotations

from app.application.ports import PhoneVerificationPort
from app.domain.exceptions import PhoneVerificationUnavailableError
from app.domain.value_objects import PhoneNumber
from tests.fakes.repositories import _round_trip

FAKE_CODE = "246810"


class FakePhoneVerifier(PhoneVerificationPort):
    def __init__(self) -> None:
        self.pending: dict[str, str] = {}
        self.sent_to: list[str] = []
        self.fail_next = False

    async def send_code(self, phone: PhoneNumber) -> None:
        await _round_trip()
        if self.fail_next:
            self.fail_next = False
            raise PhoneVerificationUnavailableError()
        self.pending[phone.value] = FAKE_CODE
        self.sent_to.append(phone.value)

    async def confirm_code(self, phone: PhoneNumber, code: str) -> bool:
        await _round_trip()
        if self.pending.get(phone.value) != code:
            return False
        # Como un proveedor real: un codigo aprobado no vale dos veces.
        del self.pending[phone.value]
        return True
