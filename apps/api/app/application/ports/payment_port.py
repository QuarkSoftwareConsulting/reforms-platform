"""Puerto de la pasarela de pago.

Modela solo lo que el negocio necesita: crear una sesion de checkout y entender el
resultado de un evento entrante. Nada de tipos de Stripe cruza esta frontera.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    """Sesion de pago creada en la pasarela."""

    id: str
    url: str
    expires_at_epoch: int | None = None


@dataclass(frozen=True, slots=True)
class CheckoutRequest:
    purchase_id: UUID
    lead_id: UUID
    professional_id: UUID
    amount: Money
    product_name: str
    product_description: str
    customer_email: str | None
    success_url: str
    cancel_url: str
    locale: str = "es"
    expires_in_minutes: int = 30


class PaymentEventType(StrEnum):
    CHECKOUT_COMPLETED = "checkout_completed"
    CHECKOUT_EXPIRED = "checkout_expired"
    PAYMENT_FAILED = "payment_failed"
    REFUNDED = "refunded"
    IGNORED = "ignored"


@dataclass(frozen=True, slots=True)
class PaymentEvent:
    """Evento de la pasarela ya normalizado al lenguaje del dominio."""

    id: str
    type: PaymentEventType
    raw_type: str
    purchase_id: UUID | None
    checkout_session_id: str | None
    payment_intent_id: str | None
    amount_cents: int | None
    currency: str | None
    payload: dict[str, object]


class PaymentPort(ABC):
    @abstractmethod
    async def create_checkout_session(self, request: CheckoutRequest) -> CheckoutSession: ...

    @abstractmethod
    def parse_webhook_event(self, payload: bytes, signature: str) -> PaymentEvent:
        """Verifica la firma y traduce el evento crudo a un `PaymentEvent`.

        Lanza `AuthenticationError` si la firma no es valida.
        """

    @abstractmethod
    async def expire_checkout_session(self, session_id: str) -> None:
        """Cierra en la pasarela una sesion cuya reserva hemos liberado."""
