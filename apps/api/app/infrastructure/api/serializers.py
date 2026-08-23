"""Conversion de resultados de casos de uso a schemas de respuesta.

Vive en la capa API porque conoce URLs publicas de CDN y el idioma de la peticion,
dos cosas que no pertenecen al dominio.
"""

from __future__ import annotations

from app.application.dto import LeadDetail, LeadListItem, LeadListResult, PurchasedContact
from app.application.ports import PresignedUpload, StoragePort
from app.domain.models import (
    Category,
    ClientContact,
    Lead,
    LeadPublicView,
    Professional,
    Purchase,
    User,
)
from app.domain.value_objects import Money
from app.infrastructure.api.schemas.common import MoneyOut
from app.infrastructure.api.schemas.leads import (
    CategoryOut,
    ClientContactOut,
    CreateLeadOut,
    LeadDetailOut,
    LeadListOut,
    LeadPublicOut,
    PresignPhotoOut,
    PurchaseOut,
)
from app.infrastructure.api.schemas.professionals import ProfessionalOut
from app.infrastructure.api.schemas.purchases import PurchasedLeadOut

CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}


def money_out(money: Money) -> MoneyOut:
    symbol = CURRENCY_SYMBOLS.get(money.currency, money.currency)
    return MoneyOut(
        amount_cents=money.amount_cents,
        currency=money.currency,
        formatted=f"{money.units:.2f} {symbol}",
    )


def category_out(category: Category, locale: str) -> CategoryOut:
    return CategoryOut(
        id=category.id,
        slug=category.slug,
        name=category.name(locale),
        lead_price=money_out(category.lead_price),
    )


def lead_public_out(
    view: LeadPublicView,
    category: Category,
    price: Money,
    *,
    storage: StoragePort,
    locale: str,
    distance_km: float | None = None,
    already_purchased: bool = False,
) -> LeadPublicOut:
    return LeadPublicOut(
        id=view.id,
        title=view.title,
        description=view.description,
        city=view.city,
        province=view.province,
        postal_code_prefix=view.postal_code_prefix,
        category=category_out(category, locale),
        photo_urls=[storage.public_url(key) for key in view.photo_keys],
        created_at=view.created_at,
        remaining_slots=view.remaining_slots,
        distance_km=distance_km,
        masked_phone=view.masked_phone,
        masked_email=view.masked_email,
        already_purchased=already_purchased,
        price=money_out(price),
    )


def lead_list_item_out(item: LeadListItem, *, storage: StoragePort, locale: str) -> LeadPublicOut:
    return lead_public_out(
        item.lead,
        item.category,
        item.price,
        storage=storage,
        locale=locale,
        distance_km=item.distance_km,
        already_purchased=item.already_purchased,
    )


def lead_list_out(result: LeadListResult, *, storage: StoragePort, locale: str) -> LeadListOut:
    return LeadListOut(
        items=[lead_list_item_out(item, storage=storage, locale=locale) for item in result.items],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


def contact_out(contact: ClientContact) -> ClientContactOut:
    return ClientContactOut(
        name=contact.name,
        phone=contact.phone.value,
        email=contact.email.value if contact.email else None,
    )


def purchase_out(purchase: Purchase) -> PurchaseOut:
    return PurchaseOut(
        id=purchase.id,
        status=purchase.status.value,
        amount=money_out(purchase.price),
        created_at=purchase.created_at,
        paid_at=purchase.paid_at,
        reserved_until=purchase.reserved_until,
    )


def lead_detail_out(detail: LeadDetail, *, storage: StoragePort, locale: str) -> LeadDetailOut:
    return LeadDetailOut(
        lead=lead_public_out(
            detail.lead,
            detail.category,
            detail.price,
            storage=storage,
            locale=locale,
            distance_km=detail.distance_km,
            already_purchased=detail.is_unlocked,
        ),
        is_unlocked=detail.is_unlocked,
        contact=contact_out(detail.contact) if detail.contact else None,
        purchase=purchase_out(detail.purchase) if detail.purchase else None,
    )


def purchased_lead_out(entry: PurchasedContact, *, locale: str) -> PurchasedLeadOut:
    return PurchasedLeadOut(
        lead_id=entry.lead.id,
        title=entry.lead.title,
        city=entry.lead.location.city,
        province=entry.lead.location.province,
        category=category_out(entry.category, locale),
        purchase=purchase_out(entry.purchase),
        is_unlocked=entry.contact is not None,
        contact=contact_out(entry.contact) if entry.contact else None,
    )


def created_lead_out(lead: Lead) -> CreateLeadOut:
    return CreateLeadOut(
        id=lead.id,
        status=lead.status.value,
        city=lead.location.city,
        province=lead.location.province,
        created_at=lead.created_at,
    )


def professional_out(
    professional: Professional, categories: list[Category], locale: str
) -> ProfessionalOut:
    return ProfessionalOut(
        id=professional.id,
        business_name=professional.business_name,
        phone=professional.phone.value,
        postal_code=professional.base_postal_code.value,
        city=professional.city,
        province=professional.province,
        service_radius_km=professional.service_radius_km,
        categories=[category_out(category, locale) for category in categories],
    )


def presign_out(upload: PresignedUpload) -> PresignPhotoOut:
    return PresignPhotoOut(
        storage_key=upload.storage_key,
        upload_url=upload.upload_url,
        method=upload.method,
        headers=upload.headers,
        expires_in_seconds=upload.expires_in_seconds,
    )


def user_summary(user: User) -> dict[str, object]:
    return {
        "user_id": user.id,
        "email": user.email.value,
        "role": user.role.value,
        "display_name": user.display_name,
    }
