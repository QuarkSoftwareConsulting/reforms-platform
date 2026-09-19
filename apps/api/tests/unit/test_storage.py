"""Contratos de almacenamiento sin red, incluyendo la firma real V4 del SDK."""

from __future__ import annotations

import asyncio
import base64
import json
import threading
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from google.api_core.exceptions import Forbidden, NotFound
from google.auth.compute_engine import Credentials
from google.auth.exceptions import RefreshError, TransportError
from google.cloud.storage import Bucket
from pydantic import ValidationError

from app.config import Settings
from app.infrastructure.adapters.storage.gcs_adapter import GCSStorage
from app.infrastructure.adapters.storage.object_keys import create_object_key
from app.infrastructure.adapters.storage.s3_adapter import S3Storage
from app.infrastructure.api.dependencies import create_storage

MODULE = "app.infrastructure.adapters.storage.gcs_adapter"
EMAIL = "runtime@example.iam.gserviceaccount.com"


@pytest.fixture
def adc(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    credentials = Mock(spec=Credentials)
    credentials.valid = False
    credentials.service_account_email = "default"
    credentials.token = None

    def refresh(request: object) -> None:
        credentials.valid = True
        credentials.service_account_email = EMAIL
        credentials.token = "test-token"

    credentials.refresh.side_effect = refresh
    monkeypatch.setattr(
        f"{MODULE}.google.auth.default", Mock(return_value=(credentials, "project"))
    )
    return credentials


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Mock:
    client = Mock()
    client.bucket.return_value.blob.return_value.generate_signed_url.return_value = "https://signed"
    monkeypatch.setattr(f"{MODULE}.storage.Client", Mock(return_value=client))
    return client


def settings(**overrides: object) -> Settings:
    values = {
        "_env_file": None,
        "environment": "production",
        "storage_backend": "s3",
        "google_application_credentials": "",
        "firebase_auth_emulator_host": "",
        "firebase_project_id": "project",
        "stripe_secret_key": "test-key",
        "stripe_webhook_secret": "test-webhook",
        "s3_access_key_id": "",
        "s3_secret_access_key": "",
    }
    values.update(overrides)
    return Settings(**values)


def test_default_backend_is_s3_without_adc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    adc = Mock(side_effect=AssertionError("S3 no debe cargar ADC"))
    monkeypatch.setattr(f"{MODULE}.google.auth.default", adc)
    s3_client = Mock()
    monkeypatch.setattr("app.infrastructure.adapters.storage.s3_adapter.boto3.client", s3_client)
    config = Settings(_env_file=None)
    assert config.storage_backend == "s3"
    adapter = create_storage(config)
    assert isinstance(adapter, S3Storage)
    assert adapter.public_url("leads/a.jpg").endswith("/leads/a.jpg")
    adc.assert_not_called()


def test_select_gcs_without_s3_secrets(adc: Mock, client: Mock) -> None:
    config = settings(storage_backend="gcs", gcs_bucket="private-photos")
    config.assert_production_ready()
    assert isinstance(create_storage(config), GCSStorage)
    client.bucket.assert_called_once_with("private-photos")


def test_s3_still_requires_secrets_in_production() -> None:
    with pytest.raises(RuntimeError, match="S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY"):
        settings().assert_production_ready()


@pytest.mark.parametrize(
    "overrides",
    [
        {"storage_backend": "other"},
        {"storage_backend": "gcs", "gcs_bucket": " "},
        {"gcs_signed_url_expires_seconds": 0},
        {"gcs_signed_url_expires_seconds": 604801},
        {
            "storage_backend": "gcs",
            "gcs_bucket": "private",
            "google_application_credentials": "/not-loaded.json",
        },
    ],
)
def test_invalid_storage_configuration(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        settings(**overrides)


def test_gcs_rejects_credentials_file_before_loading_adc(
    monkeypatch: pytest.MonkeyPatch, adc: Mock, client: Mock
) -> None:
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/not-loaded.json")
    default = Mock(side_effect=AssertionError("No debe leer el archivo"))
    monkeypatch.setattr(f"{MODULE}.google.auth.default", default)
    with pytest.raises(ValueError, match="sin GOOGLE_APPLICATION_CREDENTIALS"):
        GCSStorage(bucket="private")
    default.assert_not_called()


def test_object_keys_keep_date_uuid_and_sanitized_filename() -> None:
    before = datetime.now(UTC).strftime("%Y/%m/%d")
    key = create_object_key("leads", "kitchen /photo.exe", "image/png")
    after = datetime.now(UTC).strftime("%Y/%m/%d")
    prefix, year, month, day, identifier, filename = key.split("/")
    assert prefix == "leads"
    assert f"{year}/{month}/{day}" in {before, after}
    assert len(identifier) == 32
    int(identifier, 16)
    assert filename == "kitchen--photo.png"
    assert key != create_object_key("leads", "kitchen /photo.exe", "image/png")


async def test_gcs_put_contract_and_signing_off_event_loop(adc: Mock, client: Mock) -> None:
    loop_thread = threading.get_ident()
    blob = client.bucket.return_value.blob.return_value

    def sign(**kwargs: object) -> str:
        assert threading.get_ident() != loop_thread
        return "https://signed-put"

    blob.generate_signed_url.side_effect = sign
    adapter = GCSStorage(bucket="private", signed_url_expires_seconds=120)
    result = await adapter.create_presigned_upload(
        key_prefix="leads", filename="photo.exe", content_type="image/jpeg"
    )
    assert result.storage_key.startswith("leads/")
    assert result.storage_key.endswith("/photo.jpg")
    assert result.upload_url == "https://signed-put"
    assert result.method == "PUT"
    assert result.headers == {"Content-Type": "image/jpeg"}
    assert result.expires_in_seconds == 120
    client.bucket.return_value.blob.assert_called_with(result.storage_key)
    blob.generate_signed_url.assert_called_once_with(
        version="v4",
        expiration=timedelta(seconds=120),
        method="PUT",
        content_type="image/jpeg",
        credentials=adc,
        service_account_email=EMAIL,
        access_token="test-token",
    )
    blob.make_public.assert_not_called()


async def test_get_signs_again_and_refreshes_expired_adc(adc: Mock, client: Mock) -> None:
    adapter = GCSStorage(bucket="private")
    blob = client.bucket.return_value.blob.return_value
    blob.generate_signed_url.side_effect = ["https://first", "https://second"]
    assert await asyncio.to_thread(adapter.public_url, "leads/a.jpg") == "https://first"
    adc.valid = False
    assert await asyncio.to_thread(adapter.public_url, "leads/a.jpg") == "https://second"
    assert adc.refresh.call_count == 2
    assert blob.generate_signed_url.call_count == 2
    assert blob.generate_signed_url.call_args.kwargs["method"] == "GET"
    assert blob.generate_signed_url.call_args.kwargs["expiration"] == timedelta(seconds=900)


@pytest.mark.parametrize("error", [Forbidden("sensitive"), TransportError("sensitive")])
async def test_signing_errors_do_not_return_public_url(
    adc: Mock, client: Mock, error: Exception
) -> None:
    client.bucket.return_value.blob.return_value.generate_signed_url.side_effect = error
    with pytest.raises(RuntimeError, match="No se pudo firmar") as caught:
        await asyncio.to_thread(GCSStorage(bucket="private").public_url, "leads/a.jpg")
    assert "sensitive" not in str(caught.value)
    assert caught.value.__suppress_context__


async def test_refresh_failure_does_not_attempt_signing(adc: Mock, client: Mock) -> None:
    adc.refresh.side_effect = RefreshError("sensitive-token")
    with pytest.raises(RuntimeError, match="RefreshError"):
        await GCSStorage(bucket="private").create_presigned_upload(
            key_prefix="leads", filename="a.jpg", content_type="image/jpeg"
        )
    client.bucket.return_value.blob.assert_not_called()


def test_missing_service_account_identity_fails(adc: Mock, client: Mock) -> None:
    adc.valid = True
    adc.service_account_email = "default"
    with pytest.raises(ValueError, match="email y token"):
        GCSStorage(bucket="private").public_url("leads/a.jpg")
    client.bucket.return_value.blob.assert_not_called()


async def test_delete_is_offloaded_and_missing_object_is_idempotent(
    adc: Mock, client: Mock
) -> None:
    loop_thread = threading.get_ident()
    blob = client.bucket.return_value.blob.return_value

    def delete() -> None:
        assert threading.get_ident() != loop_thread

    blob.delete.side_effect = delete
    adapter = GCSStorage(bucket="private")
    await adapter.delete("leads/a.jpg")
    client.bucket.return_value.blob.assert_called_with("leads/a.jpg")
    blob.delete.side_effect = NotFound("missing")
    await adapter.delete("leads/a.jpg")
    blob.delete.side_effect = Forbidden("sensitive")
    with pytest.raises(RuntimeError, match=r"No se pudo borrar.*Forbidden"):
        await adapter.delete("leads/a.jpg")


@pytest.mark.parametrize("method", ["GET", "PUT"])
async def test_real_sdk_uses_iam_signblob_with_keyless_compute_credentials(
    monkeypatch: pytest.MonkeyPatch, client: Mock, method: str
) -> None:
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    credentials = Credentials(service_account_email=EMAIL)
    credentials.token = "metadata-token"
    monkeypatch.setattr(
        f"{MODULE}.google.auth.default", Mock(return_value=(credentials, "project"))
    )
    client.universe_domain = "googleapis.com"
    client.api_endpoint = "https://storage.googleapis.com"
    bucket = Bucket(client, "private-photos")
    client.bucket.return_value = bucket
    transport = Mock(
        return_value=Mock(
            status=200,
            data=json.dumps({"signedBlob": base64.b64encode(b"iam-signature").decode()}).encode(),
        )
    )
    monkeypatch.setattr(
        "google.cloud.storage._signing.requests.Request", Mock(return_value=transport)
    )
    adapter = GCSStorage(bucket="private-photos")
    if method == "GET":
        url = await asyncio.to_thread(adapter.public_url, "leads/a.jpg")
    else:
        result = await adapter.create_presigned_upload(
            key_prefix="leads", filename="a.jpg", content_type="image/jpeg"
        )
        url = result.upload_url
    query = parse_qs(urlsplit(url).query)
    assert query["X-Goog-Algorithm"] == ["GOOG4-RSA-SHA256"]
    assert query["X-Goog-Expires"] == ["900"]
    assert query["X-Goog-Signature"] == [b"iam-signature".hex()]
    assert query["X-Goog-SignedHeaders"] == ["host" if method == "GET" else "content-type;host"]
    request = transport.call_args.kwargs
    assert request["method"] == "POST"
    assert request["url"] == (
        f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{EMAIL}:signBlob?alt=json"
    )
    assert request["headers"]["Authorization"] == "Bearer metadata-token"
    payload = base64.b64decode(json.loads(request["body"])["payload"])
    assert payload.startswith(b"GOOG4-RSA-SHA256\n")


async def test_s3_upload_contract_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock()
    client.generate_presigned_url.return_value = "https://signed-s3"
    monkeypatch.setattr(
        "app.infrastructure.adapters.storage.s3_adapter.boto3.client", Mock(return_value=client)
    )
    adapter = create_storage(settings(s3_access_key_id="key", s3_secret_access_key="secret"))
    result = await adapter.create_presigned_upload(
        key_prefix="leads", filename="a.png", content_type="image/png"
    )
    client.generate_presigned_url.assert_called_once_with(
        "put_object",
        Params={"Bucket": "reforma-hub-dev", "Key": result.storage_key, "ContentType": "image/png"},
        ExpiresIn=900,
    )
    assert result.method == "PUT"
    assert result.headers == {"Content-Type": "image/png"}
    assert result.upload_url == "https://signed-s3"
    await adapter.delete(result.storage_key)
    client.delete_object.assert_called_once_with(Bucket="reforma-hub-dev", Key=result.storage_key)
