"""Adaptador REAL de Twilio Verify, con la red sustituida por un transporte simulado.

Comprueba lo que un fake no ve (AGENTS.md 7.3): URL, autenticacion, formato del
cuerpo y como se traducen los errores de Twilio a los del dominio.
"""

import base64
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import parse_qs

import httpx
import pytest

from app.config import Settings
from app.domain.exceptions import (
    PhoneVerificationUnavailableError,
    TooManyVerificationAttemptsError,
)
from app.domain.value_objects import PhoneNumber
from app.infrastructure.adapters.sms import TwilioPhoneVerifier
from app.infrastructure.adapters.sms.twilio_adapter import to_e164
from app.infrastructure.api.dependencies import create_phone_verifier
from tests.fakes import FakeClock

# THIS ARE TEST VALUES, DO NOT USE THEM IN PRODUCTION
SERVICE = "VA00000000000000000000000000000000"
KEY_SID = "SK00000000000000000000000000000000"
KEY_SECRET = "s3cret"
PHONE = PhoneNumber("611 22 33 44")

Handler = Callable[[httpx.Request], httpx.Response]


def verifier(handler: Handler, requests: list[httpx.Request] | None = None) -> TwilioPhoneVerifier:
    def record(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        return handler(request)

    return TwilioPhoneVerifier(
        api_key_sid=KEY_SID,
        api_key_secret=KEY_SECRET,
        service_sid=SERVICE,
        transport=httpx.MockTransport(record),
    )


def twilio_error(status: int, code: int) -> Handler:
    return lambda _: httpx.Response(status, json={"code": code, "status": status})


def form(request: httpx.Request) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(request.content.decode()).items()}


@pytest.mark.parametrize("raw", ["611223344", "+34611223344", "0034611223344", "611 22 33 44"])
def test_spanish_mobiles_are_normalized_to_e164(raw: str) -> None:
    # Enviar con un formato y confirmar con otro daria "codigo incorrecto" siempre.
    assert to_e164(PhoneNumber(raw)) == "+34611223344"


async def test_send_posts_an_sms_verification_with_api_key_auth() -> None:
    requests: list[httpx.Request] = []
    sms = verifier(lambda _: httpx.Response(201, json={"status": "pending"}), requests)

    await sms.send_code(PHONE)

    [request] = requests
    assert request.method == "POST"
    assert str(request.url) == f"https://verify.twilio.com/v2/Services/{SERVICE}/Verifications"
    expected = base64.b64encode(f"{KEY_SID}:{KEY_SECRET}".encode()).decode()
    assert request.headers["Authorization"] == f"Basic {expected}"
    assert form(request) == {"To": "+34611223344", "Channel": "sms"}


@pytest.mark.parametrize(("status", "code"), [(429, 60203), (429, 20429)])
async def test_send_rate_limit_becomes_too_many_attempts(status: int, code: int) -> None:
    with pytest.raises(TooManyVerificationAttemptsError):
        await verifier(twilio_error(status, code)).send_code(PHONE)


async def test_send_failure_is_unavailable_and_logs_no_full_phone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR), pytest.raises(PhoneVerificationUnavailableError):
        await verifier(twilio_error(401, 20003)).send_code(PHONE)
    assert "611223344" not in caplog.text
    assert "20003" in caplog.text


async def test_network_error_is_unavailable() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    sms = verifier(boom)
    with pytest.raises(PhoneVerificationUnavailableError):
        await sms.send_code(PHONE)
    with pytest.raises(PhoneVerificationUnavailableError):
        await sms.confirm_code(PHONE, "123456")


async def test_confirm_posts_the_code_and_accepts_only_approved() -> None:
    requests: list[httpx.Request] = []
    sms = verifier(lambda _: httpx.Response(200, json={"status": "approved"}), requests)

    assert await sms.confirm_code(PhoneNumber("+34611223344"), "123456") is True

    [request] = requests
    assert str(request.url).endswith(f"/Services/{SERVICE}/VerificationCheck")
    assert form(request) == {"To": "+34611223344", "Code": "123456"}


async def test_wrong_code_is_rejected() -> None:
    sms = verifier(lambda _: httpx.Response(200, json={"status": "pending"}))
    assert await sms.confirm_code(PHONE, "000000") is False


@pytest.mark.parametrize(
    ("status", "code"),
    [(404, 20404), (429, 60202), (400, 60200)],
    ids=["caducado-o-ya-usado", "demasiados-intentos", "formato-invalido"],
)
async def test_unusable_codes_are_rejected_not_errors(status: int, code: int) -> None:
    assert await verifier(twilio_error(status, code)).confirm_code(PHONE, "123456") is False


async def test_confirm_provider_failure_is_unavailable() -> None:
    # Decir "codigo incorrecto" con Twilio caido haria pedir SMS que no van a servir.
    with pytest.raises(PhoneVerificationUnavailableError):
        await verifier(twilio_error(503, 20500)).confirm_code(PHONE, "123456")


def test_composition_root_builds_the_twilio_verifier() -> None:
    settings = Settings(
        phone_verification_backend="twilio",
        twilio_api_key_sid=KEY_SID,
        twilio_api_key_secret=KEY_SECRET,
        twilio_verify_service_sid=SERVICE,
    )
    built = create_phone_verifier(settings, FakeClock(datetime(2026, 11, 16, tzinfo=UTC)))
    assert isinstance(built, TwilioPhoneVerifier)
    assert built.service_sid == SERVICE


@pytest.mark.parametrize(
    ("overrides", "variable"),
    [
        ({"twilio_api_key_sid": ""}, "TWILIO_API_KEY_SID"),
        ({"twilio_api_key_sid": "AC123"}, "TWILIO_API_KEY_SID"),
        ({"twilio_api_key_secret": ""}, "TWILIO_API_KEY_SECRET"),
        ({"twilio_verify_service_sid": "MG123"}, "TWILIO_VERIFY_SERVICE_SID"),
    ],
)
def test_twilio_backend_refuses_to_start_half_configured(
    overrides: dict[str, str], variable: str
) -> None:
    values = {
        "twilio_api_key_sid": KEY_SID,
        "twilio_api_key_secret": KEY_SECRET,
        "twilio_verify_service_sid": SERVICE,
        **overrides,
    }
    with pytest.raises(ValueError, match=variable):
        Settings(phone_verification_backend="twilio", **values)
