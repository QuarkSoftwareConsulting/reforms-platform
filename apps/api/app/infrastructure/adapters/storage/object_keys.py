"""Claves compartidas por los adaptadores de almacenamiento."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

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


def create_object_key(key_prefix: str, filename: str, content_type: str) -> str:
    today = datetime.now(UTC).strftime("%Y/%m/%d")
    return f"{key_prefix}/{today}/{uuid.uuid4().hex}/{safe_filename(filename, content_type)}"
