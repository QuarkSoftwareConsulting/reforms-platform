"""Schemas del area de administracion.

Los importes se reciben en centimos, la misma unidad que guarda `Money` y que usa
Stripe: aceptar euros con decimales obligaria a redondear en el borde del API y
seria la puerta de entrada de los errores de coma flotante.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.domain.models import MAX_SALE_PRICE_CENTS
from app.infrastructure.api.schemas.common import ApiModel, MoneyOut
from app.infrastructure.api.schemas.leads import CategoryOut, CreateLeadOut, PurchaseOut


class SetLeadPriceIn(ApiModel):
    amount_cents: int | None = Field(
        default=None,
        gt=0,
        le=MAX_SALE_PRICE_CENTS,
        description=(
            "Precio de venta de este contacto, en centimos. "
            "`null` borra el precio propio y vuelve al sugerido de la categoria."
        ),
    )
    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Divisa ISO-4217; si falta se usa la del oficio.",
    )


class SetCategoryPriceIn(ApiModel):
    amount_cents: int = Field(gt=0, le=MAX_SALE_PRICE_CENTS)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class LeadPricingOut(ApiModel):
    """Precio efectivo de un contacto junto a la referencia de su oficio."""

    lead_id: UUID
    category: CategoryOut
    suggested_price: MoneyOut
    sale_price: MoneyOut
    is_custom: bool


class AdminConsentIn(ApiModel):
    policy_version: str = Field(min_length=1, max_length=40)
    accepted_at: datetime
    channel: str = Field(min_length=2, max_length=120)
    campaign_reference: str | None = Field(default=None, max_length=200)


class AdminCreateLeadIn(ApiModel):
    category_id: UUID
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(min_length=20, max_length=4000)
    postal_code: str = Field(min_length=3, max_length=12)
    client_name: str = Field(min_length=2, max_length=200)
    client_phone: str = Field(min_length=6, max_length=20)
    client_email: str | None = Field(default=None, max_length=320)
    photo_keys: list[str] = Field(default_factory=list, max_length=8)
    consent: AdminConsentIn

    @field_validator("photo_keys")
    @classmethod
    def _reject_absolute_keys(cls, keys: list[str]) -> list[str]:
        for key in keys:
            if not key.startswith("leads/") or ".." in key:
                raise ValueError(f"Clave de foto no valida: {key}")
        return keys


class AdminLeadOut(ApiModel):
    """Fila de inventario sin nombre, telefono ni email del cliente."""

    id: UUID
    title: str
    description: str
    city: str
    province: str
    postal_code_prefix: str
    category: CategoryOut
    photo_urls: list[str]
    created_at: datetime
    status: str
    source: str
    purchases_count: int
    max_purchases: int
    remaining_slots: int
    price: MoneyOut


class AdminLeadListOut(ApiModel):
    items: list[AdminLeadOut]
    total: int
    limit: int
    offset: int


class AdminLeadStatusOut(ApiModel):
    id: UUID
    status: str


class AdminMetricsOut(ApiModel):
    leads_total: int
    leads_published: int
    leads_exhausted: int
    leads_disabled: int
    leads_organic: int
    leads_admin: int
    professionals_total: int
    paid_purchases: int
    paid_leads: int
    coverage_rate: float
    liquidity: float
    revenue_by_currency: dict[str, MoneyOut]


class AdminProfessionalOut(ApiModel):
    id: UUID
    business_name: str
    postal_code: str
    city: str | None = None
    province: str | None = None
    service_radius_km: int
    categories: list[CategoryOut]


class AdminProfessionalListOut(ApiModel):
    items: list[AdminProfessionalOut]
    total: int
    limit: int
    offset: int


class AdminPurchaseOut(ApiModel):
    purchase: PurchaseOut
    professional: AdminProfessionalOut | None = None
    review_count: int


class PurchaseReviewIn(ApiModel):
    note: str = Field(min_length=3, max_length=500)


class PurchaseReviewOut(ApiModel):
    id: UUID
    purchase_id: UUID
    created_at: datetime


__all__ = [
    "AdminConsentIn",
    "AdminCreateLeadIn",
    "AdminLeadListOut",
    "AdminLeadOut",
    "AdminLeadStatusOut",
    "AdminMetricsOut",
    "AdminProfessionalListOut",
    "AdminProfessionalOut",
    "AdminPurchaseOut",
    "CreateLeadOut",
    "LeadPricingOut",
    "PurchaseReviewIn",
    "PurchaseReviewOut",
    "SetCategoryPriceIn",
    "SetLeadPriceIn",
]
