"""Aplica al saldo la devolucion de un cobro de la recarga por el banco.

Con SEPA el titular puede pedir a su banco que le devuelva un adeudo sin dar motivo
(8 semanas) y el banco nos lo retira sin preguntar; con tarjeta pasa lo mismo con
una disputa. No podemos impedirlo, pero el saldo que abono esa recarga ya no esta
respaldado por dinero: se retira, y si el profesional ya lo gasto queda como deuda.
Con deuda no se compra; la siguiente recarga cobrada la salda primero. Si la
pasarela gana la disputa y nos devuelve el dinero, se devuelve el saldo.

Como `ApplySubscriptionEvent`, no se expone por si solo: lo invoca
`HandlePaymentEvent` DESPUES de registrar el evento en `processed_payment_events`.
El segundo cerrojo es el libro: la disputa (`source_ref`) solo se retira una vez,
aunque lleguen `charge.dispute.created` y `charge.dispute.funds_withdrawn`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.application.ports import (
    ChargeOwner,
    ClockPort,
    CreditLedgerRepositoryPort,
    PaymentEvent,
    PaymentEventType,
    ProfessionalAccountRepositoryPort,
)
from app.application.use_cases.credit_ledger import CreditLedgerService
from app.domain.exceptions import ProfessionalAccountNotFoundError, ValidationError
from app.domain.models import CreditEntryKind, ProfessionalAccount
from app.domain.value_objects import Money

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ApplyChargeback:
    accounts: ProfessionalAccountRepositoryPort
    ledger: CreditLedgerRepositoryPort
    credit: CreditLedgerService
    clock: ClockPort

    async def execute(self, event: PaymentEvent, owner: ChargeOwner) -> ProfessionalAccount | None:
        """Devuelve la cuenta afectada, o None si el cargo no era de una recarga."""
        if owner.purchase_id is not None:
            # Disputa de la compra de un contacto: el dato ya se cedio (4.6) y ese
            # cobro no abono saldo. Queda en la pasarela para que el admin decida.
            logger.warning(
                "disputa_de_compra: dispute=%s purchase=%s", event.dispute_id, owner.purchase_id
            )
            return None
        if not owner.customer_id:
            logger.warning("disputa_sin_cliente: dispute=%s", event.dispute_id)
            return None
        if not event.dispute_id or not event.amount_cents or not event.currency:
            raise ValidationError(f"El evento {event.id} no trae la disputa ni su importe")

        account = await self.accounts.get_by_customer_for_update(owner.customer_id)
        if account is None:
            # Como en la recarga: el error revierte el registro del evento y la
            # pasarela lo reintentara, en vez de perder una devolucion.
            raise ProfessionalAccountNotFoundError(
                f"El evento {event.id} no referencia ninguna cuenta conocida"
            )

        now = self.clock.now()
        if event.type is PaymentEventType.CHARGE_DISPUTED:
            await self.credit.record(
                account,
                kind=CreditEntryKind.CHARGEBACK,
                amount=Money(event.amount_cents, event.currency),
                source_ref=event.dispute_id,
                now=now,
                note="Recarga devuelta por el banco",
            )
        elif event.type is PaymentEventType.DISPUTE_WON:
            # Solo se devuelve lo que se retiro: una consulta sin retirada de fondos
            # que se cierra a nuestro favor no debe abonar nada.
            withdrawn = await self.ledger.find(CreditEntryKind.CHARGEBACK, event.dispute_id)
            if withdrawn is not None:
                await self.credit.record(
                    account,
                    kind=CreditEntryKind.CHARGEBACK_REVERSAL,
                    amount=withdrawn.amount,
                    source_ref=event.dispute_id,
                    now=now,
                    note="Disputa ganada: la pasarela devolvio el importe",
                )
        return account
