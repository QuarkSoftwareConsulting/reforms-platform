"""Caso de uso: procesar un evento de la pasarela de pago (webhook).

Dos garantias imprescindibles:

* **Idempotencia**: Stripe reenvia eventos. El registro `stripe_events` actua como
  cerrojo: si el `event_id` ya existe, salimos sin repetir efectos.
* **Atomicidad**: marcar la compra como pagada e incrementar el contador del lead
  ocurre en la misma transaccion, con la fila del lead bloqueada.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports import (
    ClockPort,
    LeadRepositoryPort,
    PaymentEvent,
    PaymentEventType,
    PaymentPort,
    ProcessedEventRepositoryPort,
    PurchaseRepositoryPort,
    UnitOfWork,
)
from app.domain.exceptions import LeadNotFoundError, PurchaseNotFoundError
from app.domain.models import Purchase


@dataclass(frozen=True, slots=True)
class PaymentEventOutcome:
    event_id: str
    event_type: str
    handled: bool
    duplicate: bool = False
    purchase: Purchase | None = None


@dataclass(slots=True)
class HandlePaymentEvent:
    purchases: PurchaseRepositoryPort
    leads: LeadRepositoryPort
    processed_events: ProcessedEventRepositoryPort
    payments: PaymentPort
    clock: ClockPort
    uow: UnitOfWork

    async def execute(self, *, payload: bytes, signature: str) -> PaymentEventOutcome:
        event = self.payments.parse_webhook_event(payload, signature)

        if event.type is PaymentEventType.IGNORED:
            return PaymentEventOutcome(event_id=event.id, event_type=event.raw_type, handled=False)

        async with self.uow:
            is_new = await self.processed_events.mark_processed(
                event.id, event.raw_type, event.payload
            )
            if not is_new:
                return PaymentEventOutcome(
                    event_id=event.id,
                    event_type=event.raw_type,
                    handled=False,
                    duplicate=True,
                )

            purchase = await self._resolve_purchase(event)
            if purchase is None:
                raise PurchaseNotFoundError(
                    f"El evento {event.id} no referencia ninguna compra conocida"
                )

            if event.type is PaymentEventType.CHECKOUT_COMPLETED:
                await self._confirm(purchase, event)
            elif event.type is PaymentEventType.CHECKOUT_EXPIRED:
                purchase.mark_expired()
                await self.purchases.update(purchase)
            elif event.type is PaymentEventType.PAYMENT_FAILED:
                purchase.mark_failed()
                await self.purchases.update(purchase)
            elif event.type is PaymentEventType.REFUNDED:
                purchase.mark_refunded()
                await self.purchases.update(purchase)

            return PaymentEventOutcome(
                event_id=event.id,
                event_type=event.raw_type,
                handled=True,
                purchase=purchase,
            )

    async def _resolve_purchase(self, event: PaymentEvent) -> Purchase | None:
        if event.purchase_id is not None:
            purchase = await self.purchases.get(event.purchase_id)
            if purchase is not None:
                return purchase
        if event.checkout_session_id is not None:
            return await self.purchases.get_by_checkout_session(event.checkout_session_id)
        return None

    async def _confirm(self, purchase: Purchase, event: PaymentEvent) -> None:
        if purchase.unlocks_contact:
            # Ya estaba pagada (reintento con otro event_id): no volvemos a contar.
            return

        lead = await self.leads.get_for_update(purchase.lead_id)
        if lead is None:
            raise LeadNotFoundError()

        purchase.mark_paid(now=self.clock.now(), payment_intent_id=event.payment_intent_id)
        lead.register_paid_purchase()

        await self.purchases.update(purchase)
        await self.leads.update(lead)
