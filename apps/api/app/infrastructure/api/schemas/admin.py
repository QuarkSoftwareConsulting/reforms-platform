"""Schemas del area de administracion.

Los importes se reciben en centimos, la misma unidad que guarda `Money` y que usa
Stripe: aceptar euros con decimales obligaria a redondear en el borde del API y
seria la puerta de entrada de los errores de coma flotante.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.domain.models import (
    MAX_SALE_PRICE_CENTS,
    MAX_SERVICES_PER_LEAD,
    ProjectSchedule,
    PropertyType,
    UserRole,
    VerificationStatus,
)
from app.infrastructure.api.schemas.billing import AdminAccountOut
from app.infrastructure.api.schemas.common import ApiModel, MoneyOut
from app.infrastructure.api.schemas.leads import CategoryOut, CreateLeadOut, PurchaseOut
from app.infrastructure.api.schemas.professionals import ProfessionalDocumentOut, ProfessionalOut


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
    # Opcionales: un lead captado en una campana externa puede no traerlos.
    service_ids: list[UUID] = Field(default_factory=list, max_length=MAX_SERVICES_PER_LEAD)
    property_type: PropertyType | None = None
    schedule: ProjectSchedule | None = None

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
    active_accounts: int = 0
    topup_revenue_by_currency: dict[str, MoneyOut] = Field(default_factory=dict)


class AdminProfessionalOut(ApiModel):
    id: UUID
    business_name: str
    legal_name: str | None = None
    postal_code: str
    city: str | None = None
    province: str | None = None
    service_radius_km: int
    categories: list[CategoryOut]
    account: AdminAccountOut | None = None
    verification_status: VerificationStatus
    submitted_at: datetime | None = None


class DocumentDownloadOut(ProfessionalDocumentOut):
    download_url: str = Field(description="Firmada; caduca en minutos")


class VerificationEventOut(ApiModel):
    from_status: VerificationStatus
    to_status: VerificationStatus
    actor_user_id: UUID | None = None
    note: str | None = None
    created_at: datetime


class VerificationDossierOut(ApiModel):
    professional: ProfessionalOut
    email: str | None = None
    documents: list[DocumentDownloadOut]
    events: list[VerificationEventOut]


class RejectProfessionalIn(ApiModel):
    reason: str = Field(min_length=3, max_length=1000)


class RejectionOut(ApiModel):
    professional: ProfessionalOut
    refunded: MoneyOut | None = None
    subscription_canceled: bool


class AdminProfessionalListOut(ApiModel):
    items: list[AdminProfessionalOut]
    total: int
    limit: int
    offset: int


class AdminPurchaseLeadOut(ApiModel):
    """Lo justo para saber que se vendio. Sin datos de contacto del cliente."""

    id: UUID
    title: str
    city: str | None = None
    province: str | None = None
    category: CategoryOut | None = None


class AdminPurchaseOut(ApiModel):
    purchase: PurchaseOut
    professional: AdminProfessionalOut | None = None
    review_count: int
    lead: AdminPurchaseLeadOut | None = Field(
        default=None, description="Solo en el listado global de compras"
    )


class AdminPurchaseListOut(ApiModel):
    items: list[AdminPurchaseOut]
    total: int
    limit: int
    offset: int


class AdminUserOut(ApiModel):
    id: UUID
    email: str
    display_name: str | None = None
    role: UserRole
    created_at: datetime
    professional: AdminProfessionalOut | None = Field(
        default=None, description="Resumen del perfil profesional, si lo tiene"
    )


class AdminUserListOut(ApiModel):
    items: list[AdminUserOut]
    total: int
    limit: int
    offset: int


class SetUserRoleIn(ApiModel):
    role: UserRole
    note: str | None = Field(default=None, max_length=500)


class UserRoleEventOut(ApiModel):
    from_role: UserRole
    to_role: UserRole
    actor_user_id: UUID | None = None
    note: str | None = None
    created_at: datetime


class DailyMetricsOut(ApiModel):
    day: date
    leads_created: int
    paid_purchases: int
    revenue_by_currency: dict[str, MoneyOut]
    topups: int
    topup_revenue_by_currency: dict[str, MoneyOut]


class MetricsTimeseriesOut(ApiModel):
    start: date
    end: date
    timezone: str
    points: list[DailyMetricsOut]


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
    "AdminPurchaseLeadOut",
    "AdminPurchaseListOut",
    "AdminPurchaseOut",
    "AdminUserListOut",
    "AdminUserOut",
    "CreateLeadOut",
    "DailyMetricsOut",
    "LeadPricingOut",
    "MetricsTimeseriesOut",
    "PurchaseReviewIn",
    "PurchaseReviewOut",
    "SetCategoryPriceIn",
    "SetLeadPriceIn",
    "SetUserRoleIn",
    "UserRoleEventOut",
]
