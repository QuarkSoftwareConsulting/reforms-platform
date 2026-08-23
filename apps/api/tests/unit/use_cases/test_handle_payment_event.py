"""Tests del webhook de pagos: confirmacion, idempotencia y liberacion de plazas."""

import pytest

from app.application.ports import PaymentEventType
from app.domain.exceptions import AuthenticationError, PurchaseNotFoundError
from app.domain.models import Category, LeadStatus, Professional, PurchaseStatus
from tests.conftest import World
from tests.factories import make_lead
from tests.fakes.payments import VALID_SIGNATURE, FakePaymentGateway


async def _reserve(world: World, lead_id, professional_id):
    return await world.start_purchase.execute(lead_id=lead_id, professional_id=professional_id)


@pytest.fixture
def lead(world: World, carpentry: Category):
    item = make_lead(category_id=carpentry.id, max_purchases=3)
    world.leads.items[item.id] = item
    return item


class TestConfirmation:
    async def test_completed_checkout_marks_paid_and_counts_the_sale(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        reservation = await _reserve(world, lead.id, madrid_carpenter.id)

        outcome = await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_1",
                event_type=PaymentEventType.CHECKOUT_COMPLETED,
                purchase_id=reservation.purchase_id,
                checkout_session_id=reservation.checkout_session_id,
            ),
            signature=VALID_SIGNATURE,
        )

        assert outcome.handled is True
        purchase = world.purchases.items[reservation.purchase_id]
        assert purchase.status is PurchaseStatus.PAID
        assert purchase.paid_at == world.clock.now()
        assert purchase.stripe_payment_intent_id == "pi_test_0001"
        assert lead.purchases_count == 1
        assert lead.status is LeadStatus.PUBLISHED

    async def test_third_sale_exhausts_the_lead(self, world: World, carpentry: Category) -> None:
        item = make_lead(category_id=carpentry.id, max_purchases=3)
        world.leads.items[item.id] = item

        for index in range(3):
            pro = world.add_professional(category_ids={carpentry.id})
            reservation = await _reserve(world, item.id, pro.id)
            await world.handle_event.execute(
                payload=FakePaymentGateway.event_payload(
                    event_id=f"evt_{index}",
                    event_type=PaymentEventType.CHECKOUT_COMPLETED,
                    purchase_id=reservation.purchase_id,
                ),
                signature=VALID_SIGNATURE,
            )

        assert item.purchases_count == 3
        assert item.status is LeadStatus.EXHAUSTED

        # Un cuarto profesional ya no puede comprarlo.
        from app.domain.exceptions import LeadCapReachedError

        fourth = world.add_professional(category_ids={carpentry.id})
        with pytest.raises(LeadCapReachedError):
            await _reserve(world, item.id, fourth.id)

    async def test_event_can_be_resolved_by_checkout_session_alone(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        reservation = await _reserve(world, lead.id, madrid_carpenter.id)

        outcome = await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_no_metadata",
                event_type=PaymentEventType.CHECKOUT_COMPLETED,
                purchase_id=None,
                checkout_session_id=reservation.checkout_session_id,
            ),
            signature=VALID_SIGNATURE,
        )
        assert outcome.handled is True
        assert world.purchases.items[reservation.purchase_id].status is PurchaseStatus.PAID


class TestIdempotency:
    async def test_replaying_the_same_event_does_not_double_count(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        reservation = await _reserve(world, lead.id, madrid_carpenter.id)
        payload = FakePaymentGateway.event_payload(
            event_id="evt_dup",
            event_type=PaymentEventType.CHECKOUT_COMPLETED,
            purchase_id=reservation.purchase_id,
        )

        first = await world.handle_event.execute(payload=payload, signature=VALID_SIGNATURE)
        second = await world.handle_event.execute(payload=payload, signature=VALID_SIGNATURE)

        assert first.handled is True
        assert first.duplicate is False
        assert second.handled is False
        assert second.duplicate is True
        assert lead.purchases_count == 1, "el contador del lead solo se incrementa una vez"

    async def test_distinct_event_ids_for_an_already_paid_purchase_are_harmless(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        """Stripe puede emitir varios eventos distintos sobre el mismo pago."""
        reservation = await _reserve(world, lead.id, madrid_carpenter.id)
        for event_id in ("evt_a", "evt_b"):
            await world.handle_event.execute(
                payload=FakePaymentGateway.event_payload(
                    event_id=event_id,
                    event_type=PaymentEventType.CHECKOUT_COMPLETED,
                    purchase_id=reservation.purchase_id,
                ),
                signature=VALID_SIGNATURE,
            )
        assert lead.purchases_count == 1


class TestFailureAndExpiry:
    async def test_expired_checkout_releases_the_slot(
        self, world: World, carpentry: Category
    ) -> None:
        item = make_lead(category_id=carpentry.id, max_purchases=1)
        world.leads.items[item.id] = item
        pro_a = world.add_professional(category_ids={carpentry.id})
        pro_b = world.add_professional(category_ids={carpentry.id})

        reservation = await _reserve(world, item.id, pro_a.id)
        await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_expired",
                event_type=PaymentEventType.CHECKOUT_EXPIRED,
                purchase_id=reservation.purchase_id,
            ),
            signature=VALID_SIGNATURE,
        )

        assert world.purchases.items[reservation.purchase_id].status is PurchaseStatus.EXPIRED
        assert item.purchases_count == 0
        # La plaza vuelve a estar libre inmediatamente, sin esperar el TTL.
        assert await _reserve(world, item.id, pro_b.id) is not None

    async def test_failed_payment_marks_the_purchase_failed(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        reservation = await _reserve(world, lead.id, madrid_carpenter.id)
        await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_failed",
                event_type=PaymentEventType.PAYMENT_FAILED,
                purchase_id=reservation.purchase_id,
            ),
            signature=VALID_SIGNATURE,
        )
        assert world.purchases.items[reservation.purchase_id].status is PurchaseStatus.FAILED
        assert lead.purchases_count == 0

    async def test_refund_keeps_the_sale_counted(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        reservation = await _reserve(world, lead.id, madrid_carpenter.id)
        await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_paid",
                event_type=PaymentEventType.CHECKOUT_COMPLETED,
                purchase_id=reservation.purchase_id,
            ),
            signature=VALID_SIGNATURE,
        )
        await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_refund",
                event_type=PaymentEventType.REFUNDED,
                purchase_id=reservation.purchase_id,
            ),
            signature=VALID_SIGNATURE,
        )

        purchase = world.purchases.items[reservation.purchase_id]
        assert purchase.status is PurchaseStatus.REFUNDED
        assert purchase.unlocks_contact is False
        # El dato personal ya se cedio: la plaza no se reutiliza.
        assert lead.purchases_count == 1


class TestSecurityAndNoise:
    async def test_invalid_signature_is_rejected(self, world: World) -> None:
        with pytest.raises(AuthenticationError):
            await world.handle_event.execute(
                payload=FakePaymentGateway.event_payload(
                    event_id="evt_x", event_type=PaymentEventType.CHECKOUT_COMPLETED
                ),
                signature="firma-falsa",
            )
        assert world.processed_events.seen == {}

    async def test_irrelevant_event_is_ignored_without_touching_state(self, world: World) -> None:
        outcome = await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_noise",
                event_type=PaymentEventType.IGNORED,
                raw_type="customer.updated",
            ),
            signature=VALID_SIGNATURE,
        )
        assert outcome.handled is False
        assert outcome.duplicate is False
        assert world.processed_events.seen == {}

    async def test_event_for_unknown_purchase_raises(self, world: World) -> None:
        from uuid import uuid4

        with pytest.raises(PurchaseNotFoundError):
            await world.handle_event.execute(
                payload=FakePaymentGateway.event_payload(
                    event_id="evt_orphan",
                    event_type=PaymentEventType.CHECKOUT_COMPLETED,
                    purchase_id=uuid4(),
                ),
                signature=VALID_SIGNATURE,
            )
