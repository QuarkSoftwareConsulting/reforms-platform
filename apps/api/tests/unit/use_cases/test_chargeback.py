"""Recarga devuelta por el banco: se retira el saldo y lo gastado queda como deuda."""

import pytest

from app.application.ports import ChargeOwner, PaymentEventType
from app.domain.exceptions import (
    CreditDebtOutstandingError,
    PaymentGatewayError,
    ProfessionalAccountNotFoundError,
)
from app.domain.models import Category, CreditEntryKind, Professional
from app.domain.value_objects import Money
from tests.conftest import World
from tests.factories import make_lead
from tests.fakes import FakePaymentGateway
from tests.fakes.payments import VALID_SIGNATURE

PRICE = Money(500, "EUR")


@pytest.fixture
def carpentry_5(world: World) -> Category:
    return world.add_category(slug="carpinteria", suggested_lead_price=PRICE)


def topup_payer(world: World, category: Category, *, balance_cents: int) -> Professional:
    """Profesional cuya recarga se cobro con el cargo `ch_topup`."""
    professional = world.add_professional(category_ids={category.id}, balance_cents=balance_cents)
    customer_id = world.accounts.items[professional.id].stripe_customer_id
    world.payments.charge_owners["ch_topup"] = ChargeOwner(
        customer_id=customer_id, purchase_id=None
    )
    return professional


async def dispute(
    world: World, event_type: PaymentEventType, *, event_id: str = "evt_dp_1", **kwargs: object
):
    payload = FakePaymentGateway.dispute_event_payload(
        event_id=event_id,
        event_type=event_type,
        **kwargs,  # type: ignore[arg-type]
    )
    return await world.handle_event.execute(payload=payload, signature=VALID_SIGNATURE)


def account_of(world: World, professional: Professional):
    return world.accounts.items[professional.id]


class TestChargeback:
    async def test_spent_top_up_becomes_debt_and_blocks_buying(
        self, world: World, carpentry_5: Category
    ) -> None:
        # Pago 18 EUR, gasto 13 en contactos y le quedan 5; el banco devuelve los 18.
        buyer = topup_payer(world, carpentry_5, balance_cents=500)

        outcome = await dispute(world, PaymentEventType.CHARGE_DISPUTED)

        assert outcome.handled
        account = account_of(world, buyer)
        assert account.balance == Money(0, "EUR")
        assert account.debt == Money(1300, "EUR")
        assert account.is_active(world.clock.now()), "la recarga sigue al dia"
        lead = make_lead(category_id=carpentry_5.id)
        world.leads.items[lead.id] = lead
        with pytest.raises(CreditDebtOutstandingError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        # El libro cuadra con saldo y deuda (los 5 EUR iniciales no pasaron por el libro).
        assert world.ledger.balance_of(buyer.id) == (0 - 1300) - 500

    async def test_created_and_funds_withdrawn_debit_once(
        self, world: World, carpentry_5: Category
    ) -> None:
        # Stripe manda ambos eventos para la misma disputa (y los reenvia).
        buyer = topup_payer(world, carpentry_5, balance_cents=1800)
        for event_id in ("evt_created", "evt_created", "evt_withdrawn"):
            await dispute(world, PaymentEventType.CHARGE_DISPUTED, event_id=event_id)

        chargebacks = [e for e in world.ledger.entries if e.kind is CreditEntryKind.CHARGEBACK]
        assert len(chargebacks) == 1
        assert account_of(world, buyer).balance == Money(0, "EUR")
        assert account_of(world, buyer).debt == Money(0, "EUR")

    async def test_the_next_top_up_settles_the_debt_first(
        self, world: World, carpentry_5: Category
    ) -> None:
        buyer = topup_payer(world, carpentry_5, balance_cents=500)
        await dispute(world, PaymentEventType.CHARGE_DISPUTED)
        customer_id = account_of(world, buyer).stripe_customer_id

        await world.handle_event.execute(
            payload=FakePaymentGateway.subscription_event_payload(
                event_id="evt_inv_2",
                event_type=PaymentEventType.INVOICE_PAID,
                customer_id=customer_id,
                invoice_id="in_2",
                amount_cents=1800,
            ),
            signature=VALID_SIGNATURE,
        )

        account = account_of(world, buyer)
        assert account.debt == Money(0, "EUR")
        assert account.balance == Money(500, "EUR")
        account.assert_can_purchase(world.clock.now())

    async def test_a_won_dispute_gives_the_balance_back(
        self, world: World, carpentry_5: Category
    ) -> None:
        buyer = topup_payer(world, carpentry_5, balance_cents=500)
        await dispute(world, PaymentEventType.CHARGE_DISPUTED)
        # `funds_reinstated` y `closed` (won): se devuelve una sola vez.
        for event_id in ("evt_won", "evt_closed"):
            await dispute(world, PaymentEventType.DISPUTE_WON, event_id=event_id)

        account = account_of(world, buyer)
        assert account.debt == Money(0, "EUR")
        assert account.balance == Money(500, "EUR")
        reversals = [
            e for e in world.ledger.entries if e.kind is CreditEntryKind.CHARGEBACK_REVERSAL
        ]
        assert [e.amount for e in reversals] == [Money(1800, "EUR")]

    async def test_winning_without_a_withdrawal_credits_nothing(
        self, world: World, carpentry_5: Category
    ) -> None:
        buyer = topup_payer(world, carpentry_5, balance_cents=500)
        await dispute(world, PaymentEventType.DISPUTE_WON, dispute_id="dp_inquiry")
        assert account_of(world, buyer).balance == Money(500, "EUR")

    async def test_a_disputed_contact_purchase_does_not_touch_the_balance(
        self, world: World, carpentry_5: Category
    ) -> None:
        buyer = topup_payer(world, carpentry_5, balance_cents=500)
        customer_id = account_of(world, buyer).stripe_customer_id
        world.payments.charge_owners["ch_lead"] = ChargeOwner(
            customer_id=customer_id, purchase_id=make_lead().id
        )

        outcome = await dispute(world, PaymentEventType.CHARGE_DISPUTED, charge_id="ch_lead")

        assert not outcome.handled
        assert account_of(world, buyer).balance == Money(500, "EUR")
        assert world.ledger.entries == []

    async def test_a_gateway_failure_leaves_the_event_to_be_retried(
        self, world: World, carpentry_5: Category
    ) -> None:
        buyer = topup_payer(world, carpentry_5, balance_cents=500)
        world.payments.fail_on_describe = True
        with pytest.raises(PaymentGatewayError):
            await dispute(world, PaymentEventType.CHARGE_DISPUTED)
        assert world.processed_events.seen == {}

        world.payments.fail_on_describe = False
        await dispute(world, PaymentEventType.CHARGE_DISPUTED)
        assert account_of(world, buyer).debt == Money(1300, "EUR")

    async def test_an_unknown_customer_is_retried_instead_of_lost(self, world: World) -> None:
        world.payments.charge_owners["ch_topup"] = ChargeOwner(
            customer_id="cus_nadie", purchase_id=None
        )
        # El error revierte el registro del evento (lo prueba Postgres; este fake no
        # es transaccional) y la pasarela lo reintentara.
        with pytest.raises(ProfessionalAccountNotFoundError):
            await dispute(world, PaymentEventType.CHARGE_DISPUTED)
