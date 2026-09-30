"""Schemas del perfil profesional y de su alta (F02)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.application.use_cases import UploadPurpose
from app.domain.models import (
    MAX_WORK_PHOTOS,
    DocumentKind,
    ProfessionalType,
    VerificationStatus,
)
from app.infrastructure.api.schemas.billing import AccountOut
from app.infrastructure.api.schemas.common import ApiModel
from app.infrastructure.api.schemas.leads import CategoryOut, ServiceOut

MAX_KEY = 500


class UpsertProfessionalIn(ApiModel):
    """Perfil completo: el formulario lo envia entero en cada guardado."""

    business_name: str = Field(min_length=2, max_length=200)
    phone: str = Field(min_length=6, max_length=20, description="Movil espanol")
    postal_code: str = Field(min_length=3, max_length=12)
    service_radius_km: int = Field(ge=1, le=300)
    category_ids: list[UUID] = Field(min_length=1, max_length=12)
    service_ids: list[UUID] = Field(default_factory=list, max_length=100)
    professional_type: ProfessionalType | None = None
    legal_name: str | None = Field(default=None, max_length=200)
    tax_id: str | None = Field(default=None, max_length=20, description="NIF, NIE o CIF")
    address: str | None = Field(default=None, max_length=300)
    profile_photo_key: str | None = Field(default=None, max_length=MAX_KEY)
    logo_key: str | None = Field(default=None, max_length=MAX_KEY)
    work_photo_keys: list[str] = Field(default_factory=list, max_length=MAX_WORK_PHOTOS)


class MediaOut(ApiModel):
    key: str
    url: str


class ProfessionalDocumentOut(ApiModel):
    id: UUID
    kind: DocumentKind
    filename: str
    uploaded_at: datetime


class VerificationOut(ApiModel):
    status: VerificationStatus
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    missing: list[str] = Field(
        description="Lo que falta para enviar el alta a revision (claves estables)"
    )


class ProfessionalOut(ApiModel):
    id: UUID
    business_name: str
    phone: str
    postal_code: str
    city: str | None = None
    province: str | None = None
    service_radius_km: int
    categories: list[CategoryOut]
    services: list[ServiceOut]
    professional_type: ProfessionalType | None = None
    legal_name: str | None = None
    tax_id: str | None = None
    address: str | None = None
    profile_photo: MediaOut | None = None
    logo: MediaOut | None = None
    work_photos: list[MediaOut]
    documents: list[ProfessionalDocumentOut]
    verification: VerificationOut


class ProfessionalUploadIn(ApiModel):
    purpose: UploadPurpose = Field(description="media (bucket publico) o document (privado)")
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(min_length=3, max_length=100)
    size_bytes: int | None = Field(default=None, ge=1)


class AddDocumentIn(ApiModel):
    kind: DocumentKind
    storage_key: str = Field(min_length=1, max_length=MAX_KEY)
    filename: str = Field(min_length=1, max_length=200)


class MeOut(ApiModel):
    user_id: UUID
    email: str
    role: str
    display_name: str | None = None
    professional: ProfessionalOut | None = None
    account: AccountOut | None = None
    """Estado de la recarga; None si aun no tiene perfil profesional."""
