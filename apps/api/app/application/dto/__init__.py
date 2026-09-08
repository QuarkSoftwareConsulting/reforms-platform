"""DTOs de entrada/salida de los casos de uso.

Son estructuras planas de dominio (no Pydantic) para que la capa de aplicacion no
dependa del framework web.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.models import (
    Category,
    ClientContact,
    Lead,
    LeadPublicView,
    LeadSource,
    LeadStatus,
    Professional,
    Purchase,
    PurchaseReview,
)
from app.domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class ConsentInput:
    accepted: bool
    policy_version: str
    ip_address: str | None = None
    user_agent: str | None = None
    channel: str | None = None
    campaign_reference: str | None = None
    accepted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CreateLeadInput:
    category_id: UUID
    title: str
    description: str
    postal_code: str
    client_name: str
    client_phone: str
    client_email: str | None = None
    photo_keys: list[str] = field(default_factory=list)
    consent: ConsentInput | None = None


@dataclass(frozen=True, slots=True)
class LeadListItem:
    """Fila del explorador: nunca contiene datos personales del cliente."""

    lead: LeadPublicView
    category: Category
    price: Money
    distance_km: float | None
    already_purchased: bool


@dataclass(frozen=True, slots=True)
class LeadListResult:
    items: list[LeadListItem]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class LeadDetail:
    """Detalle de un lead. `contact` viene relleno solo si hay compra pagada."""

    lead: LeadPublicView
    category: Category
    price: Money
    distance_km: float | None
    contact: ClientContact | None
    purchase: Purchase | None

    @property
    def is_unlocked(self) -> bool:
        return self.contact is not None


@dataclass(frozen=True, slots=True)
class LeadPricing:
    """Vista de precios de un lead para el admin.

    Lleva las dos cifras a la vez porque la decision del admin es comparativa:
    ve el precio sugerido del oficio y decide si este contacto vale otra cosa.
    """

    lead_id: UUID
    category: Category
    suggested_price: Money
    sale_price: Money
    is_custom: bool


@dataclass(frozen=True, slots=True)
class StartPurchaseResult:
    purchase_id: UUID
    checkout_url: str
    checkout_session_id: str
    amount: Money
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class PurchasedContact:
    """Entrada del historial "Mis contactos"."""

    purchase: Purchase
    lead: Lead
    category: Category
    contact: ClientContact | None


@dataclass(frozen=True, slots=True)
class UpsertProfessionalInput:
    business_name: str
    phone: str
    postal_code: str
    service_radius_km: int
    category_ids: set[UUID]


@dataclass(frozen=True, slots=True)
class ProfessionalProfile:
    professional: Professional
    categories: list[Category]


@dataclass(frozen=True, slots=True)
class AdminLeadItem:
    """Fila administrativa sin campos de contacto del cliente."""

    lead: LeadPublicView
    category: Category
    price: Money
    status: LeadStatus
    source: LeadSource
    purchases_count: int
    max_purchases: int


@dataclass(frozen=True, slots=True)
class AdminLeadListResult:
    items: list[AdminLeadItem]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class AdminPurchaseItem:
    purchase: Purchase
    professional: Professional | None
    review_count: int


@dataclass(frozen=True, slots=True)
class AdminProfessionalItem:
    professional: Professional
    categories: list[Category]


@dataclass(frozen=True, slots=True)
class AdminProfessionalListResult:
    items: list[AdminProfessionalItem]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class AdminMetrics:
    leads_total: int
    leads_published: int
    leads_exhausted: int
    leads_disabled: int
    leads_organic: int
    leads_admin: int
    professionals_total: int
    paid_purchases: int
    paid_leads: int
    revenue_by_currency: dict[str, int]

    @property
    def coverage_rate(self) -> float:
        return self.paid_leads / self.leads_total if self.leads_total else 0.0

    @property
    def liquidity(self) -> float:
        return self.paid_purchases / self.leads_total if self.leads_total else 0.0


@dataclass(frozen=True, slots=True)
class PurchaseReviewEntry:
    review: PurchaseReview
