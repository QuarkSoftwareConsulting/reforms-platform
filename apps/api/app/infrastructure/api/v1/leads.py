"""Endpoints de solicitudes: publicacion publica y explorador para profesionales."""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.application.dto import ConsentInput, CreateLeadInput
from app.application.parsing import parse_postal_code
from app.domain.exceptions import UnknownPostalCodeError
from app.domain.models import LeadSource
from app.infrastructure.api import serializers
from app.infrastructure.api.dependencies import (
    ContainerDep,
    CurrentProfessionalDep,
    LocaleDep,
)
from app.infrastructure.api.middlewares.request_context import client_ip, rate_limit_origin
from app.infrastructure.api.schemas.leads import (
    CreateLeadIn,
    CreateLeadOut,
    LeadDetailOut,
    LeadListOut,
    PhoneVerificationIn,
    PhoneVerificationOut,
    PostalCodeOut,
    PresignPhotoIn,
    PresignPhotoOut,
)
from app.infrastructure.api.schemas.purchases import StartPurchaseOut

router = APIRouter(tags=["leads"])


@router.post(
    "/leads",
    response_model=CreateLeadOut,
    status_code=status.HTTP_201_CREATED,
    summary="Publicar una solicitud de trabajo",
)
async def create_lead(
    payload: CreateLeadIn, request: Request, container: ContainerDep
) -> CreateLeadOut:
    """Endpoint publico: el cliente no necesita cuenta para publicar.

    La IP y el user-agent se toman del servidor, nunca del cuerpo de la peticion:
    son la prueba auditable del consentimiento y no deben poder falsificarse.
    """
    settings = container.infra.settings
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
            phone_verification_code=payload.phone_verification_code,
            consent=ConsentInput(
                accepted=payload.consent.accepted,
                policy_version=payload.consent.policy_version or settings.privacy_policy_version,
                ip_address=client_ip(request, settings.trusted_proxy_hops),
                user_agent=request.headers.get("user-agent"),
            ),
        ),
        source=LeadSource.ORGANIC,
    )
    return serializers.created_lead_out(lead)


@router.post(
    "/leads/phone-verification",
    response_model=PhoneVerificationOut,
    summary="Enviar el SMS que verifica el movil del cliente",
)
async def start_phone_verification(
    payload: PhoneVerificationIn, request: Request, container: ContainerDep
) -> PhoneVerificationOut:
    """Endpoint publico, como la publicacion: el cliente no tiene cuenta.

    Con `required=False` el entorno no verifica por SMS y el formulario publica sin
    codigo. El limite de envios por telefono lo aplica el proveedor; el limite por IP
    (contra el "SMS pumping") lo aplica el caso de uso, con la IP tomada del servidor.
    """
    ip = client_ip(request, container.infra.settings.trusted_proxy_hops)
    result = await container.start_phone_verification.execute(
        payload.phone, origin=rate_limit_origin(ip)
    )
    return PhoneVerificationOut(required=result.required)


@router.post(
    "/leads/photos/presign",
    response_model=PresignPhotoOut,
    summary="Obtener URL prefirmada para subir una foto",
)
async def presign_photo(payload: PresignPhotoIn, container: ContainerDep) -> PresignPhotoOut:
    upload = await container.request_photo_upload.execute(
        filename=payload.filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
    )
    return serializers.presign_out(upload)


@router.get("/leads", response_model=LeadListOut, summary="Explorar solicitudes disponibles")
async def list_leads(
    container: ContainerDep,
    professional: CurrentProfessionalDep,
    locale: LocaleDep,
    category_ids: Annotated[list[UUID] | None, Query()] = None,
    radius_km: Annotated[int | None, Query(ge=1, le=300)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LeadListOut:
    result = await container.list_leads.execute(
        professional_id=professional.id,
        category_ids=set(category_ids) if category_ids else None,
        radius_km=radius_km,
        limit=limit,
        offset=offset,
    )
    # La firma de URLs de lectura puede requerir una llamada de red sincrona.
    return await asyncio.to_thread(
        serializers.lead_list_out, result, storage=container.infra.storage, locale=locale
    )


@router.get(
    "/leads/{lead_id}",
    response_model=LeadDetailOut,
    summary="Detalle de una solicitud (contacto oculto hasta la compra)",
)
async def get_lead(
    lead_id: UUID,
    container: ContainerDep,
    professional: CurrentProfessionalDep,
    locale: LocaleDep,
) -> LeadDetailOut:
    detail = await container.lead_detail.execute(lead_id=lead_id, professional_id=professional.id)
    return await asyncio.to_thread(
        serializers.lead_detail_out, detail, storage=container.infra.storage, locale=locale
    )


@router.post(
    "/leads/{lead_id}/purchase",
    response_model=StartPurchaseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Comprar el contacto del cliente",
)
async def start_purchase(
    lead_id: UUID,
    container: ContainerDep,
    professional: CurrentProfessionalDep,
    locale: LocaleDep,
) -> StartPurchaseOut:
    """Reserva la plaza y devuelve la URL del checkout.

    Exige estar al dia con la recarga mensual (402 `SUBSCRIPTION_REQUIRED`). Si el
    saldo cubre el precio, la compra queda pagada sin checkout. Si no, el contacto
    se desbloquea cuando el webhook confirma el pago, no al volver de la pasarela:
    la confirmacion tiene que venir de Stripe, no del navegador.
    """
    result = await container.start_purchase.execute(
        lead_id=lead_id, professional_id=professional.id, locale=locale
    )
    return StartPurchaseOut(
        purchase_id=result.purchase_id,
        checkout_url=result.checkout_url,
        amount=serializers.money_out(result.amount),
        credit_applied=serializers.money_out(result.credit_applied),
        amount_due=serializers.money_out(result.amount_due),
        paid_with_credit=result.paid_with_credit,
        expires_at=result.expires_at,
    )


@router.get(
    "/postal-codes/{code}",
    response_model=PostalCodeOut,
    summary="Resolver ciudad y provincia de un codigo postal",
)
async def get_postal_code(code: str, container: ContainerDep) -> PostalCodeOut:
    info = await container.postal_codes.get(parse_postal_code(code))
    if info is None:
        raise UnknownPostalCodeError(f"Codigo postal no reconocido: {code}")
    return PostalCodeOut(
        code=info.code.value,
        city=info.city,
        province=info.province,
        latitude=info.coordinates.latitude,
        longitude=info.coordinates.longitude,
    )
