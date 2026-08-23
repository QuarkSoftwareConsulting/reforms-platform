"""Schemas de solicitudes (leads).

La separacion entre `LeadPublicOut` y `LeadContactOut` es deliberada: el schema de
listado no tiene campos donde quepan los datos personales, asi que un descuido en
un endpoint no puede filtrarlos.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.infrastructure.api.schemas.common import ApiModel, MoneyOut

MIN_DESCRIPTION = 20
MAX_DESCRIPTION = 4000


class ConsentIn(ApiModel):
    accepted: bool = Field(description="El cliente marco la casilla de politica de privacidad")
    policy_version: str | None = Field(
        default=None, description="Version aceptada; si falta se usa la vigente del servidor"
    )


class CreateLeadIn(ApiModel):
    category_id: UUID
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(min_length=MIN_DESCRIPTION, max_length=MAX_DESCRIPTION)
    postal_code: str = Field(min_length=3, max_length=12)
    client_name: str = Field(min_length=2, max_length=200)
    client_phone: str = Field(min_length=6, max_length=20)
    client_email: str | None = Field(default=None, max_length=320)
    photo_keys: list[str] = Field(default_factory=list, max_length=8)
    consent: ConsentIn

    @field_validator("photo_keys")
    @classmethod
    def _reject_absolute_keys(cls, keys: list[str]) -> list[str]:
        """Solo se aceptan claves emitidas por nuestro endpoint de presign."""
        for key in keys:
            if not key.startswith("leads/") or ".." in key:
                raise ValueError(f"Clave de foto no valida: {key}")
        return keys


class CategoryOut(ApiModel):
    id: UUID
    slug: str
    name: str
    lead_price: MoneyOut


class LeadPublicOut(ApiModel):
    """Vista del explorador: sin nombre, telefono ni email del cliente."""

    id: UUID
    title: str
    description: str
    city: str
    province: str
    postal_code_prefix: str
    category: CategoryOut
    photo_urls: list[str]
    created_at: datetime
    remaining_slots: int
    distance_km: float | None = None
    masked_phone: str
    masked_email: str | None = None
    already_purchased: bool = False
    price: MoneyOut


class LeadListOut(ApiModel):
    items: list[LeadPublicOut]
    total: int
    limit: int
    offset: int


class ClientContactOut(ApiModel):
    """Datos personales del cliente. Solo se serializa tras una compra pagada."""

    name: str
    phone: str
    email: str | None = None


class PurchaseOut(ApiModel):
    id: UUID
    status: str
    amount: MoneyOut
    created_at: datetime
    paid_at: datetime | None = None
    reserved_until: datetime | None = None


class LeadDetailOut(ApiModel):
    lead: LeadPublicOut
    is_unlocked: bool
    contact: ClientContactOut | None = None
    purchase: PurchaseOut | None = None


class CreateLeadOut(ApiModel):
    id: UUID
    status: str
    city: str
    province: str
    created_at: datetime


class PresignPhotoIn(ApiModel):
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(min_length=3, max_length=100)
    size_bytes: int | None = Field(default=None, ge=1)


class PresignPhotoOut(ApiModel):
    storage_key: str
    upload_url: str
    method: str
    headers: dict[str, str]
    expires_in_seconds: int


class PostalCodeOut(ApiModel):
    code: str
    city: str
    province: str
    latitude: float
    longitude: float
