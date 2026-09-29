"""Aplica a la cuenta del profesional un evento de la recarga mensual.

No se expone por si solo: lo invoca `HandlePaymentEvent` DESPUES de registrar el
evento en `processed_payment_events`, dentro de la misma transaccion. Asi los
eventos de la recarga pasan por el mismo cerrojo de idempotencia que los de las
compras (un `invoice.paid` reenviado no abona el saldo dos veces).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports import (
    ClockPort,
    PaymentEvent,
    PaymentEventType,
    ProfessionalAccountRepositoryPort,
)
from app.application.use_cases.credit_ledger import CreditLedgerService
from app.domain.exceptions import ProfessionalAccountNotFoundError
from app.domain.models import CreditEntryKind, ProfessionalAccount
from app.domain.value_objects import Money


@dataclass(slots=True)
class ApplySubscriptionEvent:
    accounts: ProfessionalAccountRepositoryPort
    credit: CreditLedgerService
    clock: ClockPort

    async def execute(self, event: PaymentEvent) -> ProfessionalAccount:
        account = await self._load(event)
        now = self.clock.now()
        at = event.occurred_at or now

        if event.type is PaymentEventType.SUBSCRIPTION_CHECKOUT_COMPLETED:
            account.record_checkout_completed(subscription_id=event.subscription_id, at=at)
        elif event.type is PaymentEventType.INVOICE_PAID:
            account.record_invoice_paid(
                subscription_id=event.subscription_id, period_end=event.period_end, at=at
            )
            # El abono se registra aunque el evento llegue desordenado: el dinero se
            # cobro igual. La idempotencia la da la factura (`source_ref`).
            if event.invoice_id and event.amount_cents and event.currency:
                await self.credit.record(
                    account,
                    kind=CreditEntryKind.TOPUP,
                    amount=Money(event.amount_cents, event.currency),
                    source_ref=event.invoice_id,
                    now=now,
                )
        elif event.type is PaymentEventType.INVOICE_PAYMENT_FAILED:
            account.record_payment_failed(at=at)
        elif (
            event.type is PaymentEventType.SUBSCRIPTION_UPDATED
            and event.subscription_status is not None
        ):
            account.sync_subscription(
                status=event.subscription_status,
                subscription_id=event.subscription_id,
                period_end=event.period_end,
                at=at,
            )

        await self.accounts.update(account)
        return account

    async def _load(self, event: PaymentEvent) -> ProfessionalAccount:
        account = (
            await self.accounts.get_by_customer_for_update(event.customer_id)
            if event.customer_id
            else None
        )
        if account is None:
            # Se lanza en vez de ignorarlo: el error revierte el registro del evento
            # y Stripe lo reintentara. Ignorarlo podria perder una recarga cobrada.
            raise ProfessionalAccountNotFoundError(
                f"El evento {event.id} no referencia ninguna cuenta conocida"
            )
        return account
