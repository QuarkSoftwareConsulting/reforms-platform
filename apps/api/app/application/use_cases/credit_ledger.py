"""Movimientos de saldo compartidos por varios casos de uso.

Gastar saldo en una compra, devolverlo si la reserva no llega a pagarse y abonar
una recarga son la misma operacion con distinto signo: registrar el movimiento en
el libro y, solo si es nuevo, aplicarlo al saldo de la cuenta bloqueada. Vive en un
solo sitio para que ningun camino (compra, caducidad, webhook, job) se salte el
cerrojo de idempotencia del libro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.ports import (
    CreditLedgerRepositoryPort,
    IdGeneratorPort,
    ProfessionalAccountRepositoryPort,
)
from app.domain.exceptions import ProfessionalAccountNotFoundError
from app.domain.models import CreditEntry, CreditEntryKind, ProfessionalAccount, Purchase
from app.domain.value_objects import Money


@dataclass(slots=True)
class CreditLedgerService:
    accounts: ProfessionalAccountRepositoryPort
    ledger: CreditLedgerRepositoryPort
    ids: IdGeneratorPort

    async def record(
        self,
        account: ProfessionalAccount,
        *,
        kind: CreditEntryKind,
        amount: Money,
        source_ref: str,
        now: datetime,
        note: str | None = None,
        created_by_user_id: UUID | None = None,
    ) -> bool:
        """Registra y aplica un movimiento sobre una cuenta YA bloqueada.

        Devuelve False si el movimiento ya existia (reintento): el saldo no cambia.
        """
        entry = CreditEntry(
            id=self.ids.new_id(),
            professional_id=account.professional_id,
            kind=kind,
            amount=amount,
            source_ref=source_ref,
            created_at=now,
            note=note,
            created_by_user_id=created_by_user_id,
        )
        # Se valida contra el saldo antes de escribir: si el cargo no cabe, la
        # excepcion no deja un movimiento huerfano en el libro.
        account.balance_after(entry)
        if not await self.ledger.add_if_absent(entry):
            return False
        account.apply(entry)
        await self.accounts.update(account)
        return True

    async def return_reserved_credit(self, purchase: Purchase, *, now: datetime) -> None:
        """Devuelve el saldo de una reserva que caduco o fallo sin llegar a pagarse.

        Debe llamarse dentro de la transaccion que cambia el estado de la compra,
        para que la plaza y el saldo se liberen juntos o no se libere ninguno.
        """
        if purchase.credit_applied is None or purchase.credit_cents == 0:
            return
        account = await self.accounts.get_for_update(purchase.professional_id)
        if account is None:
            raise ProfessionalAccountNotFoundError()
        await self.record(
            account,
            kind=CreditEntryKind.SPEND_REVERSAL,
            amount=purchase.credit_applied,
            source_ref=str(purchase.id),
            now=now,
        )
