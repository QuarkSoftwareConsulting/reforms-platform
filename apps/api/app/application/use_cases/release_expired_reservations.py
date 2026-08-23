"""Caso de uso: liberar las plazas de reservas caducadas.

Se dispara desde el evento `checkout.session.expired` y desde un job periodico,
porque Stripe puede tardar en emitir ese evento (o no emitirlo si el usuario nunca
abrio el checkout).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.application.ports import (
    ClockPort,
    PaymentPort,
    PurchaseRepositoryPort,
    UnitOfWork,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ReleaseExpiredReservations:
    purchases: PurchaseRepositoryPort
    payments: PaymentPort
    clock: ClockPort
    uow: UnitOfWork

    async def execute(self, *, batch_size: int = 100) -> int:
        now = self.clock.now()
        expired = await self.purchases.list_expired_reservations(now=now, limit=batch_size)
        if not expired:
            return 0

        released = 0
        async with self.uow:
            for purchase in expired:
                purchase.mark_expired()
                await self.purchases.update(purchase)
                released += 1

        # Cerrar la sesion en la pasarela es best-effort: la plaza ya esta libre en
        # nuestra BD y el pago tardio se rechazaria de todos modos.
        for purchase in expired:
            if purchase.stripe_checkout_session_id:
                try:
                    await self.payments.expire_checkout_session(purchase.stripe_checkout_session_id)
                except Exception:
                    logger.warning(
                        "No se pudo expirar la sesion de checkout %s",
                        purchase.stripe_checkout_session_id,
                        exc_info=True,
                    )
        return released
