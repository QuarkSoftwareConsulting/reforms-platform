"""Entidad Purchase: la compra de un contacto por parte de un profesional."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.exceptions import PurchaseNotPayableError
from app.domain.models.enums import PurchaseStatus
from app.domain.value_objects import Money


@dataclass(slots=True)
class Purchase:
    """Compra de un lead.

    Nace en `RESERVED` para bloquear una de las plazas del lead mientras el
    profesional completa el pago en Stripe. Si el checkout caduca la reserva se
    libera; si el webhook confirma el pago pasa a `PAID` y desbloquea el contacto.
    """

    id: UUID
    lead_id: UUID
    professional_id: UUID
    price: Money
    status: PurchaseStatus
    created_at: datetime
    reserved_until: datetime | None = None
    stripe_checkout_session_id: str | None = None
    stripe_payment_intent_id: str | None = None
    paid_at: datetime | None = None

    # ----------------------------- Consultas -----------------------------

    def is_reservation_expired(self, now: datetime) -> bool:
        if self.status is not PurchaseStatus.RESERVED:
            return False
        return self.reserved_until is not None and self.reserved_until <= now

    @property
    def unlocks_contact(self) -> bool:
        return self.status.unlocks_contact

    def occupies_slot_at(self, now: datetime) -> bool:
        """Una reserva caducada ya no ocupa plaza aunque siga en estado RESERVED."""
        if self.is_reservation_expired(now):
            return False
        return self.status.occupies_slot

    # ----------------------------- Transiciones --------------------------

    def attach_checkout_session(self, session_id: str) -> None:
        if self.status is not PurchaseStatus.RESERVED:
            raise PurchaseNotPayableError(
                "Solo una reserva puede asociarse a una sesion de checkout"
            )
        self.stripe_checkout_session_id = session_id

    def mark_paid(self, *, now: datetime, payment_intent_id: str | None = None) -> None:
        """Confirma el pago. Idempotente: repetir sobre una compra pagada no hace nada.

        El webhook de Stripe puede entregar el mismo evento varias veces, asi que
        esta transicion debe tolerar reintentos sin duplicar efectos.
        """
        if self.status is PurchaseStatus.PAID:
            return
        if self.status is not PurchaseStatus.RESERVED:
            raise PurchaseNotPayableError(
                f"No se puede pagar una compra en estado {self.status.value}"
            )
        self.status = PurchaseStatus.PAID
        self.paid_at = now
        self.reserved_until = None
        if payment_intent_id:
            self.stripe_payment_intent_id = payment_intent_id

    def mark_expired(self) -> None:
        """Libera la plaza de una reserva que nunca se pago."""
        if self.status is not PurchaseStatus.RESERVED:
            return
        self.status = PurchaseStatus.EXPIRED
        self.reserved_until = None

    def mark_failed(self) -> None:
        if self.status is PurchaseStatus.PAID:
            raise PurchaseNotPayableError("Una compra pagada no puede marcarse como fallida")
        self.status = PurchaseStatus.FAILED
        self.reserved_until = None

    def mark_refunded(self) -> None:
        if self.status is not PurchaseStatus.PAID:
            raise PurchaseNotPayableError("Solo se puede reembolsar una compra pagada")
        self.status = PurchaseStatus.REFUNDED
