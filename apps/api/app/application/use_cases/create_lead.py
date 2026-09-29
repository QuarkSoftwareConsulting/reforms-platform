"""Caso de uso: publicar una solicitud de trabajo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.dto import CreateLeadInput
from app.application.ports import (
    CategoryRepositoryPort,
    ClockPort,
    IdGeneratorPort,
    LeadRepositoryPort,
    PhoneVerificationPort,
    PostalCodeRepositoryPort,
    UnitOfWork,
)
from app.domain.exceptions import (
    CategoryNotFoundError,
    ConsentRequiredError,
    PhoneNotVerifiedError,
    UnknownPostalCodeError,
    ValidationError,
)
from app.domain.models import (
    DEFAULT_MAX_PURCHASES,
    MADRID,
    ClientContact,
    ConsentRecord,
    Lead,
    LeadLocation,
    LeadPhoto,
    LeadSource,
    LeadStatus,
    ServiceArea,
)
from app.domain.value_objects import Email, PhoneNumber, PostalCode


@dataclass(slots=True)
class CreateLead:
    """Crea el lead a partir del formulario publico o del panel de admin.

    Resuelve la ubicacion desde el catalogo de codigos postales en vez de llamar a
    un geocoder externo: en Espana el CP da precision de barrio, que es mas de lo
    que necesita un filtro por radio, y evita una dependencia de red en el camino
    critico de publicacion.
    """

    leads: LeadRepositoryPort
    categories: CategoryRepositoryPort
    postal_codes: PostalCodeRepositoryPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork
    max_purchases: int = DEFAULT_MAX_PURCHASES
    service_area: ServiceArea = MADRID
    phone_verifier: PhoneVerificationPort | None = None
    """`None` = verificacion por SMS desactivada (no hay proveedor configurado)."""

    async def execute(self, data: CreateLeadInput, *, source: LeadSource) -> Lead:
        category = await self.categories.get(data.category_id)
        if category is None or not category.active:
            raise CategoryNotFoundError()

        postal_code = PostalCode(data.postal_code)
        # Antes de consultar el catalogo: un CP real pero fuera de zona debe decir
        # "fuera de cobertura", no "no reconocido".
        self.service_area.assert_covers(postal_code)
        location_info = await self.postal_codes.get(postal_code)
        if location_info is None:
            raise UnknownPostalCodeError(f"Codigo postal no reconocido: {postal_code}")

        services = category.resolve_services(data.service_ids)

        now = self.clock.now()
        consent = self._build_consent(data, source=source, now=now)

        lead = Lead(
            id=self.ids.new_id(),
            category_id=category.id,
            title=data.title,
            description=data.description,
            location=LeadLocation(
                postal_code=location_info.code,
                city=location_info.city,
                province=location_info.province,
                coordinates=location_info.coordinates,
            ),
            contact=ClientContact(
                name=data.client_name,
                phone=PhoneNumber(data.client_phone),
                email=Email(data.client_email) if data.client_email else None,
            ),
            created_at=now,
            status=LeadStatus.PUBLISHED,
            source=source,
            max_purchases=self.max_purchases,
            purchases_count=0,
            published_at=now,
            photos=[
                LeadPhoto(storage_key=key, sort_order=index)
                for index, key in enumerate(data.photo_keys)
            ],
            consent=consent,
            service_ids=[service.id for service in services],
            property_type=data.property_type,
            schedule=data.schedule,
        )

        # Lo ultimo antes de guardar: el codigo se consume al confirmarlo, y un
        # error en cualquier otro campo no debe obligar a pedir un SMS nuevo. Los
        # leads del admin llegan de campanas externas: su telefono lo comprueba la
        # llamada de verificacion, no un SMS.
        if source is LeadSource.ORGANIC:
            await self._confirm_phone(lead.contact.phone, data.phone_verification_code)

        async with self.uow:
            return await self.leads.add(lead)

    async def _confirm_phone(self, phone: PhoneNumber, code: str | None) -> None:
        if self.phone_verifier is None:
            return
        if not code or not await self.phone_verifier.confirm_code(phone, code.strip()):
            raise PhoneNotVerifiedError()

    def _build_consent(
        self, data: CreateLeadInput, *, source: LeadSource, now: datetime
    ) -> ConsentRecord | None:
        if data.consent is None or not data.consent.accepted:
            raise ConsentRequiredError()
        if source is LeadSource.ADMIN and data.consent.channel is None:
            raise ConsentRequiredError("Indica el canal donde se recogio el consentimiento")
        accepted_at = data.consent.accepted_at or now
        if accepted_at > now:
            raise ValidationError("La fecha del consentimiento no puede estar en el futuro")
        return ConsentRecord(
            policy_version=data.consent.policy_version,
            ip_address=data.consent.ip_address,
            user_agent=data.consent.user_agent,
            accepted_at=accepted_at,
            max_recipients=self.max_purchases,
            channel=data.consent.channel,
            campaign_reference=data.consent.campaign_reference,
            # La politica vigente (2026-09-v2) ya informa de que el nombre de pila y
            # el CP se muestran antes de la compra; el admin solo registra leads
            # captados bajo esa misma politica.
            allows_public_preview=True,
        )
