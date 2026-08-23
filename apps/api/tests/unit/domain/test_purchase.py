from datetime import timedelta

import pytest

from app.domain.exceptions import PurchaseNotPayableError
from app.domain.models import PurchaseStatus
from tests.factories import NOW, make_purchase


def test_reserved_purchase_occupies_a_slot() -> None:
    purchase = make_purchase(reserved_until=NOW + timedelta(minutes=30))
    assert purchase.occupies_slot_at(NOW) is True
    assert purchase.unlocks_contact is False


def test_expired_reservation_frees_the_slot() -> None:
    purchase = make_purchase(reserved_until=NOW - timedelta(minutes=1))
    assert purchase.is_reservation_expired(NOW) is True
    assert purchase.occupies_slot_at(NOW) is False


def test_mark_paid_unlocks_contact_and_clears_reservation() -> None:
    purchase = make_purchase(reserved_until=NOW + timedelta(minutes=30))
    purchase.mark_paid(now=NOW, payment_intent_id="pi_123")

    assert purchase.status is PurchaseStatus.PAID
    assert purchase.unlocks_contact is True
    assert purchase.paid_at == NOW
    assert purchase.reserved_until is None
    assert purchase.stripe_payment_intent_id == "pi_123"


def test_mark_paid_is_idempotent_for_webhook_retries() -> None:
    purchase = make_purchase(reserved_until=NOW + timedelta(minutes=30))
    purchase.mark_paid(now=NOW, payment_intent_id="pi_123")
    later = NOW + timedelta(minutes=5)

    purchase.mark_paid(now=later, payment_intent_id="pi_other")

    assert purchase.paid_at == NOW
    assert purchase.stripe_payment_intent_id == "pi_123"


def test_paying_an_expired_reservation_is_rejected() -> None:
    purchase = make_purchase(status=PurchaseStatus.EXPIRED)
    with pytest.raises(PurchaseNotPayableError):
        purchase.mark_paid(now=NOW)


def test_mark_expired_only_affects_reservations() -> None:
    reserved = make_purchase(reserved_until=NOW)
    reserved.mark_expired()
    assert reserved.status is PurchaseStatus.EXPIRED

    paid = make_purchase(status=PurchaseStatus.PAID, paid_at=NOW)
    paid.mark_expired()
    assert paid.status is PurchaseStatus.PAID


def test_paid_purchase_cannot_be_marked_failed() -> None:
    paid = make_purchase(status=PurchaseStatus.PAID, paid_at=NOW)
    with pytest.raises(PurchaseNotPayableError):
        paid.mark_failed()


def test_refund_keeps_the_slot_occupied() -> None:
    # El contacto ya se mostro al profesional, asi que la plaza no se reutiliza.
    paid = make_purchase(status=PurchaseStatus.PAID, paid_at=NOW)
    paid.mark_refunded()
    assert paid.status is PurchaseStatus.REFUNDED
    assert paid.occupies_slot_at(NOW) is True
    assert paid.unlocks_contact is False


def test_refunding_unpaid_purchase_is_rejected() -> None:
    with pytest.raises(PurchaseNotPayableError):
        make_purchase().mark_refunded()


def test_attach_checkout_session_requires_reservation() -> None:
    purchase = make_purchase()
    purchase.attach_checkout_session("cs_test_123")
    assert purchase.stripe_checkout_session_id == "cs_test_123"

    paid = make_purchase(status=PurchaseStatus.PAID, paid_at=NOW)
    with pytest.raises(PurchaseNotPayableError):
        paid.attach_checkout_session("cs_test_456")
