"""Endpoints del profesional: perfil, recarga mensual e historial de contactos."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.application.dto import UpsertProfessionalInput
from app.domain.models import Professional
from app.infrastructure.api import serializers
from app.infrastructure.api.dependencies import (
    ContainerDep,
    CurrentProfessionalDep,
    CurrentUserDep,
    LocaleDep,
)
from app.infrastructure.api.schemas.billing import (
    AccountOut,
    BillingPortalOut,
    SubscriptionCheckoutOut,
)
from app.infrastructure.api.schemas.leads import PresignPhotoOut
from app.infrastructure.api.schemas.professionals import (
    AddDocumentIn,
    MeOut,
    ProfessionalDocumentOut,
    ProfessionalOut,
    ProfessionalUploadIn,
    UpsertProfessionalIn,
)
from app.infrastructure.api.schemas.purchases import PurchasedLeadOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeOut, summary="Datos de la cuenta autenticada")
async def get_me(container: ContainerDep, user: CurrentUserDep, locale: LocaleDep) -> MeOut:
    """Devuelve la cuenta y, si existe, el perfil profesional asociado.

    El frontend lo usa tras el login para decidir si lleva al usuario al
    onboarding de perfil o directamente al explorador.
    """
    professional = await container.professionals.get_by_user_id(user.id)
    profile: ProfessionalOut | None = None
    account: AccountOut | None = None
    if professional is not None:
        categories = await container.categories.get_many(professional.category_ids)
        profile = serializers.professional_out(
            professional, categories, locale, storage=container.infra.storage
        )
        account = serializers.account_out(
            await container.get_account.execute(professional_id=professional.id)
        )

    return MeOut(
        user_id=user.id,
        email=user.email.value,
        role=user.role.value,
        display_name=user.display_name,
        professional=profile,
        account=account,
    )


@router.put(
    "/professional",
    response_model=ProfessionalOut,
    summary="Crear o actualizar el perfil profesional",
)
async def upsert_professional(
    payload: UpsertProfessionalIn,
    container: ContainerDep,
    user: CurrentUserDep,
    locale: LocaleDep,
) -> ProfessionalOut:
    professional = await container.upsert_profile.execute(
        user_id=user.id,
        data=UpsertProfessionalInput(
            business_name=payload.business_name,
            phone=payload.phone,
            postal_code=payload.postal_code,
            service_radius_km=payload.service_radius_km,
            category_ids=set(payload.category_ids),
            service_ids=set(payload.service_ids),
            professional_type=payload.professional_type,
            legal_name=payload.legal_name,
            tax_id=payload.tax_id,
            address=payload.address,
            profile_photo_key=payload.profile_photo_key,
            logo_key=payload.logo_key,
            work_photo_keys=payload.work_photo_keys,
        ),
    )
    return await _profile_out(container, professional, locale)


@router.get(
    "/professional",
    response_model=ProfessionalOut,
    summary="Consultar el perfil profesional",
)
async def get_professional(
    container: ContainerDep, user: CurrentUserDep, locale: LocaleDep
) -> ProfessionalOut:
    profile = await container.get_profile.execute(user_id=user.id)
    return serializers.professional_out(
        profile.professional, profile.categories, locale, storage=container.infra.storage
    )


async def _profile_out(
    container: ContainerDep, professional: Professional, locale: str
) -> ProfessionalOut:
    categories = await container.categories.get_many(professional.category_ids)
    return serializers.professional_out(
        professional, categories, locale, storage=container.infra.storage
    )


@router.post(
    "/professional/uploads",
    response_model=PresignPhotoOut,
    summary="URL prefirmada para subir una foto o un documento del alta",
)
async def request_professional_upload(
    payload: ProfessionalUploadIn,
    container: ContainerDep,
    professional: CurrentProfessionalDep,
) -> PresignPhotoOut:
    """Las fotos van al bucket publico; los documentos, al privado."""
    upload = await container.request_professional_upload.execute(
        professional_id=professional.id,
        purpose=payload.purpose,
        filename=payload.filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
    )
    return serializers.presign_out(upload)


@router.post(
    "/professional/documents",
    response_model=ProfessionalDocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Adjuntar al alta un documento ya subido",
)
async def add_professional_document(
    payload: AddDocumentIn, container: ContainerDep, professional: CurrentProfessionalDep
) -> ProfessionalDocumentOut:
    document = await container.add_professional_document.execute(
        professional_id=professional.id,
        kind=payload.kind,
        storage_key=payload.storage_key,
        filename=payload.filename,
    )
    return serializers.document_out(document)


@router.delete(
    "/professional/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar un documento del alta (solo antes de enviarla)",
)
async def remove_professional_document(
    document_id: UUID, container: ContainerDep, professional: CurrentProfessionalDep
) -> None:
    await container.remove_professional_document.execute(
        professional_id=professional.id, document_id=document_id
    )


@router.post(
    "/professional/submit",
    response_model=ProfessionalOut,
    summary="Enviar el alta a revision",
)
async def submit_for_review(
    container: ContainerDep, professional: CurrentProfessionalDep, locale: LocaleDep
) -> ProfessionalOut:
    """409 PROFILE_INCOMPLETE con `details.missing` si falta algo."""
    submitted = await container.submit_for_review.execute(professional_id=professional.id)
    return await _profile_out(container, submitted, locale)


@router.get(
    "/purchases",
    response_model=list[PurchasedLeadOut],
    summary="Historial de contactos adquiridos",
)
async def list_my_purchases(
    container: ContainerDep,
    professional: CurrentProfessionalDep,
    locale: LocaleDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PurchasedLeadOut]:
    entries = await container.my_purchases.execute(
        professional_id=professional.id, limit=limit, offset=offset
    )
    return [serializers.purchased_lead_out(entry, locale=locale) for entry in entries]


@router.get("/account", response_model=AccountOut, summary="Recarga mensual y saldo")
async def get_account(container: ContainerDep, professional: CurrentProfessionalDep) -> AccountOut:
    summary = await container.get_account.execute(
        professional_id=professional.id, include_entries=True
    )
    return serializers.account_out(summary)


@router.post(
    "/subscription/checkout",
    response_model=SubscriptionCheckoutOut,
    summary="Iniciar la recarga mensual",
)
async def start_subscription(
    container: ContainerDep,
    user: CurrentUserDep,
    professional: CurrentProfessionalDep,
    locale: LocaleDep,
) -> SubscriptionCheckoutOut:
    """Devuelve la URL del checkout de la recarga.

    La cuenta NO se activa aqui ni al volver del checkout: se activa cuando el
    webhook confirma el cobro (`invoice.paid`).
    """
    url = await container.start_subscription.execute(
        professional=professional, email=user.email.value, locale=locale
    )
    return SubscriptionCheckoutOut(checkout_url=url)


@router.post(
    "/subscription/portal",
    response_model=BillingPortalOut,
    summary="Abrir el portal para gestionar el pago de la recarga",
)
async def open_billing_portal(
    container: ContainerDep, professional: CurrentProfessionalDep, locale: LocaleDep
) -> BillingPortalOut:
    url = await container.billing_portal.execute(professional_id=professional.id, locale=locale)
    return BillingPortalOut(url=url)
