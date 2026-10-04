from __future__ import annotations

import asyncio
import json
from datetime import datetime
from uuid import UUID

from app.application.ports import (
    ChargeOwner,
    CheckoutRequest,
    CheckoutSession,
    CustomerRequest,
    PaymentEvent,
    PaymentEventType,
    PaymentPort,
    SubscriptionCheckoutRequest,
)
from app.domain.exceptions import AuthenticationError, PaymentGatewayError
from app.domain.models import SubscriptionStatus
from app.domain.value_objects import Money

VALID_SIGNATURE = "valid-signature"


class FakePaymentGateway(PaymentPort):
    """Pasarela simulada.

    Registra las sesiones creadas y permite fabricar eventos de webhook a partir
    de ellas, para poder probar confirmaciones, caducidades y reintentos.
    """

    def __init__(self, *, fail_on_create: bool = False) -> None:
        self.requests: list[CheckoutRequest] = []
        self.sessions: dict[str, CheckoutRequest] = {}
        self.expired_sessions: list[str] = []
        self.customers: dict[str, CustomerRequest] = {}
        self.subscription_checkouts: list[SubscriptionCheckoutRequest] = []
        self.portal_sessions: list[str] = []
        self.created_prices: dict[str, Money] = {}
        # Como la pasarela real: una clave de idempotencia repetida no reembolsa otra vez.
        self.refunds: dict[str, str] = {}
        self.canceled_subscriptions: set[str] = set()
        self.fail_on_refund = False
        # De quien es cada cargo, para las devoluciones (la disputa no lo trae).
        self.charge_owners: dict[str, ChargeOwner] = {}
        self.fail_on_describe = False
        self.fail_on_create = fail_on_create
        self._counter = 0

    async def create_checkout_session(self, request: CheckoutRequest) -> CheckoutSession:
        if self.fail_on_create:
            raise RuntimeError("La pasarela no responde")
        self._counter += 1
        session_id = f"cs_test_{self._counter:04d}"
        self.requests.append(request)
        self.sessions[session_id] = request
        return CheckoutSession(id=session_id, url=f"https://checkout.test/{session_id}")

    def parse_webhook_event(self, payload: bytes, signature: str) -> PaymentEvent:
        if signature != VALID_SIGNATURE:
            raise AuthenticationError("Firma de webhook invalida")
        data = json.loads(payload)
        return PaymentEvent(
            id=data["id"],
            type=PaymentEventType(data["type"]),
            raw_type=data.get("raw_type", data["type"]),
            purchase_id=UUID(data["purchase_id"]) if data.get("purchase_id") else None,
            checkout_session_id=data.get("checkout_session_id"),
            payment_intent_id=data.get("payment_intent_id"),
            amount_cents=data.get("amount_cents"),
            currency=data.get("currency"),
            payload=data,
            customer_id=data.get("customer_id"),
            subscription_id=data.get("subscription_id"),
            invoice_id=data.get("invoice_id"),
            subscription_status=(
                SubscriptionStatus(data["subscription_status"])
                if data.get("subscription_status")
                else None
            ),
            period_end=(
                datetime.fromisoformat(data["period_end"]) if data.get("period_end") else None
            ),
            occurred_at=(
                datetime.fromisoformat(data["occurred_at"]) if data.get("occurred_at") else None
            ),
            dispute_id=data.get("dispute_id"),
            charge_id=data.get("charge_id"),
        )

    async def describe_charge(self, charge_id: str) -> ChargeOwner:
        await asyncio.sleep(0)
        if self.fail_on_describe:
            raise PaymentGatewayError()
        return self.charge_owners.get(charge_id, ChargeOwner(customer_id=None, purchase_id=None))

    async def expire_checkout_session(self, session_id: str) -> None:
        self.expired_sessions.append(session_id)

    async def create_customer(self, request: CustomerRequest) -> str:
        if self.fail_on_create:
            raise RuntimeError("La pasarela no responde")
        customer_id = f"cus_test_{len(self.customers) + 1:04d}"
        self.customers[customer_id] = request
        return customer_id

    async def create_subscription_checkout(
        self, request: SubscriptionCheckoutRequest
    ) -> CheckoutSession:
        self._counter += 1
        session_id = f"cs_sub_{self._counter:04d}"
        self.subscription_checkouts.append(request)
        # El cliente va en la URL para que los tests HTTP puedan construir el
        # `invoice.paid` que enviaria Stripe sin tener que acceder al fake.
        return CheckoutSession(
            id=session_id,
            url=f"https://checkout.test/{session_id}?customer={request.customer_id}",
        )

    async def create_recurring_price(self, *, amount: Money, product_name: str) -> str:
        if self.fail_on_create:
            raise RuntimeError("La pasarela no responde")
        price_id = f"price_test_{len(self.created_prices) + 1:04d}"
        self.created_prices[price_id] = amount
        return price_id

    async def create_billing_portal_session(
        self, *, customer_id: str, return_url: str, locale: str = "es"
    ) -> str:
        self.portal_sessions.append(customer_id)
        return f"https://billing.test/{customer_id}"

    async def refund_invoice(self, *, invoice_id: str, idempotency_key: str) -> None:
        # Punto de cesion como el viaje de red a Stripe: sin el, rechazar corre de
        # forma atomica y la carrera con una aprobacion no se puede reproducir.
        await asyncio.sleep(0)
        if self.fail_on_refund:
            raise PaymentGatewayError("La pasarela no responde")
        self.refunds.setdefault(idempotency_key, invoice_id)

    async def cancel_subscription(self, subscription_id: str) -> None:
        await asyncio.sleep(0)
        self.canceled_subscriptions.add(subscription_id)

    # ------------------------- helpers para los tests --------------------

    @staticmethod
    def dispute_event_payload(
        *,
        event_id: str,
        event_type: PaymentEventType,
        dispute_id: str = "dp_1",
        charge_id: str = "ch_topup",
        amount_cents: int = 1800,
    ) -> bytes:
        return json.dumps(
            {
                "id": event_id,
                "type": event_type.value,
                "raw_type": f"stripe.{event_type.value}",
                "dispute_id": dispute_id,
                "charge_id": charge_id,
                "amount_cents": amount_cents,
                "currency": "EUR",
            }
        ).encode()

    @staticmethod
    def event_payload(
        *,
        event_id: str,
        event_type: PaymentEventType,
        purchase_id: UUID | None = None,
        checkout_session_id: str | None = None,
        payment_intent_id: str | None = "pi_test_0001",
        raw_type: str | None = None,
    ) -> bytes:
        return json.dumps(
            {
                "id": event_id,
                "type": event_type.value,
                "raw_type": raw_type or f"stripe.{event_type.value}",
                "purchase_id": str(purchase_id) if purchase_id else None,
                "checkout_session_id": checkout_session_id,
                "payment_intent_id": payment_intent_id,
            }
        ).encode()

    @staticmethod
    def subscription_event_payload(
        *,
        event_id: str,
        event_type: PaymentEventType,
        customer_id: str,
        subscription_id: str | None = "sub_test_0001",
        invoice_id: str | None = None,
        amount_cents: int | None = None,
        currency: str | None = "EUR",
        subscription_status: SubscriptionStatus | None = None,
        period_end: datetime | None = None,
        occurred_at: datetime | None = None,
    ) -> bytes:
        return json.dumps(
            {
                "id": event_id,
                "type": event_type.value,
                "raw_type": f"stripe.{event_type.value}",
                "customer_id": customer_id,
                "subscription_id": subscription_id,
                "invoice_id": invoice_id,
                "amount_cents": amount_cents,
                "currency": currency,
                "subscription_status": subscription_status.value if subscription_status else None,
                "period_end": period_end.isoformat() if period_end else None,
                "occurred_at": occurred_at.isoformat() if occurred_at else None,
            }
        ).encode()
