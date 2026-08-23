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
    Professional,
    Purchase,
)
from app.domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class ConsentInput:
    accepted: bool
    policy_version: str
    ip_address: str | None = None
    user_agent: str | None = None


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
