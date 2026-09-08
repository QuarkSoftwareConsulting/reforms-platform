"""Marca auditable de una compra que requiere revision manual."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class PurchaseReview:
    """Nota append-only para que soporte pueda investigar una compra."""

    id: UUID
    purchase_id: UUID
    reviewed_by_user_id: UUID
    note: str
    created_at: datetime

    def __post_init__(self) -> None:
        note = self.note.strip()
        if not 3 <= len(note) <= 500:
            raise ValidationError("La nota de revision debe tener entre 3 y 500 caracteres")
        object.__setattr__(self, "note", note)
