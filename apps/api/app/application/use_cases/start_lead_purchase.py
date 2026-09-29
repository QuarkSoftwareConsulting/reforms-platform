"""Caso de uso critico: iniciar la compra del contacto de un lead.

Reserva una plaza ANTES de enviar al profesional a la pasarela. Si el cap se
validara solo al confirmar el pago, N profesionales podrian pagar a la vez por un
lead de 5 plazas y habria que reembolsar a los que sobran. Con la reserva:

  1. Bloqueamos la fila del lead (`SELECT ... FOR UPDATE`).
  2. Contamos plazas vivas (pagadas + reservas no caducadas).
  3. Si queda hueco, creamos la compra en estado RESERVED con un TTL.
  4. Solo entonces pedimos la sesion de checkout.

El TTL evita que un checkout abandonado bloquee el lead para siempre.

Solo compra quien esta validado por el admin y al dia con la recarga mensual. El
saldo de la recarga se gasta dentro de la misma transaccion, con la cuenta bloqueada
DESPUES del lead (siempre en ese orden, para no interbloquear con otra compra). Si el
saldo cubre el precio entero la compra queda pagada sin pasar por la pasarela: ese
dinero ya lo confirmo el webhook cuando se cobro la recarga.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.application.dto import StartPurchaseResult
from app.application.ports import (
    CategoryRepositoryPort,
    CheckoutRequest,
    ClockPort,
    IdGeneratorPort,
    LeadRepositoryPort,
    PaymentPort,
    ProfessionalAccountRepositoryPort,
    ProfessionalRepositoryPort,
    PurchaseRepositoryPort,
    UnitOfWork,
)
from app.application.use_cases.account_access import require_active, require_active_account
from app.application.use_cases.credit_ledger import CreditLedgerService
from app.domain.exceptions import (
    CategoryNotFoundError,
    LeadNotFoundError,
    ProfessionalNotFoundError,
)
from app.domain.models import CreditEntryKind, Purchase, PurchaseStatus
from app.domain.value_objects import Money


@dataclass(slots=True)
class StartLeadPurchase:
    leads: LeadRepositoryPort
    purchases: PurchaseRepositoryPort
    professionals: ProfessionalRepositoryPort
    categories: CategoryRepositoryPort
    accounts: ProfessionalAccountRepositoryPort
    credit: CreditLedgerService
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
        # Compra solo quien el admin ya valido (F02); antes que la recarga, porque es
        # lo primero que tiene que resolver un profesional recien registrado.
        professional.assert_can_purchase()

        now = self.clock.now()
        reserved_until = now + timedelta(minutes=self.reservation_ttl_minutes)

        # Comprobacion temprana, sin bloqueo: evita tomar el lock del lead para
        # alguien que de todos modos no puede comprar. Se repite bajo bloqueo.
        await require_active_account(self.accounts, professional.id, now)

        # --- Fase 1: reservar la plaza dentro de la transaccion -------------
        async with self.uow:
            lead = await self.leads.get_for_update(lead_id)
            if lead is None:
                raise LeadNotFoundError()

            category = await self.categories.get(lead.category_id)
            if category is None:
                raise CategoryNotFoundError()

            # El precio se congela aqui, dentro del bloqueo de fila: la compra se
            # cobra al importe vigente en el instante de reservar la plaza, aunque
            # el admin lo cambie mientras el profesional completa el checkout.
            price = lead.sale_price(suggested=category.suggested_lead_price)

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

            # Orden de bloqueo fijo: lead y despues cuenta.
            account = require_active(await self.accounts.get_for_update(professional.id), now)
            credit = account.credit_to_apply(price)

            purchase = Purchase(
                id=self.ids.new_id(),
                lead_id=lead.id,
                professional_id=professional.id,
                price=price,
                status=PurchaseStatus.RESERVED,
                created_at=now,
                reserved_until=reserved_until,
                credit_applied=credit if credit.amount_cents > 0 else None,
            )
            purchase = await self.purchases.add(purchase)

            if purchase.credit_applied is not None:
                await self.credit.record(
                    account,
                    kind=CreditEntryKind.SPEND,
                    amount=purchase.credit_applied,
                    source_ref=str(purchase.id),
                    now=now,
                )

            if purchase.is_covered_by_credit:
                purchase.mark_paid(now=now)
                lead.register_paid_purchase()
                await self.purchases.update(purchase)
                await self.leads.update(lead)

        if purchase.is_covered_by_credit:
            return StartPurchaseResult(
                purchase_id=purchase.id,
                checkout_url=None,
                checkout_session_id=None,
                amount=price,
                expires_at=None,
                credit_applied=price,
                amount_due=purchase.amount_due,
            )

        # --- Fase 2: crear la sesion de pago (llamada de red, fuera de la tx) -
        # Se hace despues del commit para no mantener el bloqueo de fila abierto
        # durante una peticion HTTP a la pasarela.
        try:
            session = await self.payments.create_checkout_session(
                CheckoutRequest(
                    purchase_id=purchase.id,
                    lead_id=lead.id,
                    professional_id=professional.id,
                    amount=purchase.amount_due,
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
            # Si la pasarela no responde, liberamos la plaza (y el saldo aplicado) en
            # el acto: un fallo de nuestra infraestructura no debe bloquear una de las
            # plazas del lead durante todo el TTL de reserva.
            await self._release(purchase, now=now)
            raise

        async with self.uow:
            purchase.attach_checkout_session(session.id)
            await self.purchases.update(purchase)

        return StartPurchaseResult(
            purchase_id=purchase.id,
            checkout_url=session.url,
            checkout_session_id=session.id,
            amount=price,
            expires_at=reserved_until,
            credit_applied=purchase.credit_applied or Money.zero(price.currency),
            amount_due=purchase.amount_due,
        )

    async def _release(self, purchase: Purchase, *, now: datetime) -> None:
        """Marca la reserva como fallida para devolver la plaza y el saldo."""
        purchase.mark_failed()
        async with self.uow:
            await self.purchases.update(purchase)
            await self.credit.return_reserved_credit(purchase, now=now)
