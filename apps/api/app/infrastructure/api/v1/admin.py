"""Endpoints de administracion: precios, inventario, altas, compras y roles.

Todos exigen rol de admin (`AdminDep`). Son la unica via para cambiar lo que
cuesta un contacto: ni el cliente ni el profesional pueden tocar un precio. Y la
unica via, junto a la CLI de bootstrap, para dar o quitar el rol de admin.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.application.dto import AdminPurchaseQuery, ConsentInput, CreateLeadInput
from app.application.ports import AdminLeadFilters, AdminUserFilters
from app.domain.models import (
    LeadSource,
    LeadStatus,
    PurchaseStatus,
    UserRole,
    VerificationStatus,
)
from app.domain.value_objects import Money
from app.infrastructure.api import serializers
from app.infrastructure.api.dependencies import AdminDep, ContainerDep, LocaleDep
from app.infrastructure.api.schemas.admin import (
    AdminCreateLeadIn,
    AdminLeadListOut,
    AdminLeadStatusOut,
    AdminMetricsOut,
    AdminProfessionalListOut,
    AdminPurchaseListOut,
    AdminPurchaseOut,
    AdminUserListOut,
    AdminUserOut,
    LeadPricingOut,
    MetricsTimeseriesOut,
    PurchaseReviewIn,
    PurchaseReviewOut,
    RejectionOut,
    RejectProfessionalIn,
    SetCategoryPriceIn,
    SetLeadPriceIn,
    SetUserRoleIn,
    UserRoleEventOut,
    VerificationDossierOut,
)
from app.infrastructure.api.schemas.billing import (
    AdminAccountOut,
    CreditAdjustmentIn,
    SetSubscriptionPriceIn,
    SubscriptionPriceOut,
)
from app.infrastructure.api.schemas.leads import CategoryOut, CreateLeadOut
from app.infrastructure.api.schemas.professionals import ProfessionalOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics", response_model=AdminMetricsOut, summary="Metricas acumuladas")
async def get_metrics(container: ContainerDep, _: AdminDep) -> AdminMetricsOut:
    return serializers.admin_metrics_out(await container.admin_metrics.execute())


@router.get(
    "/metrics/timeseries",
    response_model=MetricsTimeseriesOut,
    summary="Actividad diaria para las graficas",
)
async def get_metrics_timeseries(
    container: ContainerDep,
    _: AdminDep,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
) -> MetricsTimeseriesOut:
    """Un punto por dia (hora de Madrid), ambos extremos incluidos. Por defecto, 30 dias."""
    series = await container.metrics_timeseries.execute(start=start, end=end)
    return serializers.metrics_timeseries_out(series)


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
            service_ids=payload.service_ids,
            property_type=payload.property_type,
            schedule=payload.schedule,
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
    verification_status: VerificationStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminProfessionalListOut:
    """Con `verification_status=pending` es la cola de validacion (lo mas antiguo primero)."""
    result = await container.admin_professionals.execute(
        query=query, limit=limit, offset=offset, verification_status=verification_status
    )
    return serializers.admin_professional_list_out(result, locale)


@router.get(
    "/professionals/{professional_id}/verification",
    response_model=VerificationDossierOut,
    summary="Expediente de validacion: datos, documentos y auditoria",
)
async def get_verification_dossier(
    professional_id: UUID, container: ContainerDep, locale: LocaleDep, _: AdminDep
) -> VerificationDossierOut:
    """Las URLs de los documentos son firmadas y caducan en minutos: no se guardan."""
    dossier = await container.verification_dossier.execute(professional_id=professional_id)
    return serializers.verification_dossier_out(
        dossier, storage=container.infra.storage, locale=locale
    )


@router.post(
    "/professionals/{professional_id}/approve",
    response_model=ProfessionalOut,
    summary="Aprobar el alta de un profesional",
)
async def approve_professional(
    professional_id: UUID, container: ContainerDep, locale: LocaleDep, admin: AdminDep
) -> ProfessionalOut:
    professional = await container.approve_professional.execute(
        professional_id=professional_id, admin_user_id=admin.id
    )
    categories = await container.categories.get_many(professional.category_ids)
    return serializers.professional_out(
        professional, categories, locale, storage=container.infra.storage
    )


@router.post(
    "/professionals/{professional_id}/reject",
    response_model=RejectionOut,
    summary="Rechazar el alta: reembolsa el primer cobro y cancela la recarga",
)
async def reject_professional(
    professional_id: UUID,
    payload: RejectProfessionalIn,
    container: ContainerDep,
    locale: LocaleDep,
    admin: AdminDep,
) -> RejectionOut:
    """503 PAYMENT_GATEWAY_ERROR si la pasarela falla: no se guarda nada y se puede reintentar."""
    result = await container.reject_professional.execute(
        professional_id=professional_id, admin_user_id=admin.id, reason=payload.reason
    )
    categories = await container.categories.get_many(result.professional.category_ids)
    return RejectionOut(
        professional=serializers.professional_out(
            result.professional, categories, locale, storage=container.infra.storage
        ),
        refunded=serializers.money_out(result.refunded) if result.refunded else None,
        subscription_canceled=result.subscription_canceled,
    )


@router.get(
    "/subscription-price",
    response_model=SubscriptionPriceOut,
    summary="Mensualidad vigente para suscripciones nuevas",
)
async def get_subscription_price(container: ContainerDep, _: AdminDep) -> SubscriptionPriceOut:
    return serializers.subscription_price_out(await container.pricing.current())


@router.put(
    "/subscription-price",
    response_model=SubscriptionPriceOut,
    summary="Cambiar la mensualidad",
)
async def set_subscription_price(
    payload: SetSubscriptionPriceIn, container: ContainerDep, admin: AdminDep
) -> SubscriptionPriceOut:
    """Crea un precio nuevo en la pasarela. Los ya suscritos conservan el suyo."""
    info = await container.set_subscription_price.execute(
        amount_cents=payload.amount_cents, admin_user_id=admin.id
    )
    return serializers.subscription_price_out(info)


@router.post(
    "/professionals/{professional_id}/credit-adjustments",
    response_model=AdminAccountOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ajustar a mano el saldo de un profesional",
)
async def adjust_professional_credit(
    professional_id: UUID,
    payload: CreditAdjustmentIn,
    container: ContainerDep,
    admin: AdminDep,
) -> AdminAccountOut:
    """Abona (importe positivo) o carga (negativo) saldo, con nota obligatoria.

    Es la via para compensar una compra reembolsada: la plaza no se libera, pero
    el profesional recupera el importe como saldo.
    """
    account = await container.adjust_credit.execute(
        professional_id=professional_id,
        amount_cents=payload.amount_cents,
        note=payload.note,
        admin_user_id=admin.id,
    )
    return AdminAccountOut(
        status=account.subscription_status.value,
        is_active=account.is_active(container.infra.clock.now()),
        balance=serializers.money_out(account.balance),
        current_period_end=account.current_period_end,
    )


@router.get("/purchases", response_model=AdminPurchaseListOut, summary="Todas las compras")
async def list_admin_purchases(
    container: ContainerDep,
    locale: LocaleDep,
    _: AdminDep,
    purchase_status: Annotated[PurchaseStatus | None, Query(alias="status")] = None,
    professional_id: UUID | None = None,
    from_day: Annotated[date | None, Query(alias="from")] = None,
    to_day: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminPurchaseListOut:
    """Quien compro que y cuando, lo mas reciente primero.

    `from` y `to` son dias (hora de Madrid), ambos incluidos, como en el dashboard.
    """
    result = await container.admin_purchases.execute(
        AdminPurchaseQuery(
            status=purchase_status,
            professional_id=professional_id,
            from_day=from_day,
            to_day=to_day,
            limit=limit,
            offset=offset,
        )
    )
    return serializers.admin_purchase_list_out(result, locale)


@router.get("/users", response_model=AdminUserListOut, summary="Directorio de usuarios")
async def list_admin_users(
    container: ContainerDep,
    locale: LocaleDep,
    _: AdminDep,
    query: str | None = None,
    role: UserRole | None = None,
    verification_status: VerificationStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminUserListOut:
    result = await container.admin_users.execute(
        AdminUserFilters(
            query=query,
            role=role,
            verification_status=verification_status,
            limit=limit,
            offset=offset,
        )
    )
    return serializers.admin_user_list_out(result, locale)


@router.put("/users/{user_id}/role", response_model=AdminUserOut, summary="Cambiar el rol")
async def set_user_role(
    user_id: UUID,
    payload: SetUserRoleIn,
    container: ContainerDep,
    locale: LocaleDep,
    admin: AdminDep,
) -> AdminUserOut:
    """Surte efecto en la siguiente peticion del usuario: el rol se lee de la BD."""
    result = await container.change_user_role.execute(
        user_id=user_id, role=payload.role, actor_user_id=admin.id, note=payload.note
    )
    # La fila completa del directorio, para que el panel la sustituya tal cual.
    [item] = await container.admin_users.describe([result.user])
    return serializers.admin_user_out(item, locale)


@router.get(
    "/users/{user_id}/role-events",
    response_model=list[UserRoleEventOut],
    summary="Historial de roles",
)
async def list_user_role_events(
    user_id: UUID, container: ContainerDep, _: AdminDep
) -> list[UserRoleEventOut]:
    events = await container.user_role_events.execute(user_id)
    return [serializers.user_role_event_out(event) for event in events]


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
