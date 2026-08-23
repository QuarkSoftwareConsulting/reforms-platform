"""Entidad Lead: la solicitud de trabajo publicada por un cliente.

Aqui vive la regla mas importante del negocio: un mismo lead solo puede venderse a
un numero limitado de profesionales (lead capping). El modelo no sabe nada de SQL,
HTTP ni Stripe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.exceptions import (
    CategoryMismatchError,
    ConsentRequiredError,
    ContactLockedError,
    LeadAlreadyPurchasedError,
    LeadCapReachedError,
    LeadNotPurchasableError,
    ValidationError,
)
from app.domain.models.enums import LeadSource, LeadStatus
from app.domain.value_objects import Coordinates, Email, PhoneNumber, PostalCode

MIN_DESCRIPTION_LENGTH = 20
MAX_DESCRIPTION_LENGTH = 4000
MAX_TITLE_LENGTH = 140
MAX_PHOTOS = 8


@dataclass(frozen=True, slots=True)
class LeadPhoto:
    storage_key: str
    sort_order: int = 0
    id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ClientContact:
    """Los datos personales del cliente. Es lo que el profesional compra."""

    name: str
    phone: PhoneNumber
    email: Email | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("El nombre del cliente es obligatorio")


@dataclass(frozen=True, slots=True)
class LeadLocation:
    postal_code: PostalCode
    city: str
    province: str
    coordinates: Coordinates


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    """Prueba auditable del consentimiento RGPD para ceder los datos del cliente."""

    policy_version: str
    ip_address: str | None
    user_agent: str | None
    accepted_at: datetime
    max_recipients: int

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ConsentRequiredError("Falta la version de la politica aceptada")


@dataclass(slots=True)
class Lead:
    """Solicitud de trabajo. Mutable solo a traves de sus metodos de negocio."""

    id: UUID
    category_id: UUID
    title: str
    description: str
    location: LeadLocation
    contact: ClientContact
    created_at: datetime
    status: LeadStatus = LeadStatus.PUBLISHED
    source: LeadSource = LeadSource.ORGANIC
    max_purchases: int = 3
    purchases_count: int = 0
    published_at: datetime | None = None
    photos: list[LeadPhoto] = field(default_factory=list)
    consent: ConsentRecord | None = None

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.description = self.description.strip()
        if not self.title or len(self.title) > MAX_TITLE_LENGTH:
            raise ValidationError(f"El titulo debe tener entre 1 y {MAX_TITLE_LENGTH} caracteres")
        if not MIN_DESCRIPTION_LENGTH <= len(self.description) <= MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"La descripcion debe tener entre {MIN_DESCRIPTION_LENGTH} y "
                f"{MAX_DESCRIPTION_LENGTH} caracteres"
            )
        if len(self.photos) > MAX_PHOTOS:
            raise ValidationError(f"Maximo {MAX_PHOTOS} fotos por solicitud")
        if self.max_purchases < 1:
            raise ValidationError("max_purchases debe ser al menos 1")
        if self.purchases_count < 0:
            raise ValidationError("purchases_count no puede ser negativo")
        # Un lead organico sin consentimiento registrado nunca debe existir: seria
        # una cesion de datos personales sin base legal.
        if self.source is LeadSource.ORGANIC and self.consent is None:
            raise ConsentRequiredError(
                "Un lead publicado por el cliente requiere registro de consentimiento"
            )

    # ----------------------------- Consultas -----------------------------

    @property
    def is_open(self) -> bool:
        """True si el lead admite al menos una compra mas."""
        return self.status is LeadStatus.PUBLISHED and self.purchases_count < self.max_purchases

    @property
    def remaining_slots(self) -> int:
        return max(self.max_purchases - self.purchases_count, 0)

    # ----------------------------- Reglas --------------------------------

    def assert_purchasable(
        self,
        *,
        occupied_slots: int,
        already_purchased_by_professional: bool,
        professional_category_ids: set[UUID] | None = None,
    ) -> None:
        """Valida que un profesional pueda comprar este lead.

        `occupied_slots` lo calcula el repositorio contando las compras vivas
        (pagadas + reservas no caducadas) bajo un bloqueo de fila, de modo que dos
        compras simultaneas no puedan superar el cap.
        """
        if self.status is LeadStatus.DISABLED:
            raise LeadNotPurchasableError("Esta solicitud fue retirada de la plataforma")
        if self.status is LeadStatus.EXHAUSTED:
            raise LeadCapReachedError()
        if already_purchased_by_professional:
            raise LeadAlreadyPurchasedError()
        if occupied_slots >= self.max_purchases:
            raise LeadCapReachedError()
        if (
            professional_category_ids is not None
            and self.category_id not in professional_category_ids
        ):
            raise CategoryMismatchError()

    def register_paid_purchase(self) -> None:
        """Contabiliza una compra pagada y agota el lead si toco su techo."""
        if self.purchases_count >= self.max_purchases:
            raise LeadCapReachedError()
        self.purchases_count += 1
        if self.purchases_count >= self.max_purchases:
            self.status = LeadStatus.EXHAUSTED

    def disable(self) -> None:
        self.status = LeadStatus.DISABLED

    def republish(self) -> None:
        """Vuelve a publicar un lead deshabilitado que aun tiene plazas libres."""
        if self.purchases_count >= self.max_purchases:
            raise LeadCapReachedError("El lead ya agoto sus plazas")
        self.status = LeadStatus.PUBLISHED

    # ----------------------------- Proyecciones --------------------------

    def public_view(self) -> LeadPublicView:
        """Lo que ve cualquier profesional antes de pagar: cero PII."""
        return LeadPublicView(
            id=self.id,
            category_id=self.category_id,
            title=self.title,
            description=self.description,
            city=self.location.city,
            province=self.location.province,
            postal_code_prefix=self.location.postal_code.value[:2],
            coordinates=self.location.coordinates,
            photo_keys=[p.storage_key for p in sorted(self.photos, key=lambda p: p.sort_order)],
            created_at=self.created_at,
            remaining_slots=self.remaining_slots,
            masked_phone=self.contact.phone.masked,
            masked_email=self.contact.email.masked if self.contact.email else None,
        )

    def contact_view(self, *, unlocked: bool) -> ClientContact:
        """Los datos completos del cliente. Solo tras una compra pagada."""
        if not unlocked:
            raise ContactLockedError()
        return self.contact


@dataclass(frozen=True, slots=True)
class LeadPublicView:
    """Proyeccion sin datos personales.

    Existe como tipo propio para que sea imposible devolver un `Lead` completo por
    error desde un endpoint del explorador: los serializadores publicos solo
    aceptan esta clase.
    """

    id: UUID
    category_id: UUID
    title: str
    description: str
    city: str
    province: str
    postal_code_prefix: str
    coordinates: Coordinates
    photo_keys: list[str]
    created_at: datetime
    remaining_slots: int
    masked_phone: str
    masked_email: str | None
