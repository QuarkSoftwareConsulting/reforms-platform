"""Caso de uso critico: iniciar la compra del contacto de un lead.

Reserva una plaza ANTES de enviar al profesional a la pasarela. Si el cap se
validara solo al confirmar el pago, N profesionales podrian pagar a la vez por un
lead de 3 plazas y habria que reembolsar a los que sobran. Con la reserva:

  1. Bloqueamos la fila del lead (`SELECT ... FOR UPDATE`).
  2. Contamos plazas vivas (pagadas + reservas no caducadas).
  3. Si queda hueco, creamos la compra en estado RESERVED con un TTL.
  4. Solo entonces pedimos la sesion de checkout.

El TTL evita que un checkout abandonado bloquee el lead para siempre.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from app.application.dto import StartPurchaseResult
from app.application.ports import (
    CategoryRepositoryPort,
    CheckoutRequest,
    ClockPort,
    IdGeneratorPort,
    LeadRepositoryPort,
    PaymentPort,
    ProfessionalRepositoryPort,
    PurchaseRepositoryPort,
    UnitOfWork,
)
from app.domain.exceptions import (
    CategoryNotFoundError,
    LeadNotFoundError,
    ProfessionalNotFoundError,
)
from app.domain.models import Purchase, PurchaseStatus


@dataclass(slots=True)
class StartLeadPurchase:
    leads: LeadRepositoryPort
    purchases: PurchaseRepositoryPort
    professionals: ProfessionalRepositoryPort
    categories: CategoryRepositoryPort
    payments: PaymentPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork
    web_base_url: str
    reservation_ttl_minutes: int = 30
    enforce_category_match: bool = True

    async def execute(
        self, *, lead_id: UUID, professional_id: UUID, locale: str = "es"
    ) -> StartPurchaseResult:
        professional = await self.professionals.get(professional_id)
        if professional is None:
            raise ProfessionalNotFoundError()
        professional.assert_ready_to_browse()

        now = self.clock.now()
        reserved_until = now + timedelta(minutes=self.reservation_ttl_minutes)

        # --- Fase 1: reservar la plaza dentro de la transaccion -------------
        async with self.uow:
            lead = await self.leads.get_for_update(lead_id)
            if lead is None:
                raise LeadNotFoundError()

            category = await self.categories.get(lead.category_id)
            if category is None:
                raise CategoryNotFoundError()

            existing = await self.purchases.find_active_for_lead_and_professional(
                lead_id, professional_id, now=now
            )
            occupied = await self.purchases.count_occupied_slots(lead_id, now=now)

            lead.assert_purchasable(
                occupied_slots=occupied,
                already_purchased_by_professional=existing is not None,
                professional_category_ids=(
                    professional.category_ids if self.enforce_category_match else None
                ),
            )

            purchase = Purchase(
                id=self.ids.new_id(),
                lead_id=lead.id,
                professional_id=professional.id,
                price=category.lead_price,
                status=PurchaseStatus.RESERVED,
                created_at=now,
                reserved_until=reserved_until,
            )
            purchase = await self.purchases.add(purchase)

        # --- Fase 2: crear la sesion de pago (llamada de red, fuera de la tx) -
        # Se hace despues del commit para no mantener el bloqueo de fila abierto
        # durante una peticion HTTP a la pasarela.
        try:
            session = await self.payments.create_checkout_session(
                CheckoutRequest(
                    purchase_id=purchase.id,
                    lead_id=lead.id,
                    professional_id=professional.id,
                    amount=category.lead_price,
                    product_name=f"{category.name(locale)} - {lead.location.city}",
                    product_description=lead.title,
                    customer_email=None,
                    success_url=(
                        f"{self.web_base_url}/{locale}/mis-contactos"
                        f"?purchase={purchase.id}&status=success"
                    ),
                    cancel_url=(
                        f"{self.web_base_url}/{locale}/proyectos/{lead.id}?status=cancelled"
                    ),
                    locale=locale,
                    expires_in_minutes=self.reservation_ttl_minutes,
                )
            )
        except Exception:
            # Si la pasarela no responde, liberamos la plaza en el acto: un fallo de
            # nuestra infraestructura no debe bloquear una de las 3 plazas del lead
            # durante todo el TTL de reserva.
            await self._release(purchase)
            raise

        async with self.uow:
            purchase.attach_checkout_session(session.id)
            await self.purchases.update(purchase)

        return StartPurchaseResult(
            purchase_id=purchase.id,
            checkout_url=session.url,
            checkout_session_id=session.id,
            amount=category.lead_price,
            expires_at=reserved_until,
        )

    async def _release(self, purchase: Purchase) -> None:
        """Marca la reserva como fallida para devolver la plaza al lead."""
        purchase.mark_failed()
        async with self.uow:
            await self.purchases.update(purchase)
