from __future__ import annotations

import json
from uuid import UUID

from app.application.ports import (
    CheckoutRequest,
    CheckoutSession,
    PaymentEvent,
    PaymentEventType,
    PaymentPort,
)
from app.domain.exceptions import AuthenticationError

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
        )

    async def expire_checkout_session(self, session_id: str) -> None:
        self.expired_sessions.append(session_id)

    # ------------------------- helpers para los tests --------------------

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
