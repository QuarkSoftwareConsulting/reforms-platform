"""Endpoints de solicitudes: publicacion publica y explorador para profesionales."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.application.dto import ConsentInput, CreateLeadInput
from app.domain.exceptions import UnknownPostalCodeError
from app.domain.models import LeadSource
from app.domain.value_objects import PostalCode
from app.infrastructure.api import serializers
from app.infrastructure.api.dependencies import (
    ContainerDep,
    CurrentProfessionalDep,
    LocaleDep,
)
from app.infrastructure.api.middlewares.request_context import client_ip
from app.infrastructure.api.schemas.leads import (
    CreateLeadIn,
    CreateLeadOut,
    LeadDetailOut,
    LeadListOut,
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
            consent=ConsentInput(
                accepted=payload.consent.accepted,
                policy_version=payload.consent.policy_version or settings.privacy_policy_version,
                ip_address=client_ip(request),
                user_agent=request.headers.get("user-agent"),
            ),
        ),
        source=LeadSource.ORGANIC,
    )
    return serializers.created_lead_out(lead)


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
    return serializers.lead_list_out(result, storage=container.infra.storage, locale=locale)


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
    return serializers.lead_detail_out(detail, storage=container.infra.storage, locale=locale)


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

    El contacto se desbloquea cuando el webhook confirma el pago, no al volver de
    la pasarela: la confirmacion tiene que venir de Stripe, no del navegador.
    """
    result = await container.start_purchase.execute(
        lead_id=lead_id, professional_id=professional.id, locale=locale
    )
    return StartPurchaseOut(
        purchase_id=result.purchase_id,
        checkout_url=result.checkout_url,
        amount=serializers.money_out(result.amount),
        expires_at=result.expires_at,
    )


@router.get(
    "/postal-codes/{code}",
    response_model=PostalCodeOut,
    summary="Resolver ciudad y provincia de un codigo postal",
)
async def get_postal_code(code: str, container: ContainerDep) -> PostalCodeOut:
    info = await container.postal_codes.get(PostalCode(code))
    if info is None:
        raise UnknownPostalCodeError(f"Codigo postal no reconocido: {code}")
    return PostalCodeOut(
        code=info.code.value,
        city=info.city,
        province=info.province,
        latitude=info.coordinates.latitude,
        longitude=info.coordinates.longitude,
    )
