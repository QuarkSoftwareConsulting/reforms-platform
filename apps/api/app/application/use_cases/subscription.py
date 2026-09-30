"""Casos de uso de la mensualidad del profesional.

El cobro y la activacion no ocurren aqui: iniciar la suscripcion solo devuelve la
URL del checkout. La cuenta se activa y el saldo se abona cuando el webhook
confirma el cobro (`ApplySubscriptionEvent`), nunca al volver el navegador.

El importe lo fija el admin (`SetSubscriptionPrice`). Mientras no lo haga, rige el
de configuracion (`STRIPE_TOPUP_PRICE_ID` + `SUBSCRIPTION_TOPUP_CENTS`).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto import AccountSummary, SubscriptionPriceInfo
from app.application.ports import (
    ClockPort,
    CreditLedgerRepositoryPort,
    CustomerRequest,
    IdGeneratorPort,
    PaymentPort,
    ProfessionalAccountRepositoryPort,
    ProfessionalRepositoryPort,
    SubscriptionCheckoutRequest,
    SubscriptionPriceRepositoryPort,
    UnitOfWork,
)
from app.application.use_cases.credit_ledger import CreditLedgerService
from app.domain.exceptions import (
    PaymentGatewayError,
    ProfessionalNotFoundError,
    SubscriptionRequiredError,
    ValidationError,
)
from app.domain.models import (
    CreditEntryKind,
    Professional,
    ProfessionalAccount,
    SubscriptionPrice,
    SubscriptionStatus,
    assert_valid_subscription_amount,
)
from app.domain.value_objects import Money

RECENT_ENTRIES = 20
PRODUCT_NAME = "Mensualidad Voy a Reformar"


@dataclass(slots=True)
class SubscriptionPricing:
    """Resuelve la mensualidad vigente: la del admin o, si no hay, la de configuracion."""

    prices: SubscriptionPriceRepositoryPort
    default_amount: Money
    default_price_id: str

    async def current(self) -> SubscriptionPriceInfo:
        price = await self.prices.current()
        if price is not None:
            return SubscriptionPriceInfo(
                amount=price.amount,
                stripe_price_id=price.stripe_price_id,
                updated_at=price.created_at,
                is_default=False,
            )
        return SubscriptionPriceInfo(
            amount=self.default_amount,
            stripe_price_id=self.default_price_id or None,
            updated_at=None,
            is_default=True,
        )


@dataclass(slots=True)
class SetSubscriptionPrice:
    """El admin cambia la mensualidad. Solo afecta a las suscripciones nuevas."""

    prices: SubscriptionPriceRepositoryPort
    pricing: SubscriptionPricing
    payments: PaymentPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork
    currency: str

    async def execute(self, *, amount_cents: int, admin_user_id: UUID) -> SubscriptionPriceInfo:
        amount = Money(amount_cents, self.currency)
        assert_valid_subscription_amount(amount)
        current = await self.pricing.current()
        if not current.is_default and current.amount == amount:
            return current

        # Llamada de red antes de escribir: si la pasarela falla no queda una
        # mensualidad sin precio al que suscribirse.
        stripe_price_id = await self.payments.create_recurring_price(
            amount=amount, product_name=PRODUCT_NAME
        )
        async with self.uow:
            await self.prices.add(
                SubscriptionPrice(
                    id=self.ids.new_id(),
                    amount=amount,
                    stripe_price_id=stripe_price_id,
                    created_at=self.clock.now(),
                    created_by_user_id=admin_user_id,
                )
            )
        return await self.pricing.current()


@dataclass(slots=True)
class StartSubscription:
    accounts: ProfessionalAccountRepositoryPort
    pricing: SubscriptionPricing
    payments: PaymentPort
    clock: ClockPort
    uow: UnitOfWork
    web_base_url: str
    currency: str

    async def execute(self, *, professional: Professional, email: str, locale: str = "es") -> str:
        """Devuelve la URL del checkout de la mensualidad vigente."""
        account = await self.accounts.get(professional.id)
        if account is not None:
            account.assert_can_start_subscription()

        price = await self.pricing.current()
        if price.stripe_price_id is None:
            raise PaymentGatewayError("La mensualidad no esta configurada")

        customer_id = account.stripe_customer_id if account is not None else None
        if customer_id is None:
            # Llamada de red fuera de la transaccion, como en la compra de leads.
            customer_id = await self.payments.create_customer(
                CustomerRequest(
                    professional_id=professional.id,
                    email=email,
                    name=professional.business_name,
                )
            )
            async with self.uow:
                if account is None:
                    account = ProfessionalAccount.open(
                        professional_id=professional.id,
                        currency=self.currency,
                        now=self.clock.now(),
                    )
                    account.attach_customer(customer_id)
                    await self.accounts.add(account)
                else:
                    account.attach_customer(customer_id)
                    await self.accounts.update(account)

        session = await self.payments.create_subscription_checkout(
            SubscriptionCheckoutRequest(
                professional_id=professional.id,
                customer_id=customer_id,
                price_id=price.stripe_price_id,
                success_url=f"{self.web_base_url}/{locale}/suscripcion?status=success",
                cancel_url=f"{self.web_base_url}/{locale}/suscripcion?status=cancelled",
                locale=locale,
            )
        )
        return session.url


@dataclass(slots=True)
class OpenBillingPortal:
    accounts: ProfessionalAccountRepositoryPort
    payments: PaymentPort
    web_base_url: str

    async def execute(self, *, professional_id: UUID, locale: str = "es") -> str:
        account = await self.accounts.get(professional_id)
        if account is None or account.stripe_customer_id is None:
            raise SubscriptionRequiredError()
        return await self.payments.create_billing_portal_session(
            customer_id=account.stripe_customer_id,
            return_url=f"{self.web_base_url}/{locale}/suscripcion",
            locale=locale,
        )


@dataclass(slots=True)
class GetProfessionalAccount:
    accounts: ProfessionalAccountRepositoryPort
    ledger: CreditLedgerRepositoryPort
    pricing: SubscriptionPricing
    clock: ClockPort

    async def execute(
        self, *, professional_id: UUID, include_entries: bool = False
    ) -> AccountSummary:
        account = await self.accounts.get(professional_id)
        offered = (await self.pricing.current()).amount
        if account is None:
            return AccountSummary(
                status=SubscriptionStatus.NONE,
                is_active=False,
                balance=Money.zero(offered.currency),
                topup_amount=offered,
                current_period_end=None,
                can_manage_billing=False,
            )
        entries = (
            await self.ledger.list_for_professional(professional_id, limit=RECENT_ENTRIES)
            if include_entries
            else []
        )
        # Quien ya paga conserva su importe aunque el admin cambie la mensualidad:
        # se le muestra lo que realmente se le cobra, no la tarifa de hoy.
        latest = await self.ledger.latest_topup(professional_id)
        paying = account.subscription_status is not SubscriptionStatus.CANCELED
        return AccountSummary(
            status=account.subscription_status,
            is_active=account.is_active(self.clock.now()),
            balance=account.balance,
            topup_amount=latest.amount if latest is not None and paying else offered,
            current_period_end=account.current_period_end,
            can_manage_billing=account.stripe_customer_id is not None,
            entries=entries,
        )


@dataclass(slots=True)
class AdjustProfessionalCredit:
    """Ajuste manual de saldo por el admin (p. ej. compensar un lead problematico).

    Es la via para "devolver" el saldo de una compra reembolsada: la plaza no se
    libera (el dato ya se cedio), pero el admin puede abonar el importe.
    """

    professionals: ProfessionalRepositoryPort
    accounts: ProfessionalAccountRepositoryPort
    credit: CreditLedgerService
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork
    currency: str

    async def execute(
        self, *, professional_id: UUID, amount_cents: int, note: str, admin_user_id: UUID
    ) -> ProfessionalAccount:
        if amount_cents == 0:
            raise ValidationError("El ajuste no puede ser de 0")
        note = note.strip()
        if len(note) < 3:
            raise ValidationError("Explica el motivo del ajuste")
        if await self.professionals.get(professional_id) is None:
            raise ProfessionalNotFoundError()

        now = self.clock.now()
        async with self.uow:
            account = await self.accounts.get_for_update(professional_id)
            if account is None:
                account = await self.accounts.add(
                    ProfessionalAccount.open(
                        professional_id=professional_id, currency=self.currency, now=now
                    )
                )
            await self.credit.record(
                account,
                kind=(
                    CreditEntryKind.ADJUSTMENT_CREDIT
                    if amount_cents > 0
                    else CreditEntryKind.ADJUSTMENT_DEBIT
                ),
                amount=Money(abs(amount_cents), account.currency),
                source_ref=f"adjustment:{self.ids.new_id()}",
                now=now,
                note=note,
                created_by_user_id=admin_user_id,
            )
        return account
