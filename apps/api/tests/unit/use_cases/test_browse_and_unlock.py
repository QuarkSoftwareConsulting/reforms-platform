"""Tests del explorador, el detalle y el historial: la PII nunca se filtra."""

from uuid import uuid4

import pytest

from app.application.ports import PaymentEventType
from app.domain.exceptions import (
    LeadNotFoundError,
    ProfessionalProfileIncompleteError,
    ValidationError,
)
from app.domain.models import Category, Professional
from app.domain.value_objects import Coordinates, PostalCode
from tests.conftest import World
from tests.factories import BARCELONA, MADRID, make_lead, make_lead_location
from tests.fakes.payments import VALID_SIGNATURE, FakePaymentGateway

ALCALA = Coordinates(40.4818, -3.3644)  # ~30 km de Madrid


def add_lead(world: World, category: Category, **kwargs: object):
    item = make_lead(category_id=category.id, **kwargs)
    world.leads.items[item.id] = item
    return item


class TestExplorer:
    async def test_shows_only_leads_inside_the_service_radius(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        near = add_lead(world, carpentry, location=make_lead_location(coordinates=MADRID))
        far = add_lead(
            world,
            carpentry,
            location=make_lead_location(
                postal_code=PostalCode("08001"),
                city="Barcelona",
                province="Barcelona",
                coordinates=BARCELONA,
            ),
        )

        result = await world.list_leads.execute(professional_id=madrid_carpenter.id)
        ids = {item.lead.id for item in result.items}

        assert near.id in ids
        assert far.id not in ids

    async def test_radius_parameter_can_widen_the_search(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        # Alcala esta a ~30 km: fuera del radio por defecto de 25 km.
        alcala_lead = add_lead(world, carpentry, location=make_lead_location(coordinates=ALCALA))

        default = await world.list_leads.execute(professional_id=madrid_carpenter.id)
        assert alcala_lead.id not in {i.lead.id for i in default.items}

        widened = await world.list_leads.execute(professional_id=madrid_carpenter.id, radius_km=50)
        assert alcala_lead.id in {i.lead.id for i in widened.items}

    async def test_only_shows_the_professionals_own_trades(
        self, world: World, carpentry: Category, plumbing: Category, madrid_carpenter: Professional
    ) -> None:
        mine = add_lead(world, carpentry)
        other = add_lead(world, plumbing)

        result = await world.list_leads.execute(professional_id=madrid_carpenter.id)
        ids = {i.lead.id for i in result.items}

        assert mine.id in ids
        assert other.id not in ids

    async def test_category_filter_cannot_escape_the_declared_trades(
        self, world: World, carpentry: Category, plumbing: Category, madrid_carpenter: Professional
    ) -> None:
        add_lead(world, plumbing)
        result = await world.list_leads.execute(
            professional_id=madrid_carpenter.id, category_ids={plumbing.id}
        )
        assert result.items == []

    async def test_listing_never_contains_client_pii(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        lead = add_lead(world, carpentry)
        result = await world.list_leads.execute(professional_id=madrid_carpenter.id)

        serialized = repr(result)
        assert lead.contact.name not in serialized
        assert lead.contact.phone.value not in serialized
        assert lead.contact.email is not None
        assert lead.contact.email.value not in serialized

    async def test_listing_includes_distance_and_price(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        add_lead(world, carpentry, location=make_lead_location(coordinates=ALCALA))
        result = await world.list_leads.execute(professional_id=madrid_carpenter.id, radius_km=50)
        item = result.items[0]
        assert item.distance_km == pytest.approx(30, abs=3)
        assert item.price.amount_cents == 500
        assert item.category.slug == "carpinteria"

    async def test_disabled_and_exhausted_leads_are_hidden(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        from app.domain.models import LeadStatus

        add_lead(world, carpentry, status=LeadStatus.DISABLED)
        add_lead(world, carpentry, status=LeadStatus.EXHAUSTED, purchases_count=3)
        visible = add_lead(world, carpentry)

        result = await world.list_leads.execute(professional_id=madrid_carpenter.id)
        assert [i.lead.id for i in result.items] == [visible.id]
        assert result.total == 1

    async def test_flags_leads_already_purchased(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        lead = add_lead(world, carpentry)
        reservation = await world.start_purchase.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )
        await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_1",
                event_type=PaymentEventType.CHECKOUT_COMPLETED,
                purchase_id=reservation.purchase_id,
            ),
            signature=VALID_SIGNATURE,
        )

        result = await world.list_leads.execute(professional_id=madrid_carpenter.id)
        assert result.items[0].already_purchased is True

    async def test_pagination_is_capped(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        for _ in range(5):
            add_lead(world, carpentry)
        page = await world.list_leads.execute(
            professional_id=madrid_carpenter.id, limit=2, offset=2
        )
        assert len(page.items) == 2
        assert page.total == 5
        assert page.offset == 2

    async def test_professional_without_trades_cannot_browse(self, world: World) -> None:
        pro = world.add_professional(category_ids=set())
        with pytest.raises(ProfessionalProfileIncompleteError):
            await world.list_leads.execute(professional_id=pro.id)


class TestLeadDetailUnlocking:
    async def test_detail_is_locked_before_payment(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        lead = add_lead(world, carpentry)
        detail = await world.lead_detail.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )

        assert detail.is_unlocked is False
        assert detail.contact is None
        assert detail.lead.masked_phone.endswith("44")
        assert lead.contact.phone.value not in repr(detail)

    async def test_reservation_alone_does_not_unlock(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        lead = add_lead(world, carpentry)
        await world.start_purchase.execute(lead_id=lead.id, professional_id=madrid_carpenter.id)

        detail = await world.lead_detail.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )
        assert detail.is_unlocked is False, "reservar no es pagar"
        assert detail.purchase is not None

    async def test_paid_purchase_unlocks_full_contact(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        lead = add_lead(world, carpentry)
        reservation = await world.start_purchase.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )
        await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_ok",
                event_type=PaymentEventType.CHECKOUT_COMPLETED,
                purchase_id=reservation.purchase_id,
            ),
            signature=VALID_SIGNATURE,
        )

        detail = await world.lead_detail.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )
        assert detail.is_unlocked is True
        assert detail.contact is not None
        assert detail.contact.name == "Ana Lopez"
        assert detail.contact.phone.value == "+34611223344"

    async def test_another_professionals_payment_does_not_unlock_for_me(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        lead = add_lead(world, carpentry)
        buyer = world.add_professional(category_ids={carpentry.id})
        reservation = await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_other",
                event_type=PaymentEventType.CHECKOUT_COMPLETED,
                purchase_id=reservation.purchase_id,
            ),
            signature=VALID_SIGNATURE,
        )

        detail = await world.lead_detail.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )
        assert detail.is_unlocked is False

    async def test_disabled_lead_is_hidden_unless_already_bought(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        lead = add_lead(world, carpentry)
        reservation = await world.start_purchase.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )
        await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_ok",
                event_type=PaymentEventType.CHECKOUT_COMPLETED,
                purchase_id=reservation.purchase_id,
            ),
            signature=VALID_SIGNATURE,
        )
        lead.disable()

        # Quien lo compro conserva el acceso...
        detail = await world.lead_detail.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )
        assert detail.is_unlocked is True

        # ...pero para el resto deja de existir.
        other = world.add_professional(category_ids={carpentry.id})
        with pytest.raises(LeadNotFoundError):
            await world.lead_detail.execute(lead_id=lead.id, professional_id=other.id)

    async def test_unknown_lead_raises(self, world: World, madrid_carpenter: Professional) -> None:
        with pytest.raises(LeadNotFoundError):
            await world.lead_detail.execute(lead_id=uuid4(), professional_id=madrid_carpenter.id)


class TestPurchaseHistory:
    async def test_history_exposes_contact_only_for_paid_entries(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        paid_lead = add_lead(world, carpentry)
        pending_lead = add_lead(world, carpentry)

        paid = await world.start_purchase.execute(
            lead_id=paid_lead.id, professional_id=madrid_carpenter.id
        )
        await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_paid",
                event_type=PaymentEventType.CHECKOUT_COMPLETED,
                purchase_id=paid.purchase_id,
            ),
            signature=VALID_SIGNATURE,
        )
        await world.start_purchase.execute(
            lead_id=pending_lead.id, professional_id=madrid_carpenter.id
        )

        history = await world.my_purchases.execute(professional_id=madrid_carpenter.id)
        by_lead = {entry.lead.id: entry for entry in history}

        assert by_lead[paid_lead.id].contact is not None
        assert by_lead[pending_lead.id].contact is None

    async def test_history_is_scoped_to_the_requesting_professional(
        self, world: World, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        lead = add_lead(world, carpentry)
        other = world.add_professional(category_ids={carpentry.id})
        await world.start_purchase.execute(lead_id=lead.id, professional_id=other.id)

        assert await world.my_purchases.execute(professional_id=madrid_carpenter.id) == []
        assert len(await world.my_purchases.execute(professional_id=other.id)) == 1


class TestPhotoUpload:
    async def test_presigns_allowed_image_types(self, world: World) -> None:
        upload = await world.request_upload.execute(
            filename="cocina.jpg", content_type="image/jpeg"
        )
        assert upload.storage_key.startswith("leads/")
        assert "signature=fake" in upload.upload_url
        assert upload.headers["Content-Type"] == "image/jpeg"

    async def test_rejects_non_image_uploads(self, world: World) -> None:
        with pytest.raises(ValidationError, match="no permitido"):
            await world.request_upload.execute(
                filename="malware.pdf", content_type="application/pdf"
            )

    async def test_rejects_oversized_uploads(self, world: World) -> None:
        with pytest.raises(ValidationError, match="MB"):
            await world.request_upload.execute(
                filename="huge.jpg", content_type="image/jpeg", size_bytes=20 * 1024 * 1024
            )

    async def test_content_type_with_parameters_is_normalized(self, world: World) -> None:
        upload = await world.request_upload.execute(
            filename="a.jpg", content_type="image/jpeg; charset=binary"
        )
        assert upload.headers["Content-Type"] == "image/jpeg"
