"""Traduccion entre filas del ORM y entidades de dominio.

Es la frontera del hexagono: a la izquierda SQLAlchemy y WKB de PostGIS, a la
derecha objetos de valor. Ningun otro modulo debe conocer ambos lados.
"""

from __future__ import annotations

from typing import Any

from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape

from app.application.ports import PostalCodeInfo
from app.domain.models import (
    Category,
    ClientContact,
    ConsentRecord,
    Lead,
    LeadLocation,
    LeadPhoto,
    Professional,
    Purchase,
    PurchaseReview,
    User,
)
from app.domain.value_objects import Coordinates, Email, Money, PhoneNumber, PostalCode
from app.infrastructure.adapters.db.models import (
    CategoryRow,
    LeadPurchaseRow,
    LeadRow,
    PostalCodeRow,
    ProfessionalRow,
    PurchaseReviewRow,
    UserRow,
)


def to_coordinates(value: Any) -> Coordinates:
    """Convierte la geometria de PostGIS (WKBElement) a un objeto de valor."""
    point = to_shape(value)
    return Coordinates(latitude=point.y, longitude=point.x)


def to_geography(coordinates: Coordinates) -> WKTElement:
    """Coordenada como elemento geografico de PostGIS (lon, lat en ese orden).

    Se devuelve un `WKTElement` y no un string: al usarlo como parametro de
    ST_DWithin o ST_Distance, un string se enviaria como VARCHAR y Postgres
    rechazaria la consulta por tipos incompatibles.

    Ojo: tras asignarlo a una columna, el atributo sigue siendo este WKTElement
    hasta que Postgres devuelve el WKB. Por eso los repositorios devuelven la
    entidad de dominio recibida en vez de re-mapear la fila recien escrita.
    """
    return WKTElement(f"POINT({coordinates.longitude} {coordinates.latitude})", srid=4326)


# ------------------------------ Category ---------------------------------


def category_to_domain(row: CategoryRow) -> Category:
    return Category(
        id=row.id,
        slug=row.slug,
        name_es=row.name_es,
        name_en=row.name_en,
        suggested_lead_price=Money(row.suggested_lead_price_cents, row.currency),
        active=row.active,
    )


def apply_category(row: CategoryRow, category: Category) -> CategoryRow:
    row.slug = category.slug
    row.name_es = category.name_es
    row.name_en = category.name_en
    row.suggested_lead_price_cents = category.suggested_lead_price.amount_cents
    row.currency = category.suggested_lead_price.currency
    row.active = category.active
    return row


# ------------------------------ User -------------------------------------


def user_to_domain(row: UserRow) -> User:
    return User(
        id=row.id,
        firebase_uid=row.firebase_uid,
        email=Email(row.email),
        role=row.role,
        created_at=row.created_at,
        display_name=row.display_name,
    )


def apply_user(row: UserRow, user: User) -> UserRow:
    row.created_at = user.created_at
    row.firebase_uid = user.firebase_uid
    row.email = user.email.value
    row.role = user.role
    row.display_name = user.display_name
    return row


# ------------------------------ Professional -----------------------------


def professional_to_domain(row: ProfessionalRow) -> Professional:
    return Professional(
        id=row.id,
        user_id=row.user_id,
        business_name=row.business_name,
        phone=PhoneNumber(row.phone),
        base_postal_code=PostalCode(row.base_postal_code),
        base_coordinates=to_coordinates(row.base_location),
        service_radius_km=row.service_radius_km,
        created_at=row.created_at,
        city=row.city,
        province=row.province,
        category_ids={category.id for category in row.categories},
    )


def apply_professional(row: ProfessionalRow, professional: Professional) -> ProfessionalRow:
    row.created_at = professional.created_at
    row.user_id = professional.user_id
    row.business_name = professional.business_name
    row.phone = professional.phone.value
    row.base_postal_code = professional.base_postal_code.value
    row.base_location = to_geography(professional.base_coordinates)
    row.service_radius_km = professional.service_radius_km
    row.city = professional.city
    row.province = professional.province
    return row


# ------------------------------ Lead -------------------------------------


def lead_to_domain(row: LeadRow) -> Lead:
    # El consentimiento es append-only: nos interesa el ultimo registrado.
    consent = None
    if row.consents:
        latest = max(row.consents, key=lambda c: c.accepted_at)
        consent = ConsentRecord(
            policy_version=latest.policy_version,
            ip_address=latest.ip_address,
            user_agent=latest.user_agent,
            accepted_at=latest.accepted_at,
            max_recipients=latest.max_recipients,
            channel=latest.external_channel,
            campaign_reference=latest.external_campaign_reference,
        )

    return Lead(
        id=row.id,
        category_id=row.category_id,
        title=row.title,
        description=row.description,
        location=LeadLocation(
            postal_code=PostalCode(row.postal_code),
            city=row.city,
            province=row.province,
            coordinates=to_coordinates(row.location),
        ),
        contact=ClientContact(
            name=row.client_name,
            phone=PhoneNumber(row.client_phone),
            email=Email(row.client_email) if row.client_email else None,
        ),
        created_at=row.created_at,
        status=row.status,
        source=row.source,
        max_purchases=row.max_purchases,
        purchases_count=row.purchases_count,
        published_at=row.published_at,
        photos=[
            LeadPhoto(storage_key=p.storage_key, sort_order=p.sort_order, id=p.id)
            for p in sorted(row.photos, key=lambda p: p.sort_order)
        ],
        consent=consent,
        price_override=(
            Money(row.price_override_cents, row.price_override_currency)
            if row.price_override_cents is not None and row.price_override_currency is not None
            else None
        ),
    )


def apply_lead(row: LeadRow, lead: Lead) -> LeadRow:
    row.created_at = lead.created_at
    row.category_id = lead.category_id
    row.title = lead.title
    row.description = lead.description
    row.postal_code = lead.location.postal_code.value
    row.city = lead.location.city
    row.province = lead.location.province
    row.location = to_geography(lead.location.coordinates)
    row.client_name = lead.contact.name
    row.client_phone = lead.contact.phone.value
    row.client_email = lead.contact.email.value if lead.contact.email else None
    row.status = lead.status
    row.source = lead.source
    row.max_purchases = lead.max_purchases
    row.purchases_count = lead.purchases_count
    row.published_at = lead.published_at
    row.price_override_cents = lead.price_override.amount_cents if lead.price_override else None
    row.price_override_currency = lead.price_override.currency if lead.price_override else None
    return row


# ------------------------------ Purchase ---------------------------------


def purchase_to_domain(row: LeadPurchaseRow) -> Purchase:
    return Purchase(
        id=row.id,
        lead_id=row.lead_id,
        professional_id=row.professional_id,
        price=Money(row.amount_cents, row.currency),
        status=row.status,
        created_at=row.created_at,
        reserved_until=row.reserved_until,
        stripe_checkout_session_id=row.stripe_checkout_session_id,
        stripe_payment_intent_id=row.stripe_payment_intent_id,
        paid_at=row.paid_at,
    )


def apply_purchase(row: LeadPurchaseRow, purchase: Purchase) -> LeadPurchaseRow:
    row.created_at = purchase.created_at
    row.lead_id = purchase.lead_id
    row.professional_id = purchase.professional_id
    row.amount_cents = purchase.price.amount_cents
    row.currency = purchase.price.currency
    row.status = purchase.status
    row.reserved_until = purchase.reserved_until
    row.stripe_checkout_session_id = purchase.stripe_checkout_session_id
    row.stripe_payment_intent_id = purchase.stripe_payment_intent_id
    row.paid_at = purchase.paid_at
    return row


def purchase_review_to_domain(row: PurchaseReviewRow) -> PurchaseReview:
    return PurchaseReview(
        id=row.id,
        purchase_id=row.purchase_id,
        reviewed_by_user_id=row.reviewed_by_user_id,
        note=row.note,
        created_at=row.created_at,
    )


def apply_purchase_review(row: PurchaseReviewRow, review: PurchaseReview) -> PurchaseReviewRow:
    row.purchase_id = review.purchase_id
    row.reviewed_by_user_id = review.reviewed_by_user_id
    row.note = review.note
    row.created_at = review.created_at
    return row


# ------------------------------ Postal code ------------------------------


def postal_code_to_domain(row: PostalCodeRow) -> PostalCodeInfo:
    return PostalCodeInfo(
        code=PostalCode(row.code),
        city=row.city,
        province=row.province,
        coordinates=to_coordinates(row.location),
    )
