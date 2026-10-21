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
import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.ports import (
    BillingDetails,
    CustomerRequest,
    PaymentEventType,
    SubscriptionCheckoutRequest,
)
from app.domain.exceptions import AuthenticationError
from app.domain.models import SubscriptionStatus
from app.domain.value_objects import TaxId
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

    def test_invoice_paid_carries_what_is_stored_of_the_invoice(
        self, gateway: StripePaymentGateway
    ) -> None:
        payload = signed_event(
            "invoice.paid",
            invoice(
                number="VAR-0001",
                hosted_invoice_url="https://invoice.stripe.com/i/acct_1/test_1",
                invoice_pdf="https://pay.stripe.com/invoice/acct_1/test_1/pdf",
                total_taxes=[
                    {"amount": 312, "tax_behavior": "inclusive"},
                    {"amount": 1, "tax_behavior": "inclusive"},
                ],
                status_transitions={"finalized_at": 1_779_999_000, "paid_at": 1_780_000_000},
            ),
        )
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))

        assert event.invoice_number == "VAR-0001"
        assert event.invoice_url == "https://invoice.stripe.com/i/acct_1/test_1"
        assert event.invoice_pdf_url == "https://pay.stripe.com/invoice/acct_1/test_1/pdf"
        assert event.tax_cents == 313
        assert event.issued_at == datetime.fromtimestamp(1_779_999_000, tz=UTC)

    def test_invoice_without_taxes_or_finalization_date(
        self, gateway: StripePaymentGateway
    ) -> None:
        payload = signed_event("invoice.paid", invoice(total_taxes=[], created=1_779_000_000))
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))

        assert event.tax_cents is None
        assert event.issued_at == datetime.fromtimestamp(1_779_000_000, tz=UTC)

    def test_invoice_total_is_kept_apart_from_what_was_charged(
        self, gateway: StripePaymentGateway
    ) -> None:
        # Saldo a favor del cliente en Stripe: la factura es de 18 EUR, se cobran 2.
        payload = signed_event(
            "invoice.paid",
            invoice(total=1800, amount_paid=200, total_taxes=[{"amount": 312}]),
        )
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))

        assert event.invoice_total_cents == 1800
        assert event.amount_cents == 200, "se abona lo cobrado"
        assert event.tax_cents == 312

    def test_legacy_invoice_tax_field_is_also_read(self, gateway: StripePaymentGateway) -> None:
        payload = signed_event("invoice.paid", invoice(tax=312))
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))
        assert event.tax_cents == 312

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

    def test_a_secret_mismatch_is_logged_as_a_warning(
        self, gateway: StripePaymentGateway, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Con el secreto equivocado se rechaza cada pago: tiene que verse en los logs.
        payload = checkout_completed_payload(str(uuid4()))
        with caplog.at_level(logging.WARNING), pytest.raises(AuthenticationError):
            gateway.parse_webhook_event(payload.encode(), sign(payload, secret="whsec_otro"))
        warning = next(r for r in caplog.records if r.levelno == logging.WARNING)
        assert "STRIPE_WEBHOOK_SECRET" in warning.getMessage()
        assert payload not in warning.getMessage()

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


class TestInvoiceRefundTarget:
    """El reembolso del primer cobro (rechazo del alta) sale del objeto real del SDK."""

    @staticmethod
    def invoice(payments: list[dict[str, object]]) -> object:
        import stripe

        return stripe.Invoice.construct_from(
            {
                "id": "in_1",
                "object": "invoice",
                "payments": {"object": "list", "data": payments},
            },
            "sk_test_x",
        )

    def test_uses_the_payment_intent_of_the_paid_payment(self) -> None:
        from app.infrastructure.adapters.payments.stripe_adapter import _paid_invoice_payment

        invoice = self.invoice(
            [
                {
                    "object": "invoice_payment",
                    "status": "canceled",
                    "payment": {"type": "payment_intent", "payment_intent": "pi_old"},
                },
                {
                    "object": "invoice_payment",
                    "status": "paid",
                    "payment": {"type": "payment_intent", "payment_intent": "pi_paid"},
                },
            ]
        )
        assert _paid_invoice_payment(invoice) == {"payment_intent": "pi_paid"}

    def test_falls_back_to_the_charge(self) -> None:
        from app.infrastructure.adapters.payments.stripe_adapter import _paid_invoice_payment

        invoice = self.invoice(
            [
                {
                    "object": "invoice_payment",
                    "status": "paid",
                    "payment": {"type": "charge", "charge": "ch_1"},
                }
            ]
        )
        assert _paid_invoice_payment(invoice) == {"charge": "ch_1"}

    def test_nothing_to_refund_without_a_paid_payment(self) -> None:
        from app.infrastructure.adapters.payments.stripe_adapter import _paid_invoice_payment

        assert _paid_invoice_payment(self.invoice([])) is None


class ScriptedHttpClient:
    """Cliente HTTP del SDK que responde con JSON fijo, sin red.

    Pasa por el `StripeClient` real: la traduccion de un 400 de Stripe a
    `InvalidRequestError` (con su `code`) la hace el propio SDK, igual que en produccion.
    """

    def __init__(self, responses: dict[tuple[str, str], tuple[int, dict[str, object]]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []
        self.urls: list[str] = []
        self.bodies: dict[tuple[str, str], str] = {}

    def build(self) -> object:
        import stripe

        scripted = self

        class _Client(stripe.HTTPClient):
            name = "scripted"

            def request(  # type: ignore[override]
                self, method: str, url: str, headers: object, post_data: object = None, **_: object
            ) -> tuple[str, int, dict[str, str]]:
                path = url.split("api.stripe.com", 1)[1].split("?", 1)[0]
                scripted.calls.append((method.upper(), path))
                scripted.urls.append(url)
                scripted.bodies[(method.upper(), path)] = str(post_data or "")
                status, body = scripted.responses[(method.upper(), path)]
                return json.dumps(body), status, {"request-id": "req_test"}

            def close(self) -> None:
                return None

        return _Client()


PAID_INVOICE = {
    "id": "in_first",
    "object": "invoice",
    "payments": {
        "object": "list",
        "data": [
            {
                "object": "invoice_payment",
                "status": "paid",
                "payment": {"type": "payment_intent", "payment_intent": "pi_first"},
            }
        ],
    },
}


def gateway_with(http: ScriptedHttpClient) -> StripePaymentGateway:
    import stripe

    gateway = StripePaymentGateway(secret_key="sk_test_fake", webhook_secret=WEBHOOK_SECRET)
    gateway._client = stripe.StripeClient(
        "sk_test_fake",
        http_client=http.build(),
        max_network_retries=0,  # type: ignore[arg-type]
    )
    return gateway


class TestInvoiceRefundRetries:
    async def test_refunds_the_paid_payment_intent(self) -> None:
        http = ScriptedHttpClient(
            {
                ("GET", "/v1/invoices/in_first"): (200, PAID_INVOICE),
                ("POST", "/v1/refunds"): (200, {"id": "re_1", "object": "refund"}),
            }
        )
        await gateway_with(http).refund_invoice(invoice_id="in_first", idempotency_key="k")
        assert ("POST", "/v1/refunds") in http.calls

    async def test_an_already_refunded_charge_counts_as_done(self) -> None:
        # Pasadas 24 h Stripe olvida la clave de idempotencia y el reintento de un
        # reembolso hecho responde con este error: no debe bloquear el rechazo.
        http = ScriptedHttpClient(
            {
                ("GET", "/v1/invoices/in_first"): (200, PAID_INVOICE),
                ("POST", "/v1/refunds"): (
                    400,
                    {
                        "error": {
                            "type": "invalid_request_error",
                            "code": "charge_already_refunded",
                            "message": "Charge ch_1 has already been refunded.",
                        }
                    },
                ),
            }
        )
        await gateway_with(http).refund_invoice(invoice_id="in_first", idempotency_key="k")

    async def test_other_refund_errors_still_fail(self) -> None:
        from app.domain.exceptions import PaymentGatewayError

        http = ScriptedHttpClient(
            {
                ("GET", "/v1/invoices/in_first"): (200, PAID_INVOICE),
                ("POST", "/v1/refunds"): (
                    400,
                    {
                        "error": {
                            "type": "invalid_request_error",
                            "code": "charge_disputed",
                            "message": "Charge ch_1 has been charged back.",
                        }
                    },
                ),
            }
        )
        with pytest.raises(PaymentGatewayError):
            await gateway_with(http).refund_invoice(invoice_id="in_first", idempotency_key="k")


def subscription_list(*statuses: str) -> dict[str, object]:
    return {
        "object": "list",
        "url": "/v1/subscriptions",
        "has_more": False,
        "data": [
            {"id": f"sub_{index}", "object": "subscription", "status": status}
            for index, status in enumerate(statuses)
        ],
    }


class TestLiveSubscriptionCheck:
    """Antes de abrir otro checkout se pregunta a Stripe: el webhook puede ir tarde."""

    @pytest.mark.parametrize("status", ["active", "trialing", "past_due", "unpaid", "paused"])
    async def test_a_subscription_still_charging_counts_as_live(self, status: str) -> None:
        http = ScriptedHttpClient(
            {("GET", "/v1/subscriptions"): (200, subscription_list("canceled", status))}
        )
        assert await gateway_with(http).has_live_subscription("cus_1")
        # Por cliente y en todos los estados: el filtro por defecto omite las pausadas.
        assert "customer=cus_1" in http.urls[0]
        assert "status=all" in http.urls[0]

    @pytest.mark.parametrize("statuses", [(), ("canceled",), ("incomplete", "incomplete_expired")])
    async def test_ended_or_never_paid_subscriptions_do_not_block_a_new_one(
        self, statuses: tuple[str, ...]
    ) -> None:
        http = ScriptedHttpClient(
            {("GET", "/v1/subscriptions"): (200, subscription_list(*statuses))}
        )
        assert not await gateway_with(http).has_live_subscription("cus_1")

    async def test_a_gateway_error_is_not_read_as_no_subscription(self) -> None:
        from app.domain.exceptions import PaymentGatewayError

        http = ScriptedHttpClient(
            {
                ("GET", "/v1/subscriptions"): (
                    500,
                    {"error": {"type": "api_error", "message": "Stripe is down"}},
                )
            }
        )
        with pytest.raises(PaymentGatewayError):
            await gateway_with(http).has_live_subscription("cus_1")


def dispute_object(status: str = "needs_response", **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "dp_test_1",
        "object": "dispute",
        "amount": 1800,
        "currency": "eur",
        "charge": "ch_test_1",
        "payment_intent": "pi_test_1",
        "status": status,
        "reason": "general",
        "metadata": {},
    }
    data.update(overrides)
    return data


class TestDisputeEvents:
    """Adeudo SEPA devuelto o disputa de tarjeta, con el objeto real del SDK."""

    @pytest.mark.parametrize(
        ("raw_type", "status", "expected"),
        [
            ("charge.dispute.created", "needs_response", PaymentEventType.CHARGE_DISPUTED),
            # SEPA: la devolucion llega ya perdida, no se puede contestar.
            ("charge.dispute.created", "lost", PaymentEventType.CHARGE_DISPUTED),
            # Consulta sin retirada de fondos: no toca el saldo.
            ("charge.dispute.created", "warning_needs_response", PaymentEventType.IGNORED),
            ("charge.dispute.funds_withdrawn", "needs_response", PaymentEventType.CHARGE_DISPUTED),
            ("charge.dispute.funds_reinstated", "won", PaymentEventType.DISPUTE_WON),
            ("charge.dispute.closed", "won", PaymentEventType.DISPUTE_WON),
            ("charge.dispute.closed", "lost", PaymentEventType.IGNORED),
            ("charge.dispute.closed", "warning_closed", PaymentEventType.IGNORED),
        ],
    )
    def test_classification(
        self,
        gateway: StripePaymentGateway,
        raw_type: str,
        status: str,
        expected: PaymentEventType,
    ) -> None:
        payload = signed_event(raw_type, dispute_object(status))
        assert gateway.parse_webhook_event(payload.encode(), sign(payload)).type is expected

    def test_carries_the_dispute_the_charge_and_the_amount(
        self, gateway: StripePaymentGateway
    ) -> None:
        payload = signed_event("charge.dispute.created", dispute_object())
        event = gateway.parse_webhook_event(payload.encode(), sign(payload))

        assert event.dispute_id == "dp_test_1"
        assert event.charge_id == "ch_test_1"
        assert event.amount_cents == 1800
        assert event.currency == "EUR"
        assert event.purchase_id is None


class TestDescribeCharge:
    async def test_a_top_up_charge_belongs_to_the_customer(self) -> None:
        http = ScriptedHttpClient(
            {
                ("GET", "/v1/charges/ch_topup"): (
                    200,
                    {
                        "id": "ch_topup",
                        "object": "charge",
                        "customer": "cus_test_1",
                        "metadata": {},
                        "payment_intent": {
                            "id": "pi_topup",
                            "object": "payment_intent",
                            "metadata": {},
                        },
                    },
                )
            }
        )
        owner = await gateway_with(http).describe_charge("ch_topup")
        assert owner.customer_id == "cus_test_1"
        assert owner.purchase_id is None

    async def test_a_contact_purchase_is_recognised_by_its_metadata(self) -> None:
        purchase_id = uuid4()
        http = ScriptedHttpClient(
            {
                ("GET", "/v1/charges/ch_lead"): (
                    200,
                    {
                        "id": "ch_lead",
                        "object": "charge",
                        "customer": None,
                        "metadata": {},
                        "payment_intent": {
                            "id": "pi_lead",
                            "object": "payment_intent",
                            "metadata": {"purchase_id": str(purchase_id)},
                        },
                    },
                )
            }
        )
        owner = await gateway_with(http).describe_charge("ch_lead")
        assert owner.purchase_id == purchase_id
        assert owner.customer_id is None

    async def test_a_gateway_error_is_translated(self) -> None:
        from app.domain.exceptions import PaymentGatewayError

        http = ScriptedHttpClient(
            {
                ("GET", "/v1/charges/ch_x"): (
                    404,
                    {"error": {"type": "invalid_request_error", "message": "No such charge"}},
                )
            }
        )
        with pytest.raises(PaymentGatewayError):
            await gateway_with(http).describe_charge("ch_x")


def form(body: str) -> dict[str, list[str]]:
    from urllib.parse import parse_qs

    return parse_qs(body)


CUSTOMER = {"id": "cus_1", "object": "customer"}


def tax_id_list(*values: str) -> dict[str, object]:
    return {
        "object": "list",
        "url": "/v1/customers/cus_1/tax_ids",
        "has_more": False,
        "data": [
            {"id": f"txi_{index}", "object": "tax_id", "type": "es_cif", "value": value}
            for index, value in enumerate(values)
        ],
    }


def billing(**overrides: object) -> BillingDetails:
    values: dict[str, object] = {
        "name": "Juan Lopez Garcia",
        "tax_id": TaxId("12345678Z"),
        "address": "Calle Mayor 1, 28013 Madrid",
        **overrides,
    }
    return BillingDetails(**values)  # type: ignore[arg-type]


class TestCustomerBillingDetails:
    """Lo que Stripe imprime en la factura sale del cliente: nombre, NIF y domicilio."""

    async def test_a_new_customer_carries_name_tax_id_and_address(self) -> None:
        http = ScriptedHttpClient({("POST", "/v1/customers"): (200, CUSTOMER)})
        customer_id = await gateway_with(http).create_customer(
            CustomerRequest(professional_id=uuid4(), email="pro@example.com", billing=billing())
        )

        assert customer_id == "cus_1"
        sent = form(http.bodies[("POST", "/v1/customers")])
        assert sent["name"] == ["Juan Lopez Garcia"]
        assert sent["address[line1]"] == ["Calle Mayor 1, 28013 Madrid"]
        assert sent["address[country]"] == ["ES"]
        assert sent["tax_id_data[0][type]"] == ["es_cif"]
        assert sent["tax_id_data[0][value]"] == ["12345678Z"]

    async def test_without_fiscal_data_only_the_name_is_sent(self) -> None:
        http = ScriptedHttpClient({("POST", "/v1/customers"): (200, CUSTOMER)})
        await gateway_with(http).create_customer(
            CustomerRequest(
                professional_id=uuid4(),
                email="pro@example.com",
                billing=billing(tax_id=None, address=None),
            )
        )

        sent = form(http.bodies[("POST", "/v1/customers")])
        assert sent["name"] == ["Juan Lopez Garcia"]
        assert not any(key.startswith(("address", "tax_id_data")) for key in sent)

    async def test_update_replaces_an_old_tax_id(self) -> None:
        http = ScriptedHttpClient(
            {
                ("POST", "/v1/customers/cus_1"): (200, CUSTOMER),
                ("GET", "/v1/customers/cus_1/tax_ids"): (200, tax_id_list("X1234567L")),
                ("DELETE", "/v1/customers/cus_1/tax_ids/txi_0"): (
                    200,
                    {"id": "txi_0", "object": "tax_id", "deleted": True},
                ),
                ("POST", "/v1/customers/cus_1/tax_ids"): (
                    200,
                    {"id": "txi_1", "object": "tax_id", "type": "es_cif", "value": "12345678Z"},
                ),
            }
        )
        await gateway_with(http).update_customer_billing("cus_1", billing())

        assert form(http.bodies[("POST", "/v1/customers/cus_1")])["address[line1]"] == [
            "Calle Mayor 1, 28013 Madrid"
        ]
        assert ("DELETE", "/v1/customers/cus_1/tax_ids/txi_0") in http.calls
        assert form(http.bodies[("POST", "/v1/customers/cus_1/tax_ids")])["value"] == ["12345678Z"]

    async def test_update_keeps_a_tax_id_that_did_not_change(self) -> None:
        http = ScriptedHttpClient(
            {
                ("POST", "/v1/customers/cus_1"): (200, CUSTOMER),
                ("GET", "/v1/customers/cus_1/tax_ids"): (200, tax_id_list("12345678Z")),
            }
        )
        await gateway_with(http).update_customer_billing("cus_1", billing())

        assert http.calls == [
            ("POST", "/v1/customers/cus_1"),
            ("GET", "/v1/customers/cus_1/tax_ids"),
        ]

    async def test_a_rejected_tax_id_is_a_gateway_error(self) -> None:
        from app.domain.exceptions import PaymentGatewayError

        http = ScriptedHttpClient(
            {
                ("POST", "/v1/customers/cus_1"): (200, CUSTOMER),
                ("GET", "/v1/customers/cus_1/tax_ids"): (200, tax_id_list()),
                ("POST", "/v1/customers/cus_1/tax_ids"): (
                    400,
                    {
                        "error": {
                            "type": "invalid_request_error",
                            "code": "tax_id_invalid",
                            "message": "Invalid value for es_cif.",
                        }
                    },
                ),
            }
        )
        with pytest.raises(PaymentGatewayError):
            await gateway_with(http).update_customer_billing("cus_1", billing())


def tax_rate(rate_id: str, *, percentage: int = 21, managed: bool = True) -> dict[str, object]:
    return {
        "id": rate_id,
        "object": "tax_rate",
        "percentage": percentage,
        "inclusive": True,
        "active": True,
        "metadata": {"managed_by": "reforma-hub"} if managed else {},
    }


def tax_rate_list(*rates: dict[str, object]) -> dict[str, object]:
    return {"object": "list", "url": "/v1/tax_rates", "has_more": False, "data": list(rates)}


class TestSubscriptionCheckoutVat:
    """El 21 % es una constante del dominio; el id del tipo en Stripe lo resuelve el adaptador."""

    def _request(self) -> SubscriptionCheckoutRequest:
        return SubscriptionCheckoutRequest(
            professional_id=uuid4(),
            customer_id="cus_1",
            price_id="price_1",
            success_url="https://reformahub.test/es/suscripcion?status=success",
            cancel_url="https://reformahub.test/es/suscripcion?status=cancelled",
        )

    def _http(self, *rates: dict[str, object]) -> ScriptedHttpClient:
        session = {
            "id": "cs_1",
            "object": "checkout.session",
            "url": "https://checkout.stripe.com/c/pay/cs_1",
            "expires_at": 1_780_000_000,
        }
        return ScriptedHttpClient(
            {
                ("GET", "/v1/tax_rates"): (200, tax_rate_list(*rates)),
                ("POST", "/v1/tax_rates"): (200, tax_rate("txr_new")),
                ("POST", "/v1/checkout/sessions"): (200, session),
            }
        )

    async def test_reuses_the_vat_rate_the_app_already_created(self) -> None:
        # Un tipo ajeno (sin la marca) o de otro porcentaje no se confunde con el nuestro.
        http = self._http(
            tax_rate("txr_other", managed=False),
            tax_rate("txr_reduced", percentage=10),
            tax_rate("txr_iva21"),
        )
        await gateway_with(http).create_subscription_checkout(self._request())

        sent = form(http.bodies[("POST", "/v1/checkout/sessions")])
        assert sent["line_items[0][price]"] == ["price_1"]
        assert sent["line_items[0][tax_rates][0]"] == ["txr_iva21"]
        assert ("POST", "/v1/tax_rates") not in http.calls

    async def test_creates_the_vat_rate_the_first_time(self) -> None:
        http = self._http(tax_rate("txr_other", managed=False))
        await gateway_with(http).create_subscription_checkout(self._request())

        created = form(http.bodies[("POST", "/v1/tax_rates")])
        assert created["percentage"] == ["21"]
        assert created["inclusive"] == ["true"]
        assert created["country"] == ["ES"]
        assert created["metadata[managed_by]"] == ["reforma-hub"]
        sent = form(http.bodies[("POST", "/v1/checkout/sessions")])
        assert sent["line_items[0][tax_rates][0]"] == ["txr_new"]

    async def test_the_vat_rate_is_looked_up_once_per_process(self) -> None:
        http = self._http(tax_rate("txr_iva21"))
        gateway = gateway_with(http)

        await gateway.create_subscription_checkout(self._request())
        await gateway.create_subscription_checkout(self._request())

        assert http.calls.count(("GET", "/v1/tax_rates")) == 1

    async def test_no_checkout_if_the_vat_rate_cannot_be_resolved(self) -> None:
        from app.domain.exceptions import PaymentGatewayError

        http = ScriptedHttpClient(
            {
                ("GET", "/v1/tax_rates"): (
                    500,
                    {"error": {"type": "api_error", "message": "Stripe is down"}},
                )
            }
        )
        with pytest.raises(PaymentGatewayError):
            await gateway_with(http).create_subscription_checkout(self._request())
        assert ("POST", "/v1/checkout/sessions") not in http.calls
