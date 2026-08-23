"""Adaptador de almacenamiento S3-compatible (MinIO en dev, Cloudflare R2 en prod).

La misma implementacion sirve para ambos: solo cambia el endpoint. El navegador
sube con una URL prefirmada, asi que los bytes nunca pasan por el API.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import UTC, datetime

import boto3
from botocore.client import Config

from app.application.ports import PresignedUpload, StoragePort

EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
}
_UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9._-]")


def safe_filename(filename: str, content_type: str) -> str:
    """Nombre de objeto seguro.

    Nunca se confia en el nombre que envia el navegador: podria contener `../` o
    caracteres que rompan la clave del bucket. Se conserva solo un slug corto y la
    extension se deduce del content-type declarado.
    """
    stem = _UNSAFE_CHARS.sub("-", filename.rsplit(".", 1)[0])[:40].strip("-") or "foto"
    extension = EXTENSION_BY_CONTENT_TYPE.get(content_type, "bin")
    return f"{stem}.{extension}"


class S3Storage(StoragePort):
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        region: str = "auto",
        public_base_url: str = "",
        presign_expires_seconds: int = 900,
    ) -> None:
        self._bucket = bucket
        self._public_base_url = (public_base_url or f"{endpoint_url}/{bucket}").rstrip("/")
        self._expires = presign_expires_seconds
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    async def create_presigned_upload(
        self, *, key_prefix: str, filename: str, content_type: str
    ) -> PresignedUpload:
        today = datetime.now(UTC).strftime("%Y/%m/%d")
        key = f"{key_prefix}/{today}/{uuid.uuid4().hex}/{safe_filename(filename, content_type)}"

        url = await asyncio.to_thread(
            self._client.generate_presigned_url,
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=self._expires,
        )
        return PresignedUpload(
            storage_key=key,
            upload_url=url,
            method="PUT",
            headers={"Content-Type": content_type},
            expires_in_seconds=self._expires,
        )

    def public_url(self, storage_key: str) -> str:
        return f"{self._public_base_url}/{storage_key.lstrip('/')}"

    async def delete(self, storage_key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=storage_key)
