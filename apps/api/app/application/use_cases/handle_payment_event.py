"""Caso de uso: procesar un evento de la pasarela de pago (webhook).

Dos garantias imprescindibles:

* **Idempotencia**: Stripe reenvia eventos. El registro `stripe_events` actua como
  cerrojo: si el `event_id` ya existe, salimos sin repetir efectos.
* **Atomicidad**: marcar la compra como pagada e incrementar el contador del lead
  ocurre en la misma transaccion, con la fila del lead bloqueada.

Los eventos de la recarga mensual pasan por el mismo registro de idempotencia y
despues se delegan en `ApplySubscriptionEvent`; las devoluciones de un cobro por el
banco, en `ApplyChargeback`.
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
from app.application.use_cases.apply_chargeback import ApplyChargeback
from app.application.use_cases.apply_subscription_event import ApplySubscriptionEvent
from app.application.use_cases.credit_ledger import CreditLedgerService
from app.domain.exceptions import LeadNotFoundError, PurchaseNotFoundError
from app.domain.models import ProfessionalAccount, Purchase, PurchaseStatus


@dataclass(frozen=True, slots=True)
class PaymentEventOutcome:
    event_id: str
    event_type: str
    handled: bool
    duplicate: bool = False
    purchase: Purchase | None = None
    account: ProfessionalAccount | None = None


@dataclass(slots=True)
class HandlePaymentEvent:
    purchases: PurchaseRepositoryPort
    leads: LeadRepositoryPort
    processed_events: ProcessedEventRepositoryPort
    payments: PaymentPort
    clock: ClockPort
    uow: UnitOfWork
    credit: CreditLedgerService
    subscriptions: ApplySubscriptionEvent
    chargebacks: ApplyChargeback

    async def execute(self, *, payload: bytes, signature: str) -> PaymentEventOutcome:
        event = self.payments.parse_webhook_event(payload, signature)

        if event.type is PaymentEventType.IGNORED:
            return PaymentEventOutcome(event_id=event.id, event_type=event.raw_type, handled=False)

        # La disputa no dice de quien es el cargo: se pregunta a la pasarela ANTES de
        # abrir la transaccion, para no tener bloqueos esperando a la red. Si falla,
        # el webhook responde error y la pasarela reintenta.
        owner = (
            await self.payments.describe_charge(event.charge_id)
            if event.type.concerns_dispute and event.charge_id
            else None
        )

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

            if event.type.concerns_subscription:
                account = await self.subscriptions.execute(event)
                return PaymentEventOutcome(
                    event_id=event.id,
                    event_type=event.raw_type,
                    handled=True,
                    account=account,
                )

            if event.type.concerns_dispute:
                disputed = (
                    await self.chargebacks.execute(event, owner) if owner is not None else None
                )
                return PaymentEventOutcome(
                    event_id=event.id,
                    event_type=event.raw_type,
                    handled=disputed is not None,
                    account=disputed,
                )

            purchase = await self._resolve_purchase(event)
            if purchase is None:
                raise PurchaseNotFoundError(
                    f"El evento {event.id} no referencia ninguna compra conocida"
                )

            if event.type is PaymentEventType.CHECKOUT_COMPLETED:
                await self._confirm(purchase, event)
            elif event.type is PaymentEventType.CHECKOUT_EXPIRED:
                await self._release(purchase, expired=True)
            elif event.type is PaymentEventType.PAYMENT_FAILED:
                await self._release(purchase, expired=False)
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

    async def _release(self, purchase: Purchase, *, expired: bool) -> None:
        """Libera la plaza y devuelve el saldo aplicado, solo si seguia reservada.

        Un evento de caducidad o fallo que llega sobre una compra ya cerrada no debe
        devolver saldo: la plaza (y el saldo) ya se liberaron o la compra se pago.
        """
        was_reserved = purchase.status is PurchaseStatus.RESERVED
        if expired:
            purchase.mark_expired()
        else:
            purchase.mark_failed()
        await self.purchases.update(purchase)
        if was_reserved:
            await self.credit.return_reserved_credit(purchase, now=self.clock.now())

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
