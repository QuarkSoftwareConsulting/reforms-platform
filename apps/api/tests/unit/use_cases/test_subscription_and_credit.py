"""Recarga mensual: solo compra quien esta al dia, y el saldo se gasta una sola vez."""

import asyncio
from datetime import timedelta

import pytest

from app.application.ports import PaymentEventType
from app.domain.exceptions import (
    InsufficientCreditError,
    PaymentGatewayError,
    ProfessionalAccountNotFoundError,
    SubscriptionAlreadyExistsError,
    SubscriptionRequiredError,
)
from app.domain.models import (
    Category,
    CreditEntryKind,
    Professional,
    PurchaseStatus,
    SubscriptionStatus,
)
from app.domain.value_objects import Money
from tests.conftest import DEFAULT_TOPUP_PRICE_ID, WEB_URL, World
from tests.factories import NOW, make_lead
from tests.fakes import FakePaymentGateway
from tests.fakes.payments import VALID_SIGNATURE

PRICE = Money(1800, "EUR")


@pytest.fixture
def carpentry_18(world: World) -> Category:
    return world.add_category(slug="carpinteria", suggested_lead_price=PRICE)


@pytest.fixture
def lead(world: World, carpentry_18: Category):
    item = make_lead(category_id=carpentry_18.id, max_purchases=5)
    world.leads.items[item.id] = item
    return item


def pro(world: World, category: Category, **kwargs: object) -> Professional:
    return world.add_professional(category_ids={category.id}, **kwargs)


def balance(world: World, professional: Professional) -> int:
    return world.accounts.items[professional.id].balance.amount_cents


async def send(world: World, payload: bytes):
    return await world.handle_event.execute(payload=payload, signature=VALID_SIGNATURE)


class TestSubscriptionGate:
    async def test_without_subscription_cannot_buy(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        with pytest.raises(SubscriptionRequiredError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        assert world.purchases.items == {}
        assert world.leads.lock_waits == 0

    @pytest.mark.parametrize(
        "status",
        [SubscriptionStatus.PENDING, SubscriptionStatus.PAST_DUE, SubscriptionStatus.CANCELED],
    )
    async def test_inactive_subscription_cannot_buy_even_with_balance(
        self, world: World, lead, carpentry_18: Category, status: SubscriptionStatus
    ) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        world.add_account(buyer, subscription_status=status, balance_cents=5000)
        with pytest.raises(SubscriptionRequiredError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        assert balance(world, buyer) == 5000

    async def test_inactive_professional_can_still_browse(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        """Documento del cliente (F02): la cuenta inactiva ve leads, pero no compra."""
        buyer = pro(world, carpentry_18, subscribed=False)
        result = await world.list_leads.execute(professional_id=buyer.id)
        assert [item.lead.id for item in result.items] == [lead.id]

        detail = await world.lead_detail.execute(lead_id=lead.id, professional_id=buyer.id)
        assert not detail.is_unlocked
        assert detail.contact is None


class TestPayingWithCredit:
    async def test_balance_covering_the_price_pays_without_checkout(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, balance_cents=1800)

        result = await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)

        assert result.paid_with_credit
        assert result.checkout_url is None
        assert world.payments.requests == [], "no se abre checkout"
        purchase = world.purchases.items[result.purchase_id]
        assert purchase.status is PurchaseStatus.PAID
        assert purchase.credit_applied == PRICE
        assert world.leads.items[lead.id].purchases_count == 1
        assert balance(world, buyer) == 0
        assert world.ledger.balance_of(buyer.id) == -1800  # solo el SPEND (saldo sembrado)

    async def test_contact_is_unlocked_after_paying_with_credit(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, balance_cents=1800)
        await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)

        detail = await world.lead_detail.execute(lead_id=lead.id, professional_id=buyer.id)
        assert detail.is_unlocked

    async def test_partial_balance_charges_only_the_rest(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, balance_cents=1000)

        result = await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)

        assert not result.paid_with_credit
        assert result.amount == PRICE
        assert result.credit_applied == Money(1000, "EUR")
        assert world.payments.requests[-1].amount == Money(800, "EUR")
        assert world.purchases.items[result.purchase_id].status is PurchaseStatus.RESERVED
        assert balance(world, buyer) == 0

    async def test_without_balance_checkout_charges_the_full_price(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, balance_cents=0)
        result = await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        assert world.payments.requests[-1].amount == PRICE
        assert result.credit_applied.amount_cents == 0
        assert world.ledger.entries == []

    async def test_leaves_the_gateway_minimum_for_checkout(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, balance_cents=1780)
        await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        assert world.payments.requests[-1].amount == Money(50, "EUR")
        assert balance(world, buyer) == 30


class TestCreditIsReturnedWhenTheReservationDies:
    async def test_expired_reservation_returns_the_credit(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, balance_cents=1000)
        await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        assert balance(world, buyer) == 0

        world.clock.advance(minutes=31)
        assert await world.release_reservations.execute() == 1

        assert balance(world, buyer) == 1000
        kinds = [e.kind for e in world.ledger.entries]
        assert kinds == [CreditEntryKind.SPEND, CreditEntryKind.SPEND_REVERSAL]

    async def test_gateway_failure_returns_the_credit(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        world.payments.fail_on_create = True
        buyer = pro(world, carpentry_18, balance_cents=1000)
        with pytest.raises(RuntimeError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        assert balance(world, buyer) == 1000

    async def test_checkout_expired_event_returns_the_credit_once(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, balance_cents=1000)
        result = await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)

        for event_id in ("evt_exp_1", "evt_exp_2"):  # Stripe puede mandar dos distintos
            await send(
                world,
                FakePaymentGateway.event_payload(
                    event_id=event_id,
                    event_type=PaymentEventType.CHECKOUT_EXPIRED,
                    purchase_id=result.purchase_id,
                ),
            )
        # Y el job pasa despues por la misma reserva.
        world.clock.advance(minutes=31)
        await world.release_reservations.execute()

        assert balance(world, buyer) == 1000
        reversals = [e for e in world.ledger.entries if e.kind is CreditEntryKind.SPEND_REVERSAL]
        assert len(reversals) == 1

    async def test_paid_checkout_keeps_the_credit_spent(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, balance_cents=1000)
        result = await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        await send(
            world,
            FakePaymentGateway.event_payload(
                event_id="evt_ok",
                event_type=PaymentEventType.CHECKOUT_COMPLETED,
                purchase_id=result.purchase_id,
            ),
        )
        assert world.purchases.items[result.purchase_id].status is PurchaseStatus.PAID
        assert balance(world, buyer) == 0


class TestCreditUnderConcurrency:
    async def test_two_purchases_cannot_spend_the_same_balance(
        self, world: World, carpentry_18: Category
    ) -> None:
        """Dos compras simultaneas (leads distintos) con saldo para una sola.

        El bloqueo de la cuenta las serializa: la primera gasta el saldo y la
        segunda, al leerlo ya a 0, va al checkout por el precio entero. Sin el
        bloqueo ambas leerian 1800 y el saldo se gastaria dos veces.
        """
        lead_a = make_lead(category_id=carpentry_18.id)
        lead_b = make_lead(category_id=carpentry_18.id)
        world.leads.items[lead_a.id] = lead_a
        world.leads.items[lead_b.id] = lead_b
        buyer = pro(world, carpentry_18, balance_cents=1800)

        results = await asyncio.gather(
            world.start_purchase.execute(lead_id=lead_a.id, professional_id=buyer.id),
            world.start_purchase.execute(lead_id=lead_b.id, professional_id=buyer.id),
        )

        assert sorted(r.paid_with_credit for r in results) == [False, True]
        assert balance(world, buyer) == 0
        spends = [e for e in world.ledger.entries if e.kind is CreditEntryKind.SPEND]
        assert sum(e.amount.amount_cents for e in spends) == 1800
        assert world.accounts.lock_waits >= 1, "la segunda compra debe esperar a la cuenta"


class TestSubscriptionWebhook:
    async def _subscribe(self, world: World, buyer: Professional) -> str:
        url = await world.start_subscription.execute(professional=buyer, email="pro@example.com")
        assert url.startswith("https://checkout.test/")
        account = world.accounts.items[buyer.id]
        assert account.stripe_customer_id is not None
        return account.stripe_customer_id

    async def test_start_subscription_creates_customer_and_checkout(
        self, world: World, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        customer_id = await self._subscribe(world, buyer)

        request = world.payments.subscription_checkouts[-1]
        assert request.customer_id == customer_id
        assert request.success_url == f"{WEB_URL}/es/suscripcion?status=success"
        account = world.accounts.items[buyer.id]
        assert account.subscription_status is SubscriptionStatus.NONE, "no se activa al iniciar"

    async def test_cannot_subscribe_twice(self, world: World, carpentry_18: Category) -> None:
        buyer = pro(world, carpentry_18)  # ya activo
        with pytest.raises(SubscriptionAlreadyExistsError):
            await world.start_subscription.execute(professional=buyer, email="pro@example.com")

    async def test_does_not_open_a_second_checkout_while_the_webhook_is_pending(
        self, world: World, carpentry_18: Category
    ) -> None:
        # El profesional pago, vuelve de Stripe y el webhook aun no ha llegado: la BD
        # dice "sin mensualidad". Pulsar "Activar" otra vez no puede cobrarle dos veces.
        buyer = pro(world, carpentry_18, subscribed=False)
        customer_id = await self._subscribe(world, buyer)
        world.payments.live_subscription_customers.add(customer_id)
        checkouts = len(world.payments.subscription_checkouts)

        with pytest.raises(SubscriptionAlreadyExistsError):
            await world.start_subscription.execute(professional=buyer, email="pro@example.com")

        assert len(world.payments.subscription_checkouts) == checkouts
        assert world.accounts.items[buyer.id].subscription_status is SubscriptionStatus.NONE

    async def test_an_abandoned_checkout_can_be_retried(
        self, world: World, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        await self._subscribe(world, buyer)  # abrio el checkout y no pago

        url = await world.start_subscription.execute(professional=buyer, email="pro@example.com")

        assert url.startswith("https://checkout.test/")
        assert len(world.payments.subscription_checkouts) == 2

    async def test_no_checkout_if_the_gateway_cannot_say_whether_one_exists(
        self, world: World, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        await self._subscribe(world, buyer)
        world.payments.fail_on_live_check = True

        with pytest.raises(PaymentGatewayError):
            await world.start_subscription.execute(professional=buyer, email="pro@example.com")
        assert len(world.payments.subscription_checkouts) == 1

    async def test_invoice_paid_activates_and_credits_the_topup(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        customer_id = await self._subscribe(world, buyer)

        await send(
            world,
            FakePaymentGateway.subscription_event_payload(
                event_id="evt_inv_1",
                event_type=PaymentEventType.INVOICE_PAID,
                customer_id=customer_id,
                invoice_id="in_1",
                amount_cents=1800,
                period_end=NOW + timedelta(days=30),
                occurred_at=NOW,
            ),
        )

        account = world.accounts.items[buyer.id]
        assert account.is_active(world.clock.now())
        assert account.balance == PRICE
        # Y ya puede comprar, con el saldo recien abonado.
        result = await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        assert result.paid_with_credit

    async def test_activates_when_the_subscription_event_is_delivered_before_the_payment(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        # Los tres eventos de un pago con tarjeta, en el orden en que llegaron el 4 de
        # octubre: Stripe emite el cobro un segundo antes, pero no garantiza el orden.
        buyer = pro(world, carpentry_18, subscribed=False)
        customer_id = await self._subscribe(world, buyer)

        for event_id, event_type, status, at in (
            (
                "evt_sub_created",
                PaymentEventType.SUBSCRIPTION_UPDATED,
                SubscriptionStatus.ACTIVE,
                NOW + timedelta(seconds=1),
            ),
            ("evt_inv_1", PaymentEventType.INVOICE_PAID, None, NOW),
            (
                "evt_checkout",
                PaymentEventType.SUBSCRIPTION_CHECKOUT_COMPLETED,
                None,
                NOW + timedelta(seconds=2),
            ),
        ):
            await send(
                world,
                FakePaymentGateway.subscription_event_payload(
                    event_id=event_id,
                    event_type=event_type,
                    customer_id=customer_id,
                    invoice_id="in_1" if event_type is PaymentEventType.INVOICE_PAID else None,
                    amount_cents=1800 if event_type is PaymentEventType.INVOICE_PAID else None,
                    subscription_status=status,
                    occurred_at=at,
                ),
            )

        account = world.accounts.items[buyer.id]
        assert account.subscription_status is SubscriptionStatus.ACTIVE
        assert account.balance == PRICE
        result = await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        assert result.paid_with_credit

    async def test_resent_invoice_is_credited_once(
        self, world: World, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        customer_id = await self._subscribe(world, buyer)

        # El mismo evento reenviado, y el mismo cobro con otro event_id.
        for event_id in ("evt_inv_1", "evt_inv_1", "evt_inv_1_bis"):
            await send(
                world,
                FakePaymentGateway.subscription_event_payload(
                    event_id=event_id,
                    event_type=PaymentEventType.INVOICE_PAID,
                    customer_id=customer_id,
                    invoice_id="in_1",
                    amount_cents=1800,
                ),
            )

        assert balance(world, buyer) == 1800

    async def test_monthly_topups_accumulate(self, world: World, carpentry_18: Category) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        customer_id = await self._subscribe(world, buyer)
        for month in range(3):
            await send(
                world,
                FakePaymentGateway.subscription_event_payload(
                    event_id=f"evt_inv_{month}",
                    event_type=PaymentEventType.INVOICE_PAID,
                    customer_id=customer_id,
                    invoice_id=f"in_{month}",
                    amount_cents=1800,
                ),
            )
        assert balance(world, buyer) == 3 * 1800

    async def test_failed_renewal_blocks_purchases_but_keeps_the_balance(
        self, world: World, lead, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, balance_cents=1800)
        customer_id = world.accounts.items[buyer.id].stripe_customer_id
        assert customer_id is not None

        await send(
            world,
            FakePaymentGateway.subscription_event_payload(
                event_id="evt_fail",
                event_type=PaymentEventType.INVOICE_PAYMENT_FAILED,
                customer_id=customer_id,
                occurred_at=NOW,
            ),
        )

        with pytest.raises(SubscriptionRequiredError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=buyer.id)
        assert balance(world, buyer) == 1800

    async def test_subscription_deleted_cancels(self, world: World, carpentry_18: Category) -> None:
        buyer = pro(world, carpentry_18)
        customer_id = world.accounts.items[buyer.id].stripe_customer_id
        assert customer_id is not None
        await send(
            world,
            FakePaymentGateway.subscription_event_payload(
                event_id="evt_del",
                event_type=PaymentEventType.SUBSCRIPTION_UPDATED,
                customer_id=customer_id,
                subscription_status=SubscriptionStatus.CANCELED,
                occurred_at=NOW,
            ),
        )
        assert world.accounts.items[buyer.id].subscription_status is SubscriptionStatus.CANCELED

    async def test_unknown_customer_fails_so_the_gateway_retries(self, world: World) -> None:
        payload = FakePaymentGateway.subscription_event_payload(
            event_id="evt_ghost",
            event_type=PaymentEventType.INVOICE_PAID,
            customer_id="cus_desconocido",
            invoice_id="in_x",
            amount_cents=1800,
        )
        with pytest.raises(ProfessionalAccountNotFoundError):
            await send(world, payload)
        # La excepcion revierte la transaccion, registro del evento incluido, asi
        # que el reintento de Stripe podra procesarlo.
        assert world.uow.rollbacks == 1


class TestBillingPortalAndSummary:
    async def test_portal_requires_a_customer(self, world: World, carpentry_18: Category) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        with pytest.raises(SubscriptionRequiredError):
            await world.billing_portal.execute(professional_id=buyer.id)

    async def test_portal_url_for_subscribed_professional(
        self, world: World, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18)
        url = await world.billing_portal.execute(professional_id=buyer.id)
        assert url.startswith("https://billing.test/")

    async def test_summary_without_account(self, world: World, carpentry_18: Category) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        summary = await world.get_account.execute(professional_id=buyer.id)
        assert summary.status is SubscriptionStatus.NONE
        assert not summary.is_active
        assert summary.balance.amount_cents == 0
        assert summary.topup_amount == PRICE


class TestAdminAdjustment:
    async def test_admin_credits_and_debits(self, world: World, carpentry_18: Category) -> None:
        buyer = pro(world, carpentry_18, balance_cents=0)
        admin = world.add_user()
        await world.adjust_credit.execute(
            professional_id=buyer.id,
            amount_cents=1800,
            note="Lead duplicado",
            admin_user_id=admin.id,
        )
        await world.adjust_credit.execute(
            professional_id=buyer.id, amount_cents=-500, note="Correccion", admin_user_id=admin.id
        )
        assert balance(world, buyer) == 1300
        assert [e.created_by_user_id for e in world.ledger.entries] == [admin.id, admin.id]

    async def test_debit_cannot_leave_negative_balance(
        self, world: World, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, balance_cents=100)
        with pytest.raises(InsufficientCreditError):
            await world.adjust_credit.execute(
                professional_id=buyer.id,
                amount_cents=-500,
                note="Correccion",
                admin_user_id=world.add_user().id,
            )
        assert balance(world, buyer) == 100
        assert world.ledger.entries == []


class TestConfigurableMonthlyPrice:
    async def test_until_the_admin_sets_it_the_configured_price_is_used(
        self, world: World, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        await world.start_subscription.execute(professional=buyer, email="pro@example.com")

        assert world.payments.subscription_checkouts[-1].price_id == DEFAULT_TOPUP_PRICE_ID
        info = await world.pricing.current()
        assert info.is_default
        assert info.amount == PRICE

    async def test_admin_price_creates_a_gateway_price_used_by_new_subscriptions(
        self, world: World, carpentry_18: Category
    ) -> None:
        admin = world.add_user()
        info = await world.set_subscription_price.execute(amount_cents=2500, admin_user_id=admin.id)

        assert info.amount == Money(2500, "EUR")
        assert not info.is_default
        assert list(world.payments.created_prices.values()) == [Money(2500, "EUR")]

        buyer = pro(world, carpentry_18, subscribed=False)
        await world.start_subscription.execute(professional=buyer, email="pro@example.com")
        assert world.payments.subscription_checkouts[-1].price_id == info.stripe_price_id
        summary = await world.get_account.execute(professional_id=buyer.id)
        assert summary.topup_amount == Money(2500, "EUR")

    async def test_existing_subscriber_keeps_seeing_what_they_actually_pay(
        self, world: World, carpentry_18: Category
    ) -> None:
        buyer = pro(world, carpentry_18, subscribed=False)
        await world.start_subscription.execute(professional=buyer, email="pro@example.com")
        customer_id = world.accounts.items[buyer.id].stripe_customer_id
        assert customer_id is not None
        await send(
            world,
            FakePaymentGateway.subscription_event_payload(
                event_id="evt_inv_old",
                event_type=PaymentEventType.INVOICE_PAID,
                customer_id=customer_id,
                invoice_id="in_old",
                amount_cents=1800,
            ),
        )

        await world.set_subscription_price.execute(
            amount_cents=2500, admin_user_id=world.add_user().id
        )

        summary = await world.get_account.execute(professional_id=buyer.id)
        assert summary.topup_amount == PRICE, "sigue con su importe, no con la tarifa nueva"

    async def test_setting_the_same_price_does_not_create_another(self, world: World) -> None:
        admin = world.add_user()
        await world.set_subscription_price.execute(amount_cents=2500, admin_user_id=admin.id)
        await world.set_subscription_price.execute(amount_cents=2500, admin_user_id=admin.id)
        assert len(world.payments.created_prices) == 1
        assert len(world.subscription_prices.items) == 1

    @pytest.mark.parametrize("cents", [0, 49, 100_001])
    async def test_absurd_prices_are_rejected(self, world: World, cents: int) -> None:
        from app.domain.exceptions import ValidationError

        with pytest.raises((ValidationError, ValueError)):
            await world.set_subscription_price.execute(
                amount_cents=cents, admin_user_id=world.add_user().id
            )
        assert world.payments.created_prices == {}

    async def test_gateway_failure_leaves_the_previous_price(self, world: World) -> None:
        world.payments.fail_on_create = True
        with pytest.raises(RuntimeError):
            await world.set_subscription_price.execute(
                amount_cents=2500, admin_user_id=world.add_user().id
            )
        assert world.subscription_prices.items == []
        assert (await world.pricing.current()).is_default

    async def test_without_any_configured_price_nobody_can_subscribe(
        self, world: World, carpentry_18: Category
    ) -> None:
        from app.domain.exceptions import PaymentGatewayError

        world.pricing.default_price_id = ""
        buyer = pro(world, carpentry_18, subscribed=False)
        with pytest.raises(PaymentGatewayError):
            await world.start_subscription.execute(professional=buyer, email="pro@example.com")
