"""Puerto de almacenamiento de archivos.

Hay dos instancias: la publica (fotos de solicitudes y de profesionales) y la privada
(documentos de alta del profesional: DNI, modelos de Hacienda). Del bucket privado
nunca se da una URL permanente, solo descargas firmadas de corta duracion.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    """Datos para que el navegador suba el archivo directamente al bucket."""

    storage_key: str
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str] = field(default_factory=dict)
    expires_in_seconds: int = 900


class StoragePort(ABC):
    @abstractmethod
    async def create_presigned_upload(
        self, *, key_prefix: str, filename: str, content_type: str
    ) -> PresignedUpload: ...

    @abstractmethod
    def public_url(self, storage_key: str) -> str: ...

    @abstractmethod
    async def signed_download_url(self, storage_key: str, *, filename: str) -> str:
        """URL de descarga que caduca en minutos. La unica via al bucket privado."""

    @abstractmethod
    async def delete(self, storage_key: str) -> None: ...
