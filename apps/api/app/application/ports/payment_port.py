"""Puerto de la pasarela de pago.

Modela solo lo que el negocio necesita: cobrar un contacto, cobrar la recarga
mensual y entender el resultado de un evento entrante. Nada de tipos de Stripe
cruza esta frontera.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.domain.models import SubscriptionStatus
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


@dataclass(frozen=True, slots=True)
class CustomerRequest:
    """Alta del profesional como cliente de la pasarela (necesario para suscribirse)."""

    professional_id: UUID
    email: str
    name: str


@dataclass(frozen=True, slots=True)
class SubscriptionCheckoutRequest:
    """Checkout de la mensualidad. El importe lo fija `price_id` en la pasarela."""

    professional_id: UUID
    customer_id: str
    price_id: str
    success_url: str
    cancel_url: str
    locale: str = "es"


class PaymentEventType(StrEnum):
    # Compra de un contacto
    CHECKOUT_COMPLETED = "checkout_completed"
    CHECKOUT_EXPIRED = "checkout_expired"
    PAYMENT_FAILED = "payment_failed"
    REFUNDED = "refunded"
    # Recarga mensual
    SUBSCRIPTION_CHECKOUT_COMPLETED = "subscription_checkout_completed"
    INVOICE_PAID = "invoice_paid"
    INVOICE_PAYMENT_FAILED = "invoice_payment_failed"
    SUBSCRIPTION_UPDATED = "subscription_updated"
    # Devolucion de un cobro por el banco (adeudo SEPA devuelto o disputa de tarjeta)
    CHARGE_DISPUTED = "charge_disputed"
    DISPUTE_WON = "dispute_won"
    IGNORED = "ignored"

    @property
    def concerns_subscription(self) -> bool:
        return self in {
            PaymentEventType.SUBSCRIPTION_CHECKOUT_COMPLETED,
            PaymentEventType.INVOICE_PAID,
            PaymentEventType.INVOICE_PAYMENT_FAILED,
            PaymentEventType.SUBSCRIPTION_UPDATED,
        }

    @property
    def concerns_dispute(self) -> bool:
        return self in {PaymentEventType.CHARGE_DISPUTED, PaymentEventType.DISPUTE_WON}


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
    # Solo en eventos de la recarga mensual.
    customer_id: str | None = None
    subscription_id: str | None = None
    invoice_id: str | None = None
    subscription_status: SubscriptionStatus | None = None
    period_end: datetime | None = None
    occurred_at: datetime | None = None
    """Cuando ocurrio en la pasarela (no cuando llego): ordena eventos desordenados."""
    # Solo en devoluciones: la disputa (idempotencia del libro) y el cargo disputado.
    dispute_id: str | None = None
    charge_id: str | None = None


@dataclass(frozen=True, slots=True)
class ChargeOwner:
    """De quien es un cargo de la pasarela, para saber a que afecta su devolucion."""

    customer_id: str | None
    purchase_id: UUID | None
    """Solo si el cargo es la compra de un contacto (no la recarga)."""


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

    @abstractmethod
    async def create_customer(self, request: CustomerRequest) -> str:
        """Da de alta al profesional en la pasarela y devuelve su identificador."""

    @abstractmethod
    async def create_subscription_checkout(
        self, request: SubscriptionCheckoutRequest
    ) -> CheckoutSession:
        """Checkout para suscribirse a la recarga mensual (tarjeta o domiciliacion)."""

    @abstractmethod
    async def create_recurring_price(self, *, amount: Money, product_name: str) -> str:
        """Crea un precio mensual en la pasarela y devuelve su identificador.

        Los precios de la pasarela no se editan: cambiar la mensualidad es crear
        uno nuevo, y las suscripciones existentes siguen con el suyo.
        """

    @abstractmethod
    async def refund_invoice(self, *, invoice_id: str, idempotency_key: str) -> None:
        """Reembolsa integro el cobro de una factura de la recarga.

        Con la misma `idempotency_key` un reintento no reembolsa dos veces.
        """

    @abstractmethod
    async def cancel_subscription(self, subscription_id: str) -> None:
        """Cancela la recarga en el acto (no al final del periodo).

        Cancelar una suscripcion ya cancelada no es un error: el reintento es seguro.
        """

    @abstractmethod
    async def describe_charge(self, charge_id: str) -> ChargeOwner:
        """Cliente y compra (si la hay) de un cargo: la disputa no los trae."""

    @abstractmethod
    async def create_billing_portal_session(
        self, *, customer_id: str, return_url: str, locale: str = "es"
    ) -> str:
        """URL del portal donde el profesional cambia su medio de pago o cancela."""
