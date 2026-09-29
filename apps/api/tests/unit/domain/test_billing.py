"""Reglas de la recarga mensual y del saldo del profesional."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.domain.exceptions import (
    InsufficientCreditError,
    PurchaseNotPayableError,
    SubscriptionAlreadyExistsError,
    SubscriptionRequiredError,
)
from app.domain.models import (
    MIN_CHARGE_CENTS,
    RENEWAL_GRACE,
    CreditEntry,
    CreditEntryKind,
    ProfessionalAccount,
    SubscriptionStatus,
)
from app.domain.value_objects import Money
from tests.factories import NOW, make_account, make_purchase


def entry(account: ProfessionalAccount, kind: CreditEntryKind, cents: int) -> CreditEntry:
    return CreditEntry(
        id=uuid4(),
        professional_id=account.professional_id,
        kind=kind,
        amount=Money(cents, "EUR"),
        source_ref=str(uuid4()),
        created_at=NOW,
    )


class TestActivation:
    def test_new_account_is_not_active(self) -> None:
        account = ProfessionalAccount.open(professional_id=uuid4(), currency="EUR", now=NOW)
        assert account.subscription_status is SubscriptionStatus.NONE
        assert not account.is_active(NOW)
        with pytest.raises(SubscriptionRequiredError):
            account.assert_can_purchase(NOW)

    @pytest.mark.parametrize(
        "status",
        [
            SubscriptionStatus.PENDING,
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.CANCELED,
        ],
    )
    def test_only_an_active_subscription_can_buy(self, status: SubscriptionStatus) -> None:
        account = make_account(subscription_status=status, balance_cents=5000)
        # Tener saldo no basta: sin la recarga al dia no se compra.
        with pytest.raises(SubscriptionRequiredError):
            account.assert_can_purchase(NOW)

    def test_active_account_survives_the_renewal_grace_period(self) -> None:
        account = make_account(current_period_end=NOW)
        assert account.is_active(NOW + RENEWAL_GRACE - timedelta(seconds=1))
        assert not account.is_active(NOW + RENEWAL_GRACE)

    def test_invoice_paid_activates_and_extends_the_period(self) -> None:
        account = make_account(subscription_status=SubscriptionStatus.PENDING)
        end = NOW + timedelta(days=60)
        account.record_invoice_paid(subscription_id="sub_1", period_end=end, at=NOW)
        assert account.subscription_status is SubscriptionStatus.ACTIVE
        assert account.current_period_end == end

    def test_failed_payment_deactivates(self) -> None:
        account = make_account()
        account.record_payment_failed(at=NOW)
        assert account.subscription_status is SubscriptionStatus.PAST_DUE
        assert not account.is_active(NOW)

    def test_gateway_reporting_active_does_not_activate_without_a_paid_invoice(self) -> None:
        """Con SEPA Stripe marca la suscripcion activa mientras el adeudo se procesa."""
        account = make_account(subscription_status=SubscriptionStatus.NONE)
        account.sync_subscription(
            status=SubscriptionStatus.ACTIVE, subscription_id="sub_1", period_end=None, at=NOW
        )
        assert account.subscription_status is SubscriptionStatus.PENDING
        assert not account.is_active(NOW)

    def test_incomplete_status_processed_late_does_not_deactivate(self) -> None:
        account = make_account(subscription_status=SubscriptionStatus.PENDING)
        account.record_invoice_paid(subscription_id="sub_1", period_end=None, at=NOW)
        # `customer.subscription.created` (incomplete) emitido en el mismo segundo.
        account.sync_subscription(
            status=SubscriptionStatus.PENDING, subscription_id="sub_1", period_end=None, at=NOW
        )
        assert account.subscription_status is SubscriptionStatus.ACTIVE

    def test_stale_event_does_not_override_a_newer_one(self) -> None:
        account = make_account()
        account.sync_subscription(
            status=SubscriptionStatus.CANCELED, subscription_id="sub_1", period_end=None, at=NOW
        )
        # Un cobro fallido anterior a la cancelacion llega despues.
        account.record_payment_failed(at=NOW - timedelta(minutes=5))
        assert account.subscription_status is SubscriptionStatus.CANCELED

    def test_checkout_completed_after_payment_does_not_go_back_to_pending(self) -> None:
        account = make_account(subscription_status=SubscriptionStatus.NONE)
        account.record_invoice_paid(subscription_id="sub_1", period_end=None, at=NOW)
        account.record_checkout_completed(subscription_id="sub_1", at=NOW + timedelta(seconds=1))
        assert account.subscription_status is SubscriptionStatus.ACTIVE

    @pytest.mark.parametrize(
        "status",
        [SubscriptionStatus.PENDING, SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE],
    )
    def test_cannot_start_a_second_subscription(self, status: SubscriptionStatus) -> None:
        with pytest.raises(SubscriptionAlreadyExistsError):
            make_account(subscription_status=status).assert_can_start_subscription()

    def test_can_subscribe_again_after_canceling(self) -> None:
        make_account(
            subscription_status=SubscriptionStatus.CANCELED
        ).assert_can_start_subscription()


class TestBalance:
    def test_topup_and_spend_move_the_balance(self) -> None:
        account = make_account(balance_cents=0)
        account.apply(entry(account, CreditEntryKind.TOPUP, 1800))
        account.apply(entry(account, CreditEntryKind.SPEND, 500))
        assert account.balance == Money(1300, "EUR")

    def test_balance_never_goes_negative(self) -> None:
        account = make_account(balance_cents=1000)
        with pytest.raises(InsufficientCreditError):
            account.apply(entry(account, CreditEntryKind.SPEND, 1001))
        assert account.balance == Money(1000, "EUR")

    def test_entry_amount_must_be_positive(self) -> None:
        account = make_account()
        with pytest.raises(ValueError):
            entry(account, CreditEntryKind.TOPUP, -1)

    def test_balance_after_does_not_mutate(self) -> None:
        account = make_account(balance_cents=1000)
        assert account.balance_after(entry(account, CreditEntryKind.SPEND, 400)).amount_cents == 600
        assert account.balance.amount_cents == 1000


class TestCreditToApply:
    def test_uses_the_whole_price_when_the_balance_covers_it(self) -> None:
        account = make_account(balance_cents=5000)
        assert account.credit_to_apply(Money(1800, "EUR")) == Money(1800, "EUR")

    def test_uses_everything_available_when_short(self) -> None:
        account = make_account(balance_cents=1000)
        assert account.credit_to_apply(Money(1800, "EUR")) == Money(1000, "EUR")

    def test_leaves_at_least_the_gateway_minimum_to_charge(self) -> None:
        account = make_account(balance_cents=1780)
        credit = account.credit_to_apply(Money(1800, "EUR"))
        assert 1800 - credit.amount_cents == MIN_CHARGE_CENTS

    def test_no_balance_no_credit(self) -> None:
        assert make_account(balance_cents=0).credit_to_apply(Money(1800, "EUR")).amount_cents == 0

    def test_other_currency_is_never_mixed(self) -> None:
        account = make_account(balance_cents=5000)
        assert account.credit_to_apply(Money(1800, "USD")).amount_cents == 0


class TestPurchaseWithCredit:
    def test_amount_due_is_price_minus_credit(self) -> None:
        purchase = make_purchase(price=Money(1800, "EUR"), credit_applied=Money(1000, "EUR"))
        assert purchase.amount_due == Money(800, "EUR")
        assert not purchase.is_covered_by_credit

    def test_fully_covered_purchase(self) -> None:
        purchase = make_purchase(price=Money(1800, "EUR"), credit_applied=Money(1800, "EUR"))
        assert purchase.is_covered_by_credit

    def test_credit_cannot_exceed_price(self) -> None:
        with pytest.raises(PurchaseNotPayableError):
            make_purchase(price=Money(1800, "EUR"), credit_applied=Money(1801, "EUR"))
