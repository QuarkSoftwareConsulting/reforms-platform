"""Adaptador de SMS de desarrollo: imita caducidad, limites y consumo del proveedor."""

import logging
import re
from datetime import UTC, datetime, timedelta

import pytest

from app.config import Settings
from app.domain.exceptions import TooManyVerificationAttemptsError
from app.domain.value_objects import PhoneNumber
from app.infrastructure.adapters.sms import ConsolePhoneVerifier
from app.infrastructure.adapters.sms.console_adapter import (
    CODE_TTL,
    MAX_CHECKS_PER_CODE,
    MAX_SENDS_PER_WINDOW,
    SEND_WINDOW,
)
from tests.fakes import FakeClock

PHONE = PhoneNumber("+34611223344")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 9, 28, 12, 0, tzinfo=UTC))


async def sent_code(verifier: ConsolePhoneVerifier, caplog: pytest.LogCaptureFixture) -> str:
    with caplog.at_level(logging.WARNING):
        await verifier.send_code(PHONE)
    match = re.search(r"codigo=(\d{6})", caplog.records[-1].getMessage())
    assert match is not None
    return match.group(1)


async def test_logs_the_code_but_never_the_full_phone(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    verifier = ConsolePhoneVerifier(clock=clock)
    await sent_code(verifier, caplog)
    assert PHONE.value not in caplog.text
    assert PHONE.masked in caplog.text


async def test_the_right_code_is_accepted_once(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    verifier = ConsolePhoneVerifier(clock=clock)
    code = await sent_code(verifier, caplog)
    assert await verifier.confirm_code(PHONE, code) is True
    assert await verifier.confirm_code(PHONE, code) is False


async def test_a_code_expires(clock: FakeClock, caplog: pytest.LogCaptureFixture) -> None:
    verifier = ConsolePhoneVerifier(clock=clock)
    code = await sent_code(verifier, caplog)
    clock.advance(seconds=CODE_TTL.total_seconds())
    assert await verifier.confirm_code(PHONE, code) is False


async def test_a_new_code_replaces_the_previous_one(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    verifier = ConsolePhoneVerifier(clock=clock)
    first = await sent_code(verifier, caplog)
    second = await sent_code(verifier, caplog)
    if first != second:
        assert await verifier.confirm_code(PHONE, first) is False
    assert await verifier.confirm_code(PHONE, second) is True


async def test_guessing_is_capped(clock: FakeClock, caplog: pytest.LogCaptureFixture) -> None:
    verifier = ConsolePhoneVerifier(clock=clock)
    code = await sent_code(verifier, caplog)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(MAX_CHECKS_PER_CODE):
        assert await verifier.confirm_code(PHONE, wrong) is False
    # Agotados los intentos, ni el codigo bueno vale: hay que pedir otro.
    assert await verifier.confirm_code(PHONE, code) is False


async def test_sends_are_rate_limited_per_phone(clock: FakeClock) -> None:
    verifier = ConsolePhoneVerifier(clock=clock)
    for _ in range(MAX_SENDS_PER_WINDOW):
        await verifier.send_code(PHONE)
    with pytest.raises(TooManyVerificationAttemptsError):
        await verifier.send_code(PHONE)
    # Otro movil no se ve afectado, y pasada la ventana se puede volver a pedir.
    await verifier.send_code(PhoneNumber("+34622334455"))
    clock.advance(seconds=(SEND_WINDOW + timedelta(seconds=1)).total_seconds())
    await verifier.send_code(PHONE)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_console_backend_is_refused_outside_development(environment: str) -> None:
    with pytest.raises(ValueError, match="PHONE_VERIFICATION_BACKEND"):
        Settings(environment=environment, phone_verification_backend="console")
