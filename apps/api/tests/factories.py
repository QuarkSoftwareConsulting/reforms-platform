"""Constructores de entidades de dominio para los tests.

Centralizarlos evita repetir 15 lineas de setup en cada test y hace que anadir un
campo obligatorio al dominio rompa en un solo sitio.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.models import (
    Category,
    ClientContact,
    ConsentRecord,
    Lead,
    LeadLocation,
    LeadPhoto,
    LeadSource,
    LeadStatus,
    Professional,
    Purchase,
    PurchaseStatus,
    User,
    UserRole,
)
from app.domain.value_objects import Coordinates, Email, Money, PhoneNumber, PostalCode

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
MADRID = Coordinates(40.4168, -3.7038)
BARCELONA = Coordinates(41.3874, 2.1686)
ALCALA = Coordinates(40.4818, -3.3644)  # ~30 km de Madrid


def make_consent(**kwargs: object) -> ConsentRecord:
    defaults: dict[str, object] = {
        "policy_version": "2026-01-v1",
        "ip_address": "83.45.12.9",
        "user_agent": "Mozilla/5.0",
        "accepted_at": NOW,
        "max_recipients": 3,
    }
    defaults.update(kwargs)
    return ConsentRecord(**defaults)  # type: ignore[arg-type]


def make_contact(**kwargs: object) -> ClientContact:
    defaults: dict[str, object] = {
        "name": "Ana Lopez",
        "phone": PhoneNumber("+34611223344"),
        "email": Email("ana.lopez@example.com"),
    }
    defaults.update(kwargs)
    return ClientContact(**defaults)  # type: ignore[arg-type]


def make_lead_location(**kwargs: object) -> LeadLocation:
    defaults: dict[str, object] = {
        "postal_code": PostalCode("28001"),
        "city": "Madrid",
        "province": "Madrid",
        "coordinates": MADRID,
    }
    defaults.update(kwargs)
    return LeadLocation(**defaults)  # type: ignore[arg-type]


def make_lead(**kwargs: object) -> Lead:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "category_id": uuid4(),
        "title": "Reparar armario de cocina",
        "description": "Se ha descolgado la puerta del armario alto de la cocina y "
        "necesito que la vuelvan a montar y ajusten las bisagras.",
        "location": make_lead_location(),
        "contact": make_contact(),
        "created_at": NOW,
        "status": LeadStatus.PUBLISHED,
        "source": LeadSource.ORGANIC,
        "max_purchases": 3,
        "purchases_count": 0,
        "published_at": NOW,
        "photos": [LeadPhoto(storage_key="leads/x/1.jpg", sort_order=0)],
        "consent": make_consent(),
        "price_override": None,
    }
    defaults.update(kwargs)
    return Lead(**defaults)  # type: ignore[arg-type]


def make_category(**kwargs: object) -> Category:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "slug": "carpinteria",
        "name_es": "Carpinteria",
        "name_en": "Carpentry",
        "suggested_lead_price": Money(500, "EUR"),
        "active": True,
    }
    defaults.update(kwargs)
    return Category(**defaults)  # type: ignore[arg-type]


def make_user(**kwargs: object) -> User:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "firebase_uid": "firebase-uid-123",
        "email": Email("pro@example.com"),
        "role": UserRole.PROFESSIONAL,
        "created_at": NOW,
        "display_name": "Carpinteria Lopez",
    }
    defaults.update(kwargs)
    return User(**defaults)  # type: ignore[arg-type]


def make_professional(*, category_ids: set[UUID] | None = None, **kwargs: object) -> Professional:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "business_name": "Carpinteria Lopez",
        "phone": PhoneNumber("+34600111222"),
        "base_postal_code": PostalCode("28001"),
        "base_coordinates": MADRID,
        "service_radius_km": 25,
        "created_at": NOW,
        "city": "Madrid",
        "province": "Madrid",
        "category_ids": category_ids if category_ids is not None else {uuid4()},
    }
    defaults.update(kwargs)
    return Professional(**defaults)  # type: ignore[arg-type]


def make_purchase(**kwargs: object) -> Purchase:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "lead_id": uuid4(),
        "professional_id": uuid4(),
        "price": Money(500, "EUR"),
        "status": PurchaseStatus.RESERVED,
        "created_at": NOW,
        "reserved_until": None,
        "stripe_checkout_session_id": None,
        "stripe_payment_intent_id": None,
        "paid_at": None,
    }
    defaults.update(kwargs)
    return Purchase(**defaults)  # type: ignore[arg-type]
