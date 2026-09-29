"""Archivos del alta del profesional: fotos (publicas) y documentos (privados).

El navegador sube directamente al bucket con una URL prefirmada; el API nunca ve los
bytes. Lo que si decide el API es DONDE va cada archivo: las fotos al bucket publico
(se ensenaran a los clientes) y los documentos de identidad y de Hacienda al privado,
del que solo el admin descarga con URLs firmadas de corta duracion.

Las claves llevan el id del profesional en el prefijo. Al registrar un archivo se
comprueba ese prefijo: nadie puede adjuntar a su perfil un archivo subido por otro.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.application.ports import (
    ClockPort,
    IdGeneratorPort,
    PresignedUpload,
    ProfessionalRepositoryPort,
    StoragePort,
    UnitOfWork,
)
from app.domain.exceptions import ProfessionalNotFoundError, ValidationError
from app.domain.models import DocumentKind, Professional, ProfessionalDocument

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/heic"})
DOCUMENT_TYPES = IMAGE_TYPES | {"application/pdf"}
MAX_FILENAME = 200


class UploadPurpose(StrEnum):
    MEDIA = "media"
    """Foto del rostro, logo o trabajos realizados: bucket publico."""

    DOCUMENT = "document"
    """Documentos de alta: bucket privado."""


def media_prefix(professional_id: UUID) -> str:
    return f"professionals/{professional_id}/media"


def document_prefix(professional_id: UUID) -> str:
    return f"professionals/{professional_id}/documents"


def assert_own_key(key: str, prefix: str) -> None:
    if not key.startswith(f"{prefix}/") or ".." in key:
        raise ValidationError("El archivo no pertenece a este perfil")


async def _load(professionals: ProfessionalRepositoryPort, professional_id: UUID) -> Professional:
    professional = await professionals.get(professional_id)
    if professional is None:
        raise ProfessionalNotFoundError()
    return professional


@dataclass(slots=True)
class RequestProfessionalUpload:
    media: StoragePort
    documents: StoragePort

    async def execute(
        self,
        *,
        professional_id: UUID,
        purpose: UploadPurpose,
        filename: str,
        content_type: str,
        size_bytes: int | None = None,
    ) -> PresignedUpload:
        normalized = content_type.split(";")[0].strip().lower()
        allowed = IMAGE_TYPES if purpose is UploadPurpose.MEDIA else DOCUMENT_TYPES
        if normalized not in allowed:
            raise ValidationError(
                f"Tipo de archivo no permitido: {content_type}. "
                f"Admitidos: {', '.join(sorted(allowed))}"
            )
        if size_bytes is not None and size_bytes > MAX_UPLOAD_BYTES:
            raise ValidationError(
                f"El archivo supera el maximo de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
            )
        if purpose is UploadPurpose.MEDIA:
            return await self.media.create_presigned_upload(
                key_prefix=media_prefix(professional_id),
                filename=filename,
                content_type=normalized,
            )
        return await self.documents.create_presigned_upload(
            key_prefix=document_prefix(professional_id),
            filename=filename,
            content_type=normalized,
        )


@dataclass(slots=True)
class AddProfessionalDocument:
    """Adjunta al alta un documento ya subido al bucket privado."""

    professionals: ProfessionalRepositoryPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork

    async def execute(
        self, *, professional_id: UUID, kind: DocumentKind, storage_key: str, filename: str
    ) -> ProfessionalDocument:
        assert_own_key(storage_key, document_prefix(professional_id))
        filename = filename.strip()[:MAX_FILENAME] or "documento"
        professional = await _load(self.professionals, professional_id)
        document = ProfessionalDocument(
            id=self.ids.new_id(),
            kind=kind,
            storage_key=storage_key,
            filename=filename,
            uploaded_at=self.clock.now(),
        )
        professional.add_document(document)
        async with self.uow:
            await self.professionals.update(professional)
        return document


@dataclass(slots=True)
class RemoveProfessionalDocument:
    professionals: ProfessionalRepositoryPort
    documents: StoragePort
    uow: UnitOfWork

    async def execute(self, *, professional_id: UUID, document_id: UUID) -> None:
        professional = await _load(self.professionals, professional_id)
        removed = professional.remove_document(document_id)
        async with self.uow:
            await self.professionals.update(professional)
        # Despues de guardar: si el borrado del objeto falla, queda un archivo
        # huerfano en el bucket privado, no un documento sin archivo en el perfil.
        await self.documents.delete(removed.storage_key)
