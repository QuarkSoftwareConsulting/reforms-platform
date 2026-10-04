"""Cuenta del profesional: recarga mensual y saldo para comprar contactos.

La recarga mensual cumple dos funciones a la vez. Mantiene la cuenta activa (sin
ella se pueden ver solicitudes pero no comprarlas) y abona su importe como saldo,
que se gasta en contactos. Por eso el estado de la suscripcion y el saldo viven en
la misma entidad: se bloquean juntos al comprar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.domain.exceptions import (
    CreditDebtOutstandingError,
    CurrencyMismatchError,
    InsufficientCreditError,
    RejectionAwaitingPaymentError,
    SubscriptionAlreadyExistsError,
    SubscriptionRequiredError,
    ValidationError,
)
from app.domain.models.enums import CreditEntryKind, SubscriptionStatus
from app.domain.value_objects import Money

# Margen tras el fin del periodo pagado. La renovacion por SEPA tarda varios dias
# en confirmarse y durante ese tiempo la pasarela mantiene la suscripcion activa;
# sin margen, la cuenta se desactivaria cada mes mientras el adeudo esta en curso.
RENEWAL_GRACE = timedelta(days=7)

# Importe minimo que la pasarela acepta cobrar con tarjeta en EUR. Si el saldo deja
# un resto menor, se aplica menos saldo para que el cobro sea posible.
MIN_CHARGE_CENTS = 50

NOTE_MAX_LENGTH = 500


@dataclass(frozen=True, slots=True)
class CreditEntry:
    """Movimiento append-only del libro de saldo.

    `source_ref` identifica el hecho que lo origina (factura de la recarga, compra,
    ajuste). Junto con `kind` es unico: es el segundo cerrojo, tras el registro de
    eventos del webhook, contra abonar dos veces la misma recarga.
    """

    id: UUID
    professional_id: UUID
    kind: CreditEntryKind
    amount: Money
    source_ref: str
    created_at: datetime
    note: str | None = None
    created_by_user_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.amount.amount_cents <= 0:
            raise ValidationError("Un movimiento de saldo debe tener importe positivo")
        if not self.source_ref.strip():
            raise ValidationError("Un movimiento de saldo necesita una referencia de origen")
        if self.note is not None and len(self.note) > NOTE_MAX_LENGTH:
            raise ValidationError(f"La nota no puede superar {NOTE_MAX_LENGTH} caracteres")

    @property
    def signed_cents(self) -> int:
        return self.amount.amount_cents if self.kind.is_credit else -self.amount.amount_cents


@dataclass(slots=True)
class ProfessionalAccount:
    """Suscripcion de recarga + saldo de un profesional."""

    professional_id: UUID
    balance: Money
    created_at: datetime
    subscription_status: SubscriptionStatus = SubscriptionStatus.NONE
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_end: datetime | None = None
    status_synced_at: datetime | None = None
    """Instante del ultimo evento de la pasarela aplicado al estado.

    Stripe no garantiza el orden de entrega: sin esta marca, un evento antiguo que
    llega tarde podria reactivar una suscripcion cancelada o al reves.
    """
    debt_cents: int = 0
    """Lo que el profesional nos debe por una recarga devuelta que ya habia gastado.

    Va aparte del saldo (que nunca es negativo): el saldo "neto" es saldo menos deuda.
    Cualquier abono salda primero la deuda, y con deuda no se compra.
    """

    @classmethod
    def open(cls, *, professional_id: UUID, currency: str, now: datetime) -> ProfessionalAccount:
        return cls(professional_id=professional_id, balance=Money.zero(currency), created_at=now)

    # ----------------------------- Consultas -----------------------------

    @property
    def currency(self) -> str:
        return self.balance.currency

    def is_active(self, now: datetime) -> bool:
        if self.subscription_status is not SubscriptionStatus.ACTIVE:
            return False
        if self.current_period_end is None:
            return True
        return now < self.current_period_end + RENEWAL_GRACE

    @property
    def debt(self) -> Money:
        return Money(self.debt_cents, self.currency)

    def assert_can_purchase(self, now: datetime) -> None:
        if not self.is_active(now):
            raise SubscriptionRequiredError()
        # Con la recarga al dia pero una devolucion sin saldar: el saldo que gasto
        # era dinero que el banco nos retiro.
        if self.debt_cents > 0:
            raise CreditDebtOutstandingError()

    def assert_can_start_subscription(self) -> None:
        """Evita una segunda suscripcion (y un segundo cobro mensual) en paralelo.

        Con el cobro pendiente o fallido la via es el portal de pagos, no un checkout
        nuevo.
        """
        if self.subscription_status in {
            SubscriptionStatus.PENDING,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PAST_DUE,
        }:
            raise SubscriptionAlreadyExistsError()

    def assert_no_charge_in_flight(self) -> None:
        """Rechazar el alta exige que el cobro de la recarga ya se haya resuelto.

        En `PENDING` el profesional completo el checkout pero el dinero no ha llegado
        (con SEPA, dias). Ese adeudo no se puede anular: se confirmaria despues del
        rechazo y abonaria saldo a un rechazado sin reembolso (4.13). Con el cobro
        confirmado se reembolsa; si falla, la cuenta pasa a `PAST_DUE` y no hay nada
        que devolver.
        """
        if self.subscription_status is SubscriptionStatus.PENDING:
            raise RejectionAwaitingPaymentError()

    def credit_to_apply(self, price: Money) -> Money:
        """Cuanto saldo se aplica a una compra de `price`.

        Todo el que haga falta, salvo que el resto a cobrar quede por debajo del
        minimo de la pasarela: entonces se aplica menos para que el cobro sea viable.
        """
        if price.currency != self.currency:
            return Money.zero(price.currency)
        available = min(self.balance.amount_cents, price.amount_cents)
        remainder = price.amount_cents - available
        if 0 < remainder < MIN_CHARGE_CENTS:
            available = max(0, price.amount_cents - MIN_CHARGE_CENTS)
        return Money(available, price.currency)

    # ----------------------------- Saldo ---------------------------------

    def balance_after(self, entry: CreditEntry) -> tuple[Money, Money]:
        """(saldo, deuda) resultantes de aplicar `entry`, sin aplicarlo.

        Un abono salda primero la deuda. Un cargo que no cabe en el saldo falla, salvo
        una devolucion del banco (`CHARGEBACK`): lo que falte pasa a deuda.
        """
        if entry.professional_id != self.professional_id:
            raise ValidationError("El movimiento pertenece a otra cuenta")
        if entry.amount.currency != self.currency:
            raise CurrencyMismatchError("El movimiento esta en otra divisa que el saldo")
        net = self.balance.amount_cents - self.debt_cents + entry.signed_cents
        # Un abono nunca falla, aunque no llegue a saldar toda la deuda.
        if entry.amount.amount_cents > self.balance.amount_cents and not (
            entry.kind.is_credit or entry.kind.may_create_debt
        ):
            raise InsufficientCreditError()
        return Money(max(net, 0), self.currency), Money(max(-net, 0), self.currency)

    def apply(self, entry: CreditEntry) -> None:
        balance, debt = self.balance_after(entry)
        self.balance = balance
        self.debt_cents = debt.amount_cents

    # ----------------------------- Suscripcion ---------------------------

    def attach_customer(self, customer_id: str) -> None:
        if not customer_id.strip():
            raise ValidationError("Identificador de cliente de la pasarela vacio")
        self.stripe_customer_id = customer_id

    def _is_stale(self, at: datetime) -> bool:
        return self.status_synced_at is not None and at < self.status_synced_at

    def _mark_synced(self, at: datetime) -> None:
        self.status_synced_at = at

    def record_checkout_completed(self, *, subscription_id: str | None, at: datetime) -> None:
        """El profesional completo el checkout; el cobro puede seguir pendiente (SEPA)."""
        if subscription_id:
            self.stripe_subscription_id = subscription_id
        if self._is_stale(at):
            return
        # Si el cobro ya llego (el orden de eventos no esta garantizado) no se
        # retrocede a pendiente.
        if self.subscription_status in {SubscriptionStatus.NONE, SubscriptionStatus.CANCELED}:
            self.subscription_status = SubscriptionStatus.PENDING
            self._mark_synced(at)

    def record_invoice_paid(
        self, *, subscription_id: str | None, period_end: datetime | None, at: datetime
    ) -> None:
        """Cobro de la recarga confirmado: la cuenta queda al dia."""
        if subscription_id:
            self.stripe_subscription_id = subscription_id
        if period_end is not None and (
            self.current_period_end is None or period_end > self.current_period_end
        ):
            self.current_period_end = period_end
        if self._is_stale(at):
            # Ya se aplico un evento posterior. Solo manda si dice algo que este cobro
            # no resuelve: cancelada, o un cobro fallido despues. Un PENDING es
            # justo "suscripcion viva sin cobro confirmado" (`sync_subscription` no
            # activa) y este evento es ese cobro: Stripe no garantiza el orden y el
            # `subscription.created` suele llegar antes que el `invoice.paid`.
            if self.subscription_status is SubscriptionStatus.PENDING:
                # Sin mover `status_synced_at` atras: lo siguiente se compara con el
                # evento mas reciente.
                self.subscription_status = SubscriptionStatus.ACTIVE
            return
        self.subscription_status = SubscriptionStatus.ACTIVE
        self._mark_synced(at)

    def record_payment_failed(self, *, at: datetime) -> None:
        """Fallo el cobro: sin recarga al dia no se compra."""
        if self._is_stale(at):
            return
        if self.subscription_status is not SubscriptionStatus.CANCELED:
            self.subscription_status = SubscriptionStatus.PAST_DUE
            self._mark_synced(at)

    def sync_subscription(
        self,
        *,
        status: SubscriptionStatus,
        subscription_id: str | None,
        period_end: datetime | None,
        at: datetime,
    ) -> None:
        """Replica el estado que la pasarela reporta para la suscripcion.

        Solo un cobro confirmado (`record_invoice_paid`) activa la cuenta. Con SEPA
        la pasarela marca la suscripcion como activa mientras el adeudo aun se
        procesa, y "al dia con la recarga" significa dinero recibido; por eso aqui
        un `ACTIVE` solo mantiene una cuenta que ya lo estaba.
        """
        if self._is_stale(at):
            return
        if subscription_id:
            self.stripe_subscription_id = subscription_id
        if period_end is not None:
            self.current_period_end = period_end
        if status is SubscriptionStatus.ACTIVE and (
            self.subscription_status is not SubscriptionStatus.ACTIVE
        ):
            status = SubscriptionStatus.PENDING
        # Una suscripcion nunca vuelve a "incompleta" tras cobrarse. Si llega un
        # PENDING sobre una cuenta activa es el `subscription.created` emitido en el
        # mismo segundo que el cobro, procesado despues: no debe desactivarla.
        if status is SubscriptionStatus.PENDING and (
            self.subscription_status is SubscriptionStatus.ACTIVE
        ):
            return
        self.subscription_status = status
        self._mark_synced(at)


# Tope de la mensualidad: red contra el error de tecleo del admin (100000 = 1000 EUR).
MAX_SUBSCRIPTION_CENTS = 100_000


@dataclass(frozen=True, slots=True)
class SubscriptionPrice:
    """Importe de la mensualidad fijado por el admin, con su precio en la pasarela.

    Es append-only: cambiar la mensualidad crea una fila nueva y la vigente es la
    mas reciente. Las suscripciones ya creadas conservan el precio con el que
    empezaron; la nueva solo aplica a quien se suscriba despues.
    """

    id: UUID
    amount: Money
    stripe_price_id: str
    created_at: datetime
    created_by_user_id: UUID | None = None

    def __post_init__(self) -> None:
        assert_valid_subscription_amount(self.amount)
        if not self.stripe_price_id.strip():
            raise ValidationError("La mensualidad necesita su precio en la pasarela")


def assert_valid_subscription_amount(amount: Money) -> None:
    if not MIN_CHARGE_CENTS <= amount.amount_cents <= MAX_SUBSCRIPTION_CENTS:
        raise ValidationError(
            f"La mensualidad debe estar entre {MIN_CHARGE_CENTS} y "
            f"{MAX_SUBSCRIPTION_CENTS} centimos"
        )
