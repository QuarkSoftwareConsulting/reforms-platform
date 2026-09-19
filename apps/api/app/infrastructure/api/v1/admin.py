"""Endpoints de administracion de precios.

Todos exigen rol de admin (`AdminDep`). Son la unica via para cambiar lo que
cuesta un contacto: ni el cliente ni el profesional pueden tocar un precio.
"""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.application.dto import ConsentInput, CreateLeadInput
from app.application.ports import AdminLeadFilters
from app.domain.models import LeadSource, LeadStatus
from app.domain.value_objects import Money
from app.infrastructure.api import serializers
from app.infrastructure.api.dependencies import AdminDep, ContainerDep, LocaleDep
from app.infrastructure.api.schemas.admin import (
    AdminCreateLeadIn,
    AdminLeadListOut,
    AdminLeadStatusOut,
    AdminMetricsOut,
    AdminProfessionalListOut,
    AdminPurchaseOut,
    LeadPricingOut,
    PurchaseReviewIn,
    PurchaseReviewOut,
    SetCategoryPriceIn,
    SetLeadPriceIn,
)
from app.infrastructure.api.schemas.leads import CategoryOut, CreateLeadOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics", response_model=AdminMetricsOut, summary="Metricas acumuladas")
async def get_metrics(container: ContainerDep, _: AdminDep) -> AdminMetricsOut:
    return serializers.admin_metrics_out(await container.admin_metrics.execute())


@router.get("/leads", response_model=AdminLeadListOut, summary="Inventario de solicitudes")
async def list_admin_leads(
    container: ContainerDep,
    locale: LocaleDep,
    _: AdminDep,
    category_id: UUID | None = None,
    lead_status: Annotated[LeadStatus | None, Query(alias="status")] = None,
    source: LeadSource | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminLeadListOut:
    result = await container.admin_leads.execute(
        AdminLeadFilters(
            category_id=category_id,
            status=lead_status,
            source=source,
            limit=limit,
            offset=offset,
        )
    )
    return await asyncio.to_thread(
        serializers.admin_lead_list_out, result, storage=container.infra.storage, locale=locale
    )


@router.post(
    "/leads",
    response_model=CreateLeadOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ingresar una solicitud captada externamente",
)
async def create_admin_lead(
    payload: AdminCreateLeadIn, container: ContainerDep, _: AdminDep
) -> CreateLeadOut:
    lead = await container.create_lead.execute(
        CreateLeadInput(
            category_id=payload.category_id,
            title=payload.title,
            description=payload.description,
            postal_code=payload.postal_code,
            client_name=payload.client_name,
            client_phone=payload.client_phone,
            client_email=payload.client_email,
            photo_keys=payload.photo_keys,
            consent=ConsentInput(
                accepted=True,
                policy_version=payload.consent.policy_version,
                channel=payload.consent.channel,
                campaign_reference=payload.consent.campaign_reference,
                accepted_at=payload.consent.accepted_at,
            ),
        ),
        source=LeadSource.ADMIN,
    )
    return serializers.created_lead_out(lead)


@router.post(
    "/leads/{lead_id}/disable",
    response_model=AdminLeadStatusOut,
    summary="Retirar una solicitud",
)
async def disable_lead(lead_id: UUID, container: ContainerDep, _: AdminDep) -> AdminLeadStatusOut:
    lead = await container.change_lead_availability.execute(lead_id=lead_id, publish=False)
    return AdminLeadStatusOut(id=lead.id, status=lead.status.value)


@router.post(
    "/leads/{lead_id}/republish",
    response_model=AdminLeadStatusOut,
    summary="Republicar una solicitud",
)
async def republish_lead(lead_id: UUID, container: ContainerDep, _: AdminDep) -> AdminLeadStatusOut:
    lead = await container.change_lead_availability.execute(lead_id=lead_id, publish=True)
    return AdminLeadStatusOut(id=lead.id, status=lead.status.value)


@router.get(
    "/leads/{lead_id}/purchases",
    response_model=list[AdminPurchaseOut],
    summary="Compras de una solicitud",
)
async def list_lead_purchases(
    lead_id: UUID,
    container: ContainerDep,
    locale: LocaleDep,
    _: AdminDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AdminPurchaseOut]:
    entries = await container.lead_purchases_for_admin.execute(
        lead_id=lead_id, limit=limit, offset=offset
    )
    return [serializers.admin_purchase_out(entry, locale) for entry in entries]


@router.get(
    "/professionals",
    response_model=AdminProfessionalListOut,
    summary="Directorio de profesionales",
)
async def list_admin_professionals(
    container: ContainerDep,
    locale: LocaleDep,
    _: AdminDep,
    query: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminProfessionalListOut:
    result = await container.admin_professionals.execute(query=query, limit=limit, offset=offset)
    return serializers.admin_professional_list_out(result, locale)


@router.post(
    "/purchases/{purchase_id}/reviews",
    response_model=PurchaseReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Marcar una compra para revision",
)
async def mark_purchase_for_review(
    purchase_id: UUID,
    payload: PurchaseReviewIn,
    container: ContainerDep,
    admin: AdminDep,
) -> PurchaseReviewOut:
    review = await container.mark_purchase_for_review.execute(
        purchase_id=purchase_id, admin_user_id=admin.id, note=payload.note
    )
    return serializers.purchase_review_out(review)


@router.get(
    "/leads/{lead_id}/price",
    response_model=LeadPricingOut,
    summary="Precio de venta de un contacto y sugerido de su oficio",
)
async def get_lead_price(
    lead_id: UUID, container: ContainerDep, locale: LocaleDep, _: AdminDep
) -> LeadPricingOut:
    pricing = await container.lead_pricing.execute(lead_id=lead_id)
    return serializers.lead_pricing_out(pricing, locale)


@router.put(
    "/leads/{lead_id}/price",
    response_model=LeadPricingOut,
    summary="Fijar el precio de venta de un contacto",
)
async def set_lead_price(
    lead_id: UUID,
    payload: SetLeadPriceIn,
    container: ContainerDep,
    locale: LocaleDep,
    _: AdminDep,
) -> LeadPricingOut:
    """Sustituye el precio sugerido del oficio para este contacto en concreto.

    Con `amount_cents: null` se borra el precio propio y el lead vuelve a cobrarse
    al sugerido de su categoria. El cambio solo afecta a compras futuras: las ya
    creadas conservan el importe con el que se emitio su checkout.
    """
    price = (
        Money(payload.amount_cents, payload.currency or container.infra.settings.default_currency)
        if payload.amount_cents is not None
        else None
    )
    pricing = await container.set_lead_price.execute(lead_id=lead_id, price=price)
    return serializers.lead_pricing_out(pricing, locale)


@router.put(
    "/categories/{category_id}/suggested-price",
    response_model=CategoryOut,
    summary="Fijar el precio sugerido de un oficio",
)
async def set_category_suggested_price(
    category_id: UUID,
    payload: SetCategoryPriceIn,
    container: ContainerDep,
    locale: LocaleDep,
    _: AdminDep,
) -> CategoryOut:
    """Cambia la referencia del oficio.

    Los leads con precio propio no se ven afectados: el admin ya decidio sobre
    ellos y una edicion del catalogo no debe deshacer esa decision.
    """
    category = await container.set_category_price.execute(
        category_id=category_id,
        price=Money(
            payload.amount_cents, payload.currency or container.infra.settings.default_currency
        ),
    )
    return serializers.category_out(category, locale)
