"""Objetos de valor de los datos de contacto del cliente (PII)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
_PHONE_ALLOWED_RE = re.compile(r"^\+?[0-9]{6,15}$")


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not _EMAIL_RE.match(normalized):
            raise ValueError(f"Email invalido: {self.value!r}")
        object.__setattr__(self, "value", normalized)

    @property
    def masked(self) -> str:
        """Version enmascarada para mostrar antes de comprar el contacto."""
        local, _, domain = self.value.partition("@")
        visible = local[0] if local else "*"
        return f"{visible}{'*' * max(len(local) - 1, 3)}@{domain}"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    """Telefono en formato E.164 laxo (sin separadores, prefijo + opcional)."""

    value: str

    def __post_init__(self) -> None:
        compact = re.sub(r"[\s\-().]", "", self.value.strip())
        if not _PHONE_ALLOWED_RE.match(compact):
            raise ValueError(f"Telefono invalido: {self.value!r}")
        object.__setattr__(self, "value", compact)

    @property
    def masked(self) -> str:
        """Deja visibles solo los dos ultimos digitos."""
        return f"{'*' * max(len(self.value) - 2, 4)}{self.value[-2:]}"

    def __str__(self) -> str:
        return self.value
