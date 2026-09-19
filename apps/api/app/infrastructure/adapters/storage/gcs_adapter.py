"""GCS privado con ADC y firma remota mediante IAM Credentials, sin claves JSON."""

from __future__ import annotations

import asyncio
import os
from datetime import timedelta
from threading import Lock

import google.auth
from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.cloud import storage
from requests.exceptions import RequestException

from app.application.ports import PresignedUpload, StoragePort
from app.infrastructure.adapters.storage.object_keys import create_object_key


class GCSStorage(StoragePort):
    def __init__(self, *, bucket: str, signed_url_expires_seconds: int = 900) -> None:
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError("GCS requiere ADC del runtime, sin GOOGLE_APPLICATION_CREDENTIALS")
        self._credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._client = storage.Client(project=project, credentials=self._credentials)
        self._bucket = self._client.bucket(bucket)
        self._expires = signed_url_expires_seconds
        self._credentials_lock = Lock()

    def _signed_url(self, key: str, *, method: str, content_type: str | None = None) -> str:
        try:
            # El refresh resuelve el email real del metadata server y renueva el token.
            # Varias peticiones pueden firmar simultaneamente desde distintos threads.
            with self._credentials_lock:
                if not self._credentials.valid:
                    self._credentials.refresh(Request())
                email = getattr(self._credentials, "service_account_email", None)
                token = self._credentials.token
            if not isinstance(email, str) or "@" not in email or not token:
                raise ValueError("GCS requiere ADC de una cuenta de servicio con email y token")

            # Ambos argumentos fuerzan signBlob en el SDK; ADC de Cloud Run no tiene clave.
            url: str = self._bucket.blob(key).generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=self._expires),
                method=method,
                content_type=content_type,
                credentials=self._credentials,
                service_account_email=email,
                access_token=token,
            )
            return url
        except (GoogleAuthError, GoogleAPICallError, RequestException) as exc:
            # Los errores del SDK pueden incluir URLs o tokens; no llegan a los logs.
            raise RuntimeError(f"No se pudo firmar la URL GCS ({type(exc).__name__})") from None

    async def create_presigned_upload(
        self, *, key_prefix: str, filename: str, content_type: str
    ) -> PresignedUpload:
        key = create_object_key(key_prefix, filename, content_type)
        url = await asyncio.to_thread(
            self._signed_url, key, method="PUT", content_type=content_type
        )
        return PresignedUpload(
            storage_key=key,
            upload_url=url,
            method="PUT",
            headers={"Content-Type": content_type},
            expires_in_seconds=self._expires,
        )

    def public_url(self, storage_key: str) -> str:
        """Conserva el puerto; en GCS la URL de lectura caduca y nunca se persiste.

        El llamador debe ejecutar la serializacion fuera del event loop.
        """
        return self._signed_url(storage_key.lstrip("/"), method="GET")

    async def delete(self, storage_key: str) -> None:
        try:
            await asyncio.to_thread(self._bucket.blob(storage_key).delete)
        except NotFound:
            # Igual que DeleteObject de S3, borrar un objeto ausente es idempotente.
            return
        except (GoogleAuthError, GoogleAPICallError, RequestException) as exc:
            raise RuntimeError(f"No se pudo borrar el objeto GCS ({type(exc).__name__})") from None
