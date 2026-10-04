"""Tablas de la base de datos."""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.models import (
    CreditEntryKind,
    DocumentKind,
    LeadSource,
    LeadStatus,
    ProfessionalType,
    ProjectSchedule,
    PropertyType,
    PurchaseStatus,
    SubscriptionStatus,
    UserRole,
    VerificationStatus,
)
from app.infrastructure.adapters.db.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)

# Los enums se materializan en Postgres para que la BD rechace valores invalidos.
user_role_enum = Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e])
lead_status_enum = Enum(
    LeadStatus, name="lead_status", values_callable=lambda e: [m.value for m in e]
)
lead_source_enum = Enum(
    LeadSource, name="lead_source", values_callable=lambda e: [m.value for m in e]
)
purchase_status_enum = Enum(
    PurchaseStatus, name="purchase_status", values_callable=lambda e: [m.value for m in e]
)
subscription_status_enum = Enum(
    SubscriptionStatus,
    name="subscription_status",
    values_callable=lambda e: [m.value for m in e],
)
credit_entry_kind_enum = Enum(
    CreditEntryKind, name="credit_entry_kind", values_callable=lambda e: [m.value for m in e]
)
property_type_enum = Enum(
    PropertyType, name="property_type", values_callable=lambda e: [m.value for m in e]
)
project_schedule_enum = Enum(
    ProjectSchedule, name="project_schedule", values_callable=lambda e: [m.value for m in e]
)
professional_type_enum = Enum(
    ProfessionalType, name="professional_type", values_callable=lambda e: [m.value for m in e]
)
verification_status_enum = Enum(
    VerificationStatus,
    name="verification_status",
    values_callable=lambda e: [m.value for m in e],
)
document_kind_enum = Enum(
    DocumentKind, name="document_kind", values_callable=lambda e: [m.value for m in e]
)

Point = Geography(geometry_type="POINT", srid=4326, spatial_index=False)


class UserRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    firebase_uid: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[UserRole] = mapped_column(
        user_role_enum, nullable=False, default=UserRole.PROFESSIONAL
    )
    display_name: Mapped[str | None] = mapped_column(String(200))

    professional: Mapped[ProfessionalRow | None] = relationship(
        back_populates="user", uselist=False
    )


class UserRoleEventRow(Base, UUIDPrimaryKeyMixin):
    """Auditoria de los cambios de rol. Append-only: nunca se actualiza ni se borra."""

    __tablename__ = "user_role_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    from_role: Mapped[UserRole] = mapped_column(user_role_enum, nullable=False)
    to_role: Mapped[UserRole] = mapped_column(user_role_enum, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_user_role_events_user_id", "user_id"),)


class CategoryRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name_es: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    suggested_lead_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    # Se cargan todos, tambien los retirados: un lead antiguo sigue nombrando el suyo.
    services: Mapped[list[ServiceRow]] = relationship(
        back_populates="category",
        lazy="selectin",
        order_by="ServiceRow.sort_order",
    )

    __table_args__ = (
        CheckConstraint("suggested_lead_price_cents > 0", name="suggested_lead_price_positive"),
    )


class ServiceRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Servicio dentro de una categoria (segundo nivel del catalogo)."""

    __tablename__ = "services"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name_es: Mapped[str] = mapped_column(String(160), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    category: Mapped[CategoryRow] = relationship(back_populates="services")

    __table_args__ = (
        # El mismo servicio puede existir en dos categorias (Domotica esta en Seguridad
        # Electronica y en Instaladores), pero no dos veces en la misma.
        UniqueConstraint("category_id", "slug", name="uq_services_category_slug"),
    )


class LeadServiceRow(Base):
    """Tabla puente: que servicios de su categoria eligio el cliente."""

    __tablename__ = "lead_services"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), primary_key=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    lead: Mapped[LeadRow] = relationship(back_populates="services")


class ProfessionalCategoryRow(Base):
    """Tabla puente: que oficios ofrece cada profesional."""

    __tablename__ = "professional_categories"

    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )


class ProfessionalRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "professionals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    base_postal_code: Mapped[str] = mapped_column(String(12), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120))
    province: Mapped[str | None] = mapped_column(String(120))
    base_location: Mapped[object] = mapped_column(Point, nullable=False)
    service_radius_km: Mapped[int] = mapped_column(Integer, nullable=False, default=25)

    # --- Alta (F02) ---
    professional_type: Mapped[ProfessionalType | None] = mapped_column(professional_type_enum)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    tax_id: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(String(300))
    profile_photo_key: Mapped[str | None] = mapped_column(String(500))
    logo_key: Mapped[str | None] = mapped_column(String(500))

    # --- Validacion ---
    # Los perfiles anteriores a la Etapa 1 quedan "incompletos": tienen que aportar
    # sus datos y documentos, como cualquier alta nueva, antes de poder comprar.
    verification_status: Mapped[VerificationStatus] = mapped_column(
        verification_status_enum,
        nullable=False,
        default=VerificationStatus.INCOMPLETE,
        server_default=text("'incomplete'"),
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    user: Mapped[UserRow] = relationship(back_populates="professional")
    categories: Mapped[list[CategoryRow]] = relationship(
        secondary="professional_categories", lazy="selectin"
    )
    services: Mapped[list[ProfessionalServiceRow]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )
    work_photos: Mapped[list[ProfessionalWorkPhotoRow]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProfessionalWorkPhotoRow.sort_order",
    )
    documents: Mapped[list[ProfessionalDocumentRow]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProfessionalDocumentRow.uploaded_at",
    )

    __table_args__ = (
        CheckConstraint("service_radius_km BETWEEN 1 AND 300", name="service_radius_in_range"),
        Index("ix_professionals_base_location", "base_location", postgresql_using="gist"),
        Index("ix_professionals_verification_status", "verification_status"),
    )


class ProfessionalServiceRow(Base):
    """Tabla puente: que servicios concretos ofrece el profesional."""

    __tablename__ = "professional_services"

    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), primary_key=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), primary_key=True
    )


class ProfessionalWorkPhotoRow(Base, UUIDPrimaryKeyMixin):
    """Fotos de trabajos realizados (bucket publico: se ensenaran a los clientes)."""

    __tablename__ = "professional_work_photos"

    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (Index("ix_professional_work_photos_professional_id", "professional_id"),)


class ProfessionalDocumentRow(Base, UUIDPrimaryKeyMixin):
    """Documento de alta. La clave apunta al bucket PRIVADO: nunca a una URL publica."""

    __tablename__ = "professional_documents"

    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[DocumentKind] = mapped_column(document_kind_enum, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_professional_documents_professional_id", "professional_id"),)


class ProfessionalVerificationEventRow(Base, UUIDPrimaryKeyMixin):
    """Auditoria de la validacion. Append-only: nunca se actualiza ni se borra."""

    __tablename__ = "professional_verification_events"

    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[VerificationStatus] = mapped_column(
        verification_status_enum, nullable=False
    )
    to_status: Mapped[VerificationStatus] = mapped_column(verification_status_enum, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_professional_verification_events_professional_id", "professional_id"),
    )


class LeadRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "leads"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    postal_code: Mapped[str] = mapped_column(String(12), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    province: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[object] = mapped_column(Point, nullable=False)

    # --- Datos personales del cliente: es la mercancia de la plataforma ---
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    client_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    client_email: Mapped[str | None] = mapped_column(String(320))

    status: Mapped[LeadStatus] = mapped_column(
        lead_status_enum, nullable=False, default=LeadStatus.PUBLISHED
    )
    source: Mapped[LeadSource] = mapped_column(
        lead_source_enum, nullable=False, default=LeadSource.ORGANIC
    )
    max_purchases: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    purchases_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Precio que el admin fijo para este contacto. NULL = se cobra el sugerido de
    # la categoria. La divisa se guarda al lado del importe para que el mapeo de la
    # fila no dependa de cargar tambien el oficio.
    price_override_cents: Mapped[int | None] = mapped_column(Integer)
    price_override_currency: Mapped[str | None] = mapped_column(String(3))

    # NULL en los leads anteriores al formulario de la Etapa 1.
    property_type: Mapped[PropertyType | None] = mapped_column(property_type_enum)
    schedule: Mapped[ProjectSchedule | None] = mapped_column(project_schedule_enum)

    photos: Mapped[list[LeadPhotoRow]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )
    consents: Mapped[list[LeadConsentRow]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )
    services: Mapped[list[LeadServiceRow]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LeadServiceRow.sort_order",
    )

    __table_args__ = (
        CheckConstraint("max_purchases >= 1", name="max_purchases_positive"),
        CheckConstraint(
            "price_override_cents IS NULL OR price_override_cents > 0",
            name="price_override_positive",
        ),
        CheckConstraint(
            "(price_override_cents IS NULL) = (price_override_currency IS NULL)",
            name="price_override_complete",
        ),
        CheckConstraint(
            "purchases_count >= 0 AND purchases_count <= max_purchases",
            name="purchases_count_within_cap",
        ),
        Index("ix_leads_location", "location", postgresql_using="gist"),
        Index("ix_leads_browse", "status", "category_id", text("created_at DESC")),
    )


class LeadPhotoRow(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "lead_photos"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    lead: Mapped[LeadRow] = relationship(back_populates="photos")

    __table_args__ = (Index("ix_lead_photos_lead_id", "lead_id"),)


class LeadConsentRow(Base, UUIDPrimaryKeyMixin):
    """Registro auditable del consentimiento RGPD.

    Es append-only: nunca se actualiza ni se borra mientras el lead exista, porque
    es la prueba de que el cliente autorizo la cesion de sus datos.
    """

    __tablename__ = "lead_consents"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    max_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_channel: Mapped[str | None] = mapped_column(String(120))
    external_campaign_reference: Mapped[str | None] = mapped_column(String(200))
    # Los consentimientos anteriores a la politica 2026-09-v2 no cubren mostrar el
    # nombre de pila y el CP antes de la compra: por eso el valor por defecto es false.
    allows_public_preview: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    lead: Mapped[LeadRow] = relationship(back_populates="consents")

    __table_args__ = (Index("ix_lead_consents_lead_id", "lead_id"),)


class LeadPurchaseRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_purchases"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    status: Mapped[PurchaseStatus] = mapped_column(purchase_status_enum, nullable=False)
    reserved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Parte del importe cubierta con saldo de la recarga; el resto se cobro en Stripe.
    credit_applied_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    __table_args__ = (
        # Un profesional no puede tener dos compras vivas del mismo lead. El indice
        # unico parcial deja fuera las caducadas/fallidas para que pueda reintentar.
        Index(
            "uq_lead_purchases_active",
            "lead_id",
            "professional_id",
            unique=True,
            postgresql_where=text("status IN ('reserved', 'paid', 'refunded')"),
        ),
        Index("ix_lead_purchases_professional", "professional_id", text("created_at DESC")),
        Index(
            "ix_lead_purchases_open_reservations",
            "reserved_until",
            postgresql_where=text("status = 'reserved'"),
        ),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint(
            "credit_applied_cents >= 0 AND credit_applied_cents <= amount_cents",
            name="credit_applied_in_range",
        ),
    )


class PurchaseReviewRow(Base, UUIDPrimaryKeyMixin):
    """Marca inmutable para investigar una compra sin alterar su estado de pago."""

    __tablename__ = "purchase_reviews"

    purchase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_purchases.id", ondelete="CASCADE"), nullable=False
    )
    reviewed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    note: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_purchase_reviews_purchase", "purchase_id", "created_at"),)


class PostalCodeRow(Base):
    """Catalogo de codigos postales con su centroide."""

    __tablename__ = "postal_codes"

    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="ES")
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    province: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[object] = mapped_column(Point, nullable=False)

    __table_args__ = (
        Index("ix_postal_codes_location", "location", postgresql_using="gist"),
        Index("ix_postal_codes_city", "city"),
    )


class ProcessedPaymentEventRow(Base):
    """Eventos de la pasarela ya procesados: cerrojo de idempotencia del webhook."""

    __tablename__ = "processed_payment_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ProfessionalAccountRow(Base, TimestampMixin):
    """Recarga mensual y saldo de un profesional.

    El saldo se guarda cacheado aqui para poder bloquearlo con la fila (FOR UPDATE)
    al comprar; `credit_entries` es el libro que lo justifica movimiento a
    movimiento.
    """

    __tablename__ = "professional_accounts"

    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        subscription_status_enum, nullable=False, default=SubscriptionStatus.NONE
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    balance_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    __table_args__ = (
        # Ultima barrera contra gastar saldo que no existe, aunque el dominio falle.
        CheckConstraint("balance_cents >= 0", name="balance_non_negative"),
    )


class CreditEntryRow(Base, UUIDPrimaryKeyMixin):
    """Movimiento append-only del saldo. Nunca se actualiza ni se borra."""

    __tablename__ = "credit_entries"

    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professional_accounts.professional_id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[CreditEntryKind] = mapped_column(credit_entry_kind_enum, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # Cerrojo de idempotencia del libro: la misma factura no se abona dos veces
        # y la misma compra no gasta (ni devuelve) saldo dos veces.
        UniqueConstraint("kind", "source_ref", name="uq_credit_entries_kind_source_ref"),
        Index("ix_credit_entries_professional", "professional_id", text("created_at DESC")),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
    )


class SubscriptionPriceRow(Base, UUIDPrimaryKeyMixin):
    """Historial append-only de la mensualidad; la vigente es la mas reciente."""

    __tablename__ = "subscription_prices"

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    stripe_price_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_subscription_prices_created_at", text("created_at DESC")),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
    )


__all__ = [
    "Base",
    "CategoryRow",
    "CreditEntryRow",
    "LeadConsentRow",
    "LeadPhotoRow",
    "LeadPurchaseRow",
    "LeadRow",
    "PostalCodeRow",
    "ProcessedPaymentEventRow",
    "ProfessionalAccountRow",
    "ProfessionalCategoryRow",
    "ProfessionalRow",
    "PurchaseReviewRow",
    "SubscriptionPriceRow",
    "UserRow",
]
