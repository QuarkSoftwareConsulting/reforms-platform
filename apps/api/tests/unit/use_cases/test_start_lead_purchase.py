"""Tests del caso de uso critico: reserva de plaza y compra del contacto."""

import asyncio

import pytest

from app.domain.exceptions import (
    CategoryMismatchError,
    LeadAlreadyPurchasedError,
    LeadCapReachedError,
    LeadNotFoundError,
    LeadNotPurchasableError,
    ProfessionalProfileIncompleteError,
)
from app.domain.models import Category, LeadStatus, Professional, PurchaseStatus
from tests.conftest import WEB_URL, World
from tests.factories import make_lead, make_purchase


@pytest.fixture
def lead(world: World, carpentry: Category):
    item = make_lead(category_id=carpentry.id, max_purchases=3)
    world.leads.items[item.id] = item
    return item


class TestReservation:
    async def test_creates_reservation_and_checkout_session(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        result = await world.start_purchase.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )

        purchase = world.purchases.items[result.purchase_id]
        assert purchase.status is PurchaseStatus.RESERVED
        assert purchase.price.amount_cents == 500
        assert purchase.stripe_checkout_session_id == result.checkout_session_id
        assert result.checkout_url.startswith("https://checkout.test/")

        # La reserva ocupa plaza pero NO cuenta como venta cerrada.
        assert lead.purchases_count == 0
        assert await world.purchases.count_occupied_slots(lead.id, now=world.clock.now()) == 1

    async def test_reservation_has_ttl(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        result = await world.start_purchase.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )
        purchase = world.purchases.items[result.purchase_id]
        assert purchase.reserved_until is not None
        assert (purchase.reserved_until - world.clock.now()).total_seconds() == 30 * 60

    async def test_checkout_urls_point_back_to_the_web_app(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        await world.start_purchase.execute(lead_id=lead.id, professional_id=madrid_carpenter.id)

        request = world.payments.requests[0]
        assert request.success_url.startswith(f"{WEB_URL}/es/mis-contactos")
        assert str(request.purchase_id) in request.success_url
        assert request.cancel_url == f"{WEB_URL}/es/proyectos/{lead.id}?status=cancelled"
        assert request.amount.amount_cents == 500

    async def test_locale_is_forwarded_to_the_gateway(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        await world.start_purchase.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id, locale="en"
        )
        request = world.payments.requests[0]
        assert request.locale == "en"
        assert request.success_url.startswith(f"{WEB_URL}/en/mis-contactos")
        assert "Carpentry" in request.product_name


class TestLeadCappingUnderConcurrency:
    async def test_two_simultaneous_buyers_cannot_take_the_same_last_slot(
        self, world: World, carpentry: Category
    ) -> None:
        """La carrera que motiva la reserva previa al pago.

        El lead tiene 1 sola plaza. Dos profesionales lanzan la compra a la vez: el
        bloqueo de fila los serializa y el segundo recibe LEAD_CAP_REACHED en vez de
        pagar un contacto que no le corresponde.
        """
        item = make_lead(category_id=carpentry.id, max_purchases=1)
        world.leads.items[item.id] = item
        pro_a = world.add_professional(category_ids={carpentry.id})
        pro_b = world.add_professional(category_ids={carpentry.id})

        results = await asyncio.gather(
            world.start_purchase.execute(lead_id=item.id, professional_id=pro_a.id),
            world.start_purchase.execute(lead_id=item.id, professional_id=pro_b.id),
            return_exceptions=True,
        )

        successes = [r for r in results if not isinstance(r, BaseException)]
        failures = [r for r in results if isinstance(r, BaseException)]

        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], LeadCapReachedError)
        assert world.leads.lock_waits == 1, "la segunda compra debe esperar el bloqueo de fila"
        assert len(world.payments.requests) == 1, "solo se cobra al que consiguio la plaza"

    async def test_reserved_slots_count_towards_the_cap(
        self, world: World, carpentry: Category
    ) -> None:
        item = make_lead(category_id=carpentry.id, max_purchases=2, purchases_count=1)
        world.leads.items[item.id] = item
        # Una compra pagada + una reserva viva = 2 plazas ocupadas de 2.
        paid = make_purchase(lead_id=item.id, status=PurchaseStatus.PAID, paid_at=world.clock.now())
        reserved = make_purchase(lead_id=item.id, reserved_until=world.clock.now().replace(hour=23))
        world.purchases.items[paid.id] = paid
        world.purchases.items[reserved.id] = reserved

        pro = world.add_professional(category_ids={carpentry.id})
        with pytest.raises(LeadCapReachedError):
            await world.start_purchase.execute(lead_id=item.id, professional_id=pro.id)

    async def test_expired_reservation_frees_the_slot_for_someone_else(
        self, world: World, carpentry: Category
    ) -> None:
        item = make_lead(category_id=carpentry.id, max_purchases=1)
        world.leads.items[item.id] = item
        pro_a = world.add_professional(category_ids={carpentry.id})
        pro_b = world.add_professional(category_ids={carpentry.id})

        await world.start_purchase.execute(lead_id=item.id, professional_id=pro_a.id)
        with pytest.raises(LeadCapReachedError):
            await world.start_purchase.execute(lead_id=item.id, professional_id=pro_b.id)

        world.clock.advance(minutes=31)
        result = await world.start_purchase.execute(lead_id=item.id, professional_id=pro_b.id)
        assert result.purchase_id in world.purchases.items


class TestPurchaseGuards:
    async def test_same_professional_cannot_reserve_twice(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        await world.start_purchase.execute(lead_id=lead.id, professional_id=madrid_carpenter.id)
        with pytest.raises(LeadAlreadyPurchasedError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=madrid_carpenter.id)

    async def test_lead_outside_professional_categories_is_rejected(
        self, world: World, lead, plumbing: Category
    ) -> None:
        plumber = world.add_professional(category_ids={plumbing.id})
        with pytest.raises(CategoryMismatchError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=plumber.id)
        assert world.payments.requests == []

    async def test_disabled_lead_cannot_be_purchased(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        lead.disable()
        with pytest.raises(LeadNotPurchasableError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=madrid_carpenter.id)

    async def test_exhausted_lead_cannot_be_purchased(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        lead.status = LeadStatus.EXHAUSTED
        lead.purchases_count = lead.max_purchases
        with pytest.raises(LeadCapReachedError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=madrid_carpenter.id)

    async def test_unknown_lead_raises_not_found(
        self, world: World, madrid_carpenter: Professional
    ) -> None:
        from uuid import uuid4

        with pytest.raises(LeadNotFoundError):
            await world.start_purchase.execute(lead_id=uuid4(), professional_id=madrid_carpenter.id)

    async def test_professional_without_categories_cannot_buy(self, world: World, lead) -> None:
        pro = world.add_professional(category_ids=set())
        with pytest.raises(ProfessionalProfileIncompleteError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=pro.id)


class TestGatewayFailureReleasesTheSlot:
    """Un fallo de la pasarela no debe consumir una plaza del lead.

    Antes de este comportamiento, si Stripe no respondia la compra se quedaba en
    RESERVED y bloqueaba una de las 3 plazas durante todo el TTL, por un fallo de
    nuestra infraestructura y no del profesional.
    """

    async def test_reservation_is_released_when_the_gateway_fails(
        self, world: World, carpentry: Category
    ) -> None:
        item = make_lead(category_id=carpentry.id, max_purchases=1)
        world.leads.items[item.id] = item
        pro = world.add_professional(category_ids={carpentry.id})
        world.payments.fail_on_create = True

        with pytest.raises(RuntimeError):
            await world.start_purchase.execute(lead_id=item.id, professional_id=pro.id)

        purchases = list(world.purchases.items.values())
        assert len(purchases) == 1
        assert purchases[0].status is PurchaseStatus.FAILED
        assert await world.purchases.count_occupied_slots(item.id, now=world.clock.now()) == 0

    async def test_another_professional_can_buy_right_after_a_gateway_failure(
        self, world: World, carpentry: Category
    ) -> None:
        item = make_lead(category_id=carpentry.id, max_purchases=1)
        world.leads.items[item.id] = item
        pro_a = world.add_professional(category_ids={carpentry.id})
        pro_b = world.add_professional(category_ids={carpentry.id})

        world.payments.fail_on_create = True
        with pytest.raises(RuntimeError):
            await world.start_purchase.execute(lead_id=item.id, professional_id=pro_a.id)

        world.payments.fail_on_create = False
        result = await world.start_purchase.execute(lead_id=item.id, professional_id=pro_b.id)
        assert result.checkout_url.startswith("https://checkout.test/")

    async def test_the_same_professional_can_retry_after_a_gateway_failure(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        world.payments.fail_on_create = True
        with pytest.raises(RuntimeError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=madrid_carpenter.id)

        world.payments.fail_on_create = False
        result = await world.start_purchase.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )
        assert world.purchases.items[result.purchase_id].status is PurchaseStatus.RESERVED
