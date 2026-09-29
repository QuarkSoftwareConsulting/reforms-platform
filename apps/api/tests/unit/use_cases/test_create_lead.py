from uuid import uuid4

import pytest

from app.application.dto import ConsentInput, CreateLeadInput
from app.domain.exceptions import (
    CategoryNotFoundError,
    ConsentRequiredError,
    InvalidServiceError,
    PostalCodeNotCoveredError,
    UnknownPostalCodeError,
)
from app.domain.models import (
    Category,
    LeadSource,
    LeadStatus,
    ProjectSchedule,
    PropertyType,
    Service,
)
from tests.conftest import World

DESCRIPTION = (
    "Se ha descolgado la puerta del armario alto de la cocina y necesito "
    "que la vuelvan a montar y ajusten las bisagras."
)


def lead_input(category: Category, **overrides: object) -> CreateLeadInput:
    data: dict[str, object] = {
        "category_id": category.id,
        "title": "Reparar armario de cocina",
        "description": DESCRIPTION,
        "postal_code": "28001",
        "client_name": "Ana Lopez",
        "client_phone": "+34611223344",
        "client_email": "ana@example.com",
        "photo_keys": ["leads/1/a.jpg", "leads/1/b.jpg"],
        "property_type": PropertyType.FLAT,
        "schedule": ProjectSchedule.WITHIN_WEEKS,
        "consent": ConsentInput(
            accepted=True,
            policy_version="2026-01-v1",
            ip_address="83.45.12.9",
            user_agent="Mozilla/5.0",
        ),
    }
    data.update(overrides)
    return CreateLeadInput(**data)  # type: ignore[arg-type]


async def test_publishes_lead_and_resolves_location_from_postal_code(
    world: World, carpentry: Category
) -> None:
    lead = await world.create_lead.execute(lead_input(carpentry), source=LeadSource.ORGANIC)

    assert lead.status is LeadStatus.PUBLISHED
    assert lead.location.city == "Madrid"
    assert lead.location.province == "Madrid"
    assert lead.location.coordinates.latitude == pytest.approx(40.4168)
    assert lead.max_purchases == 5
    assert lead.purchases_count == 0
    assert world.uow.commits == 1


async def test_records_auditable_consent(world: World, carpentry: Category) -> None:
    lead = await world.create_lead.execute(lead_input(carpentry), source=LeadSource.ORGANIC)

    assert lead.consent is not None
    assert lead.consent.policy_version == "2026-01-v1"
    assert lead.consent.ip_address == "83.45.12.9"
    assert lead.consent.user_agent == "Mozilla/5.0"
    assert lead.consent.accepted_at == world.clock.now()
    # El cliente autoriza a un numero concreto de destinatarios, no a "los que sean".
    assert lead.consent.max_recipients == 5
    # La politica vigente informa de que el nombre de pila y el CP se ven antes de pagar.
    assert lead.consent.allows_public_preview is True


async def test_rejects_publication_without_consent(world: World, carpentry: Category) -> None:
    with pytest.raises(ConsentRequiredError):
        await world.create_lead.execute(
            lead_input(carpentry, consent=None), source=LeadSource.ORGANIC
        )
    assert world.leads.items == {}


async def test_rejects_unaccepted_consent_checkbox(world: World, carpentry: Category) -> None:
    with pytest.raises(ConsentRequiredError):
        await world.create_lead.execute(
            lead_input(
                carpentry,
                consent=ConsentInput(accepted=False, policy_version="2026-01-v1"),
            ),
            source=LeadSource.ORGANIC,
        )


async def test_admin_lead_requires_external_consent(world: World, carpentry: Category) -> None:
    lead = await world.create_lead.execute(
        lead_input(
            carpentry,
            consent=ConsentInput(
                accepted=True, policy_version="2026-01-v1", channel="Meta Lead Ads"
            ),
        ),
        source=LeadSource.ADMIN,
    )
    assert lead.source is LeadSource.ADMIN
    assert lead.consent is not None
    assert lead.consent.channel == "Meta Lead Ads"


async def test_unknown_postal_code_is_rejected(world: World, carpentry: Category) -> None:
    # 28999 esta dentro de la zona (Madrid) pero no existe en el catalogo.
    with pytest.raises(UnknownPostalCodeError):
        await world.create_lead.execute(
            lead_input(carpentry, postal_code="28999"), source=LeadSource.ORGANIC
        )


@pytest.mark.parametrize("source", [LeadSource.ORGANIC, LeadSource.ADMIN])
async def test_postal_code_outside_madrid_is_rejected(
    world: World, carpentry: Category, source: LeadSource
) -> None:
    # 08001 (Barcelona) existe en el catalogo: el rechazo es por cobertura, no por CP.
    consent = ConsentInput(
        accepted=True, policy_version="2026-09-v2", channel="Telefono", ip_address=None
    )
    with pytest.raises(PostalCodeNotCoveredError):
        await world.create_lead.execute(
            lead_input(carpentry, postal_code="08001", consent=consent), source=source
        )
    assert world.leads.items == {}


async def test_inactive_category_is_rejected(world: World) -> None:
    inactive = world.add_category(slug="obsoleto", active=False)
    with pytest.raises(CategoryNotFoundError):
        await world.create_lead.execute(lead_input(inactive), source=LeadSource.ORGANIC)


async def test_photos_keep_their_order(world: World, carpentry: Category) -> None:
    lead = await world.create_lead.execute(
        lead_input(carpentry, photo_keys=["z.jpg", "a.jpg"]), source=LeadSource.ORGANIC
    )
    assert [p.storage_key for p in lead.photos] == ["z.jpg", "a.jpg"]
    assert lead.public_view().photo_keys == ["z.jpg", "a.jpg"]


async def test_lead_without_email_is_allowed(world: World, carpentry: Category) -> None:
    lead = await world.create_lead.execute(
        lead_input(carpentry, client_email=None), source=LeadSource.ORGANIC
    )
    assert lead.contact.email is None
    assert lead.public_view().masked_email is None


def with_services(world: World, *slugs: str, slug: str = "reformas") -> Category:
    services = [
        Service(id=uuid4(), slug=s, name_es=s, name_en=s, sort_order=i) for i, s in enumerate(slugs)
    ]
    return world.add_category(slug=slug, services=services)


async def test_stores_services_property_type_and_schedule(world: World) -> None:
    category = with_services(world, "reformas-banos", "reformas-cocinas")
    kitchen, bathroom = category.services[1], category.services[0]

    lead = await world.create_lead.execute(
        lead_input(category, service_ids=[kitchen.id, bathroom.id]), source=LeadSource.ORGANIC
    )

    assert lead.service_ids == [kitchen.id, bathroom.id]
    assert lead.property_type is PropertyType.FLAT
    assert lead.schedule is ProjectSchedule.WITHIN_WEEKS
    view = lead.public_view()
    assert view.service_ids == [kitchen.id, bathroom.id]
    assert view.property_type is PropertyType.FLAT


async def test_rejects_a_service_from_another_category(world: World) -> None:
    reforms = with_services(world, "reformas-banos")
    movers = with_services(world, "portes", slug="mudanzas")

    with pytest.raises(InvalidServiceError):
        await world.create_lead.execute(
            lead_input(reforms, service_ids=[movers.services[0].id]), source=LeadSource.ORGANIC
        )
    assert world.leads.items == {}
