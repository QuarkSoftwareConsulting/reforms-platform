"""Tests del adaptador real de Stripe.

No necesitan cuenta ni red: la verificacion de firma del webhook es solo un
HMAC-SHA256 con nuestro propio secreto, asi que podemos construir eventos
autenticos y comprobar que el adaptador los traduce bien.

Estos tests existen porque los fakes no pueden detectar los desajustes con el SDK
real: `event.data.object` es un StripeObject y no un dict, y llamar a `.get()`
sobre el reventaba en produccion aunque toda la suite con fakes pasara.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.ports import PaymentEventType
from app.domain.exceptions import AuthenticationError
from app.domain.models import SubscriptionStatus
from app.infrastructure.adapters.payments.stripe_adapter import StripePaymentGateway

WEBHOOK_SECRET = "whsec_test_secret"


def sign(payload: str, secret: str = WEBHOOK_SECRET, timestamp: int | None = None) -> str:
    """Construye la cabecera Stripe-Signature igual que lo hace Stripe."""
    ts = timestamp if timestamp is not None else int(time.time())
    signature = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={signature}"


def checkout_completed_payload(
    purchase_id: str,
    *,
    event_id: str = "evt_test_1",
    event_type: str = "checkout.session.completed",
) -> str:
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "object": "checkout.session",
                    "payment_intent": "pi_test_456",
                    "amount_total": 500,
                    "currency": "eur",
                    "metadata": {"purchase_id": purchase_id, "lead_id": str(uuid4())},
                }
            },
        },
        separators=(",", ":"),
    )


@pytest.fixture
def gateway() -> StripePaymentGateway:
    return StripePaymentGateway(secret_key="sk_test_fake", webhook_secret=WEBHOOK_SECRET)


class TestWebhookParsing:
    def test_parses_a_genuinely_signed_checkout_completed_event(
        self, gateway: StripePaymentGateway
    ) -> None:
        purchase_id = uuid4()
        payload = checkout_completed_payload(str(purchase_id))

        event = gateway.parse_webhook_event(payload.encode(), sign(payload))

        assert event.type is PaymentEventType.CHECKOUT_COMPLETED
        assert event.raw_type == "checkout.session.completed"
        assert event.purchase_id == purchase_id
        assert event.checkout_session_id == "cs_test_123"
        assert event.payment_intent_id == "pi_test_456"
        assert event.amount_cents == 500
        assert event.currency == "EUR"

    def test_stores_only_minimal_audit_data_in_the_payload(
        self, gateway: StripePaymentGateway
    ) -> None:
        payload = checkout_completed_payload(str(uuid4()))
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))

        assert set(event.payload) == {"id", "type"}

    def test_maps_async_payment_success_to_completed(self, gateway: StripePaymentGateway) -> None:
        payload = checkout_completed_payload(
            str(uuid4()), event_type="checkout.session.async_payment_succeeded"
        )
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))
        assert event.type is PaymentEventType.CHECKOUT_COMPLETED

    def test_maps_expiry_and_failure_events(self, gateway: StripePaymentGateway) -> None:
        for raw_type, expected in (
            ("checkout.session.expired", PaymentEventType.CHECKOUT_EXPIRED),
            ("checkout.session.async_payment_failed", PaymentEventType.PAYMENT_FAILED),
            ("payment_intent.payment_failed", PaymentEventType.PAYMENT_FAILED),
            ("charge.refunded", PaymentEventType.REFUNDED),
        ):
            payload = checkout_completed_payload(str(uuid4()), event_type=raw_type)
            event = gateway.parse_webhook_event(payload.encode(), sign(payload))
            assert event.type is expected, raw_type

    def test_unrelated_events_are_marked_ignored(self, gateway: StripePaymentGateway) -> None:
        payload = checkout_completed_payload(str(uuid4()), event_type="customer.updated")
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))

        assert event.type is PaymentEventType.IGNORED
        assert event.raw_type == "customer.updated"

    def test_event_without_metadata_yields_no_purchase_id(
        self, gateway: StripePaymentGateway
    ) -> None:
        payload = json.dumps(
            {
                "id": "evt_no_meta",
                "object": "event",
                "type": "checkout.session.completed",
                "data": {"object": {"id": "cs_x", "object": "checkout.session"}},
            },
            separators=(",", ":"),
        )
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))

        assert event.purchase_id is None
        # Aun sin metadatos, la sesion permite localizar la compra reservada.
        assert event.checkout_session_id == "cs_x"

    def test_malformed_purchase_id_is_ignored_not_fatal(
        self, gateway: StripePaymentGateway
    ) -> None:
        payload = checkout_completed_payload("no-soy-un-uuid")
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))
        assert event.purchase_id is None

    def test_expanded_payment_intent_object_is_reduced_to_its_id(
        self, gateway: StripePaymentGateway
    ) -> None:
        payload = json.dumps(
            {
                "id": "evt_expanded",
                "object": "event",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_y",
                        "object": "checkout.session",
                        "payment_intent": {"id": "pi_expanded", "object": "payment_intent"},
                        "metadata": {},
                    }
                },
            },
            separators=(",", ":"),
        )
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))
        assert event.payment_intent_id == "pi_expanded"


def signed_event(event_type: str, obj: dict[str, object], *, created: int = 1_780_000_000) -> str:
    return json.dumps(
        {
            "id": f"evt_{event_type}",
            "object": "event",
            "type": event_type,
            "created": created,
            "data": {"object": obj},
        },
        separators=(",", ":"),
    )


def invoice(**overrides: object) -> dict[str, object]:
    """Factura de la recarga tal como la envian las versiones recientes de la API."""
    obj: dict[str, object] = {
        "id": "in_test_1",
        "object": "invoice",
        "customer": "cus_test_1",
        "amount_paid": 1800,
        "currency": "eur",
        "period_end": 1_700_000_000,  # periodo ANTERIOR: no debe usarse
        "parent": {
            "type": "subscription_details",
            "subscription_details": {"subscription": "sub_test_1"},
        },
        "lines": {"data": [{"period": {"start": 1_780_000_000, "end": 1_782_592_000}}]},
    }
    obj.update(overrides)
    return obj


class TestSubscriptionEvents:
    def test_invoice_paid_carries_what_the_topup_needs(self, gateway: StripePaymentGateway) -> None:
        payload = signed_event("invoice.paid", invoice())
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))

        assert event.type is PaymentEventType.INVOICE_PAID
        assert event.customer_id == "cus_test_1"
        assert event.subscription_id == "sub_test_1"
        assert event.invoice_id == "in_test_1"
        assert event.amount_cents == 1800
        assert event.currency == "EUR"
        assert event.period_end == datetime.fromtimestamp(1_782_592_000, tz=UTC)
        assert event.occurred_at == datetime.fromtimestamp(1_780_000_000, tz=UTC)
        assert event.purchase_id is None

    def test_legacy_invoice_subscription_field_is_also_read(
        self, gateway: StripePaymentGateway
    ) -> None:
        payload = signed_event("invoice.paid", invoice(parent=None, subscription="sub_legacy"))
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))
        assert event.subscription_id == "sub_legacy"

    def test_invoice_not_from_a_subscription_is_ignored(
        self, gateway: StripePaymentGateway
    ) -> None:
        payload = signed_event("invoice.paid", invoice(parent=None))
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))
        assert event.type is PaymentEventType.IGNORED

    def test_invoice_payment_failed(self, gateway: StripePaymentGateway) -> None:
        payload = signed_event("invoice.payment_failed", invoice(amount_paid=0))
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))
        assert event.type is PaymentEventType.INVOICE_PAYMENT_FAILED
        assert event.customer_id == "cus_test_1"

    @pytest.mark.parametrize(
        ("raw_status", "expected"),
        [
            ("incomplete", SubscriptionStatus.PENDING),
            ("active", SubscriptionStatus.ACTIVE),
            ("past_due", SubscriptionStatus.PAST_DUE),
            ("unpaid", SubscriptionStatus.PAST_DUE),
            ("canceled", SubscriptionStatus.CANCELED),
            ("incomplete_expired", SubscriptionStatus.CANCELED),
        ],
    )
    def test_subscription_status_is_translated(
        self, gateway: StripePaymentGateway, raw_status: str, expected: SubscriptionStatus
    ) -> None:
        obj = {
            "id": "sub_test_1",
            "object": "subscription",
            "customer": "cus_test_1",
            "status": raw_status,
            "items": {"data": [{"current_period_end": 1_782_592_000}]},
        }
        payload = signed_event("customer.subscription.updated", obj)
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))

        assert event.type is PaymentEventType.SUBSCRIPTION_UPDATED
        assert event.subscription_status is expected
        assert event.subscription_id == "sub_test_1"
        # Las versiones recientes llevan el fin de periodo en cada item.
        assert event.period_end == datetime.fromtimestamp(1_782_592_000, tz=UTC)

    def test_deleted_subscription_is_canceled(self, gateway: StripePaymentGateway) -> None:
        obj = {"id": "sub_1", "object": "subscription", "customer": "cus_1", "status": "active"}
        payload = signed_event("customer.subscription.deleted", obj)
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))
        assert event.subscription_status is SubscriptionStatus.CANCELED

    def test_subscription_checkout_is_not_confused_with_a_purchase(
        self, gateway: StripePaymentGateway
    ) -> None:
        obj = {
            "id": "cs_sub_1",
            "object": "checkout.session",
            "mode": "subscription",
            "customer": "cus_test_1",
            "subscription": "sub_test_1",
            "metadata": {"professional_id": str(uuid4())},
        }
        payload = signed_event("checkout.session.completed", obj)
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))

        assert event.type is PaymentEventType.SUBSCRIPTION_CHECKOUT_COMPLETED
        assert event.customer_id == "cus_test_1"
        assert event.subscription_id == "sub_test_1"

    def test_expired_subscription_checkout_is_ignored(self, gateway: StripePaymentGateway) -> None:
        obj = {"id": "cs_sub_1", "object": "checkout.session", "mode": "subscription"}
        payload = signed_event("checkout.session.expired", obj)
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))
        assert event.type is PaymentEventType.IGNORED

    @pytest.mark.parametrize("raw_type", ["payment_intent.payment_failed", "charge.refunded"])
    def test_payment_events_without_a_purchase_are_ignored(
        self, gateway: StripePaymentGateway, raw_type: str
    ) -> None:
        """El adeudo fallido de una recarga no es el fallo de una compra inexistente."""
        obj = {"id": "pi_1", "object": "payment_intent", "metadata": {}}
        payload = signed_event(raw_type, obj)
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))
        assert event.type is PaymentEventType.IGNORED


class TestWebhookSecurity:
    def test_forged_signature_is_rejected(self, gateway: StripePaymentGateway) -> None:
        payload = checkout_completed_payload(str(uuid4()))
        with pytest.raises(AuthenticationError):
            gateway.parse_webhook_event(payload.encode(), "t=1,v1=deadbeef")

    def test_signature_from_a_different_secret_is_rejected(
        self, gateway: StripePaymentGateway
    ) -> None:
        payload = checkout_completed_payload(str(uuid4()))
        with pytest.raises(AuthenticationError):
            gateway.parse_webhook_event(payload.encode(), sign(payload, secret="whsec_otro"))

    def test_tampered_payload_is_rejected(self, gateway: StripePaymentGateway) -> None:
        """Firmar un payload y enviar otro no debe colar."""
        signed = checkout_completed_payload(str(uuid4()), event_id="evt_original")
        tampered = checkout_completed_payload(str(uuid4()), event_id="evt_manipulado")

        with pytest.raises(AuthenticationError):
            gateway.parse_webhook_event(tampered.encode(), sign(signed))

    def test_stale_timestamp_is_rejected(self, gateway: StripePaymentGateway) -> None:
        """Un evento firmado hace horas es un intento de replay."""
        payload = checkout_completed_payload(str(uuid4()))
        old = int(time.time()) - 60 * 60 * 24

        with pytest.raises(AuthenticationError):
            gateway.parse_webhook_event(payload.encode(), sign(payload, timestamp=old))

    def test_missing_signature_header_is_rejected(self, gateway: StripePaymentGateway) -> None:
        payload = checkout_completed_payload(str(uuid4()))
        with pytest.raises(AuthenticationError):
            gateway.parse_webhook_event(payload.encode(), "")

    def test_non_json_payload_is_rejected(self, gateway: StripePaymentGateway) -> None:
        with pytest.raises(AuthenticationError):
            gateway.parse_webhook_event(b"<html>no json</html>", sign("<html>no json</html>"))


class TestConfigurationGuards:
    def test_parsing_without_a_webhook_secret_is_refused(self) -> None:
        """Sin secreto no se puede verificar nada: mejor fallar que aceptar."""
        from app.domain.exceptions import DomainError

        gateway = StripePaymentGateway(secret_key="sk_test_fake", webhook_secret="")
        payload = checkout_completed_payload(str(uuid4()))

        with pytest.raises(DomainError):
            gateway.parse_webhook_event(payload.encode(), sign(payload))

    async def test_checkout_without_a_secret_key_raises_a_gateway_error(self) -> None:
        from app.application.ports import CheckoutRequest
        from app.domain.exceptions import PaymentGatewayError
        from app.domain.value_objects import Money

        gateway = StripePaymentGateway(secret_key="", webhook_secret=WEBHOOK_SECRET)
        request = CheckoutRequest(
            purchase_id=uuid4(),
            lead_id=uuid4(),
            professional_id=uuid4(),
            amount=Money(500, "EUR"),
            product_name="Carpinteria - Madrid",
            product_description="Reparar armario",
            customer_email=None,
            success_url="https://reformahub.test/es/mis-contactos",
            cancel_url="https://reformahub.test/es/proyectos/1",
        )
        with pytest.raises(PaymentGatewayError) as exc:
            await gateway.create_checkout_session(request)
        assert exc.value.code == "PAYMENT_GATEWAY_ERROR"
        assert exc.value.status == 503

    async def test_creating_a_monthly_price_without_a_secret_key_is_a_gateway_error(
        self,
    ) -> None:
        from app.domain.exceptions import PaymentGatewayError
        from app.domain.value_objects import Money

        gateway = StripePaymentGateway(secret_key="", webhook_secret=WEBHOOK_SECRET)
        with pytest.raises(PaymentGatewayError):
            await gateway.create_recurring_price(
                amount=Money(2000, "EUR"), product_name="Mensualidad"
            )
