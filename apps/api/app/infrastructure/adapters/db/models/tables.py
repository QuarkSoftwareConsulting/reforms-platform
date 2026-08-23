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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.models import LeadSource, LeadStatus, PurchaseStatus, UserRole
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


class CategoryRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name_es: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    lead_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (CheckConstraint("lead_price_cents > 0", name="lead_price_positive"),)


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

    user: Mapped[UserRow] = relationship(back_populates="professional")
    categories: Mapped[list[CategoryRow]] = relationship(
        secondary="professional_categories", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("service_radius_km BETWEEN 1 AND 300", name="service_radius_in_range"),
        Index("ix_professionals_base_location", "base_location", postgresql_using="gist"),
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
    max_purchases: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    purchases_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    photos: Mapped[list[LeadPhotoRow]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )
    consents: Mapped[list[LeadConsentRow]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("max_purchases >= 1", name="max_purchases_positive"),
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
    max_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

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
    )


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


__all__ = [
    "Base",
    "CategoryRow",
    "LeadConsentRow",
    "LeadPhotoRow",
    "LeadPurchaseRow",
    "LeadRow",
    "PostalCodeRow",
    "ProcessedPaymentEventRow",
    "ProfessionalCategoryRow",
    "ProfessionalRow",
    "UserRow",
]
