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
    PostalCodeRepositoryPort,
    UnitOfWork,
)
from app.domain.exceptions import (
    CategoryNotFoundError,
    ConsentRequiredError,
    UnknownPostalCodeError,
)
from app.domain.models import (
    ClientContact,
    ConsentRecord,
    Lead,
    LeadLocation,
    LeadPhoto,
    LeadSource,
    LeadStatus,
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
    max_purchases: int = 3

    async def execute(self, data: CreateLeadInput, *, source: LeadSource) -> Lead:
        category = await self.categories.get(data.category_id)
        if category is None or not category.active:
            raise CategoryNotFoundError()

        postal_code = PostalCode(data.postal_code)
        location_info = await self.postal_codes.get(postal_code)
        if location_info is None:
            raise UnknownPostalCodeError(f"Codigo postal no reconocido: {postal_code}")

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
        )

        async with self.uow:
            return await self.leads.add(lead)

    def _build_consent(
        self, data: CreateLeadInput, *, source: LeadSource, now: datetime
    ) -> ConsentRecord | None:
        if source is LeadSource.ADMIN:
            # El lead viene de una campana de marketing: el consentimiento se
            # recogio en el canal de origen y el admin responde de su trazabilidad.
            return None
        if data.consent is None or not data.consent.accepted:
            raise ConsentRequiredError()
        return ConsentRecord(
            policy_version=data.consent.policy_version,
            ip_address=data.consent.ip_address,
            user_agent=data.consent.user_agent,
            accepted_at=now,
            max_recipients=self.max_purchases,
        )
