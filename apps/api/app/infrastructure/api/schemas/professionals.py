"""Schemas del perfil profesional."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.infrastructure.api.schemas.common import ApiModel
from app.infrastructure.api.schemas.leads import CategoryOut


class UpsertProfessionalIn(ApiModel):
    business_name: str = Field(min_length=2, max_length=200)
    phone: str = Field(min_length=6, max_length=20)
    postal_code: str = Field(min_length=3, max_length=12)
    service_radius_km: int = Field(ge=1, le=300)
    category_ids: list[UUID] = Field(min_length=1, max_length=12)


class ProfessionalOut(ApiModel):
    id: UUID
    business_name: str
    phone: str
    postal_code: str
    city: str | None = None
    province: str | None = None
    service_radius_km: int
    categories: list[CategoryOut]


class MeOut(ApiModel):
    user_id: UUID
    email: str
    role: str
    display_name: str | None = None
    professional: ProfessionalOut | None = None
