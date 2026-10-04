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
    CreditEntry,
    Lead,
    LeadPublicView,
    LeadSource,
    LeadStatus,
    Professional,
    ProfessionalAccount,
    ProfessionalDocument,
    ProfessionalType,
    ProjectSchedule,
    PropertyType,
    Purchase,
    PurchaseReview,
    SubscriptionStatus,
    VerificationEvent,
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
    service_ids: list[UUID] = field(default_factory=list)
    property_type: PropertyType | None = None
    schedule: ProjectSchedule | None = None
    phone_verification_code: str | None = None


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
    """Resultado de iniciar una compra.

    Si el saldo cubre el precio entero la compra ya esta pagada: no hay checkout
    (`checkout_url` es None) y el contacto queda desbloqueado en el acto.
    """

    purchase_id: UUID
    checkout_url: str | None
    checkout_session_id: str | None
    amount: Money
    expires_at: datetime | None
    credit_applied: Money
    amount_due: Money

    @property
    def paid_with_credit(self) -> bool:
        return self.checkout_url is None


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
    service_ids: set[UUID] = field(default_factory=set)
    professional_type: ProfessionalType | None = None
    legal_name: str | None = None
    tax_id: str | None = None
    address: str | None = None
    profile_photo_key: str | None = None
    logo_key: str | None = None
    work_photo_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProfessionalProfile:
    professional: Professional
    categories: list[Category]


@dataclass(frozen=True, slots=True)
class DocumentDownload:
    document: ProfessionalDocument
    download_url: str
    """Firmada y de corta duracion: nunca se guarda ni se envia fuera del panel."""


@dataclass(frozen=True, slots=True)
class VerificationDossier:
    """Lo que el admin revisa para aprobar o rechazar un alta."""

    professional: Professional
    categories: list[Category]
    documents: list[DocumentDownload]
    events: list[VerificationEvent]
    email: str | None


@dataclass(frozen=True, slots=True)
class RejectionResult:
    professional: Professional
    refunded: Money | None
    """Importe del primer cobro reembolsado; `None` si no llego a pagar."""
    subscription_canceled: bool


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
    account: ProfessionalAccount | None = None
    account_active: bool = False


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
    active_accounts: int = 0
    topup_revenue_by_currency: dict[str, int] = field(default_factory=dict)

    @property
    def coverage_rate(self) -> float:
        return self.paid_leads / self.leads_total if self.leads_total else 0.0

    @property
    def liquidity(self) -> float:
        return self.paid_purchases / self.leads_total if self.leads_total else 0.0


@dataclass(frozen=True, slots=True)
class PurchaseReviewEntry:
    review: PurchaseReview


@dataclass(frozen=True, slots=True)
class AccountSummary:
    """Estado de la recarga y del saldo tal como lo ve el profesional."""

    status: SubscriptionStatus
    is_active: bool
    balance: Money
    topup_amount: Money
    current_period_end: datetime | None
    can_manage_billing: bool
    """Tiene cliente en la pasarela: puede abrir el portal de pagos."""
    entries: list[CreditEntry] = field(default_factory=list)
    debt: Money | None = None
    """Recarga devuelta por el banco que ya se habia gastado. Con deuda no se compra."""


@dataclass(frozen=True, slots=True)
class SubscriptionPriceInfo:
    """Mensualidad vigente para las suscripciones nuevas."""

    amount: Money
    stripe_price_id: str | None
    updated_at: datetime | None
    is_default: bool
    """True si el admin aun no la ha fijado y se usa la de configuracion."""
