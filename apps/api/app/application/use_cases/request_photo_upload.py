"""Caso de uso: obtener una URL prefirmada para subir una foto de la solicitud.

El navegador sube el archivo directamente al bucket; el API nunca ve los bytes.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports import PresignedUpload, StoragePort
from app.domain.exceptions import ValidationError

ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/heic"})
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@dataclass(slots=True)
class RequestPhotoUpload:
    storage: StoragePort

    async def execute(
        self, *, filename: str, content_type: str, size_bytes: int | None = None
    ) -> PresignedUpload:
        normalized = content_type.split(";")[0].strip().lower()
        if normalized not in ALLOWED_CONTENT_TYPES:
            raise ValidationError(
                f"Tipo de archivo no permitido: {content_type}. "
                f"Admitidos: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
            )
        if size_bytes is not None and size_bytes > MAX_UPLOAD_BYTES:
            raise ValidationError(
                f"La foto supera el maximo de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
            )
        return await self.storage.create_presigned_upload(
            key_prefix="leads", filename=filename, content_type=normalized
        )
