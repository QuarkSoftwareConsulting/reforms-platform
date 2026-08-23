"""Categoria de oficio y su precio por lead."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from app.domain.exceptions import ValidationError
from app.domain.value_objects import Money

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(slots=True)
class Category:
    """Oficio (carpinteria, fontaneria...). El precio del lead se configura aqui."""

    id: UUID
    slug: str
    name_es: str
    name_en: str
    lead_price: Money
    active: bool = True

    def __post_init__(self) -> None:
        self.slug = self.slug.strip().lower()
        if not _SLUG_RE.match(self.slug):
            raise ValidationError(f"Slug de categoria invalido: {self.slug!r}")
        if self.lead_price.amount_cents <= 0:
            raise ValidationError("El precio del lead debe ser mayor que cero")

    def name(self, locale: str) -> str:
        return self.name_en if locale.lower().startswith("en") else self.name_es
