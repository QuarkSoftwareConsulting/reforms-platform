"""Enumeraciones del dominio."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    PROFESSIONAL = "professional"
    ADMIN = "admin"


class LeadStatus(StrEnum):
    PUBLISHED = "published"
    """Visible en el explorador y comprable."""

    EXHAUSTED = "exhausted"
    """Alcanzo el maximo de compras; sigue visible como historico pero no se vende."""

    DISABLED = "disabled"
    """Retirado por el admin (duplicado, fraude, cliente que se dio de baja)."""


class LeadSource(StrEnum):
    ORGANIC = "organic"
    """Publicado por el propio cliente desde el formulario web."""

    ADMIN = "admin"
    """Introducido a mano por el admin desde campanas de marketing."""


class PurchaseStatus(StrEnum):
    RESERVED = "reserved"
    """Plaza reservada mientras el profesional completa el pago en Stripe."""

    PAID = "paid"
    """Pago confirmado por webhook: el contacto queda desbloqueado."""

    EXPIRED = "expired"
    """El checkout caduco sin pagar y la plaza se libero."""

    FAILED = "failed"
    """Stripe reporto un pago fallido."""

    REFUNDED = "refunded"
    """El admin devolvio el importe; la plaza no se reutiliza."""

    @property
    def occupies_slot(self) -> bool:
        """Estados que consumen una de las plazas del lead."""
        return self in {PurchaseStatus.RESERVED, PurchaseStatus.PAID, PurchaseStatus.REFUNDED}

    @property
    def unlocks_contact(self) -> bool:
        """Solo un pago confirmado da acceso a los datos del cliente."""
        return self is PurchaseStatus.PAID


class SubscriptionStatus(StrEnum):
    """Estado de la recarga mensual que mantiene activa la cuenta del profesional."""

    NONE = "none"
    """Nunca se ha suscrito (o la cuenta aun no tiene cliente en la pasarela)."""

    PENDING = "pending"
    """Checkout completado pero el primer cobro no esta confirmado (SEPA tarda dias)."""

    ACTIVE = "active"
    """Al dia con la recarga: puede comprar contactos."""

    PAST_DUE = "past_due"
    """Fallo el cobro de la recarga: puede ver solicitudes pero no comprar."""

    CANCELED = "canceled"
    """Suscripcion cancelada. El saldo se conserva pero no se puede gastar."""


class CreditEntryKind(StrEnum):
    """Movimientos del libro de saldo. El signo lo decide el tipo, no el importe."""

    TOPUP = "topup"
    """Recarga mensual cobrada y confirmada por la pasarela."""

    SPEND = "spend"
    """Saldo aplicado a la compra de un contacto."""

    SPEND_REVERSAL = "spend_reversal"
    """Devolucion del saldo de una reserva que caduco o fallo sin completarse."""

    ADJUSTMENT_CREDIT = "adjustment_credit"
    """Abono manual del admin (p. ej. compensar un lead problematico)."""

    ADJUSTMENT_DEBIT = "adjustment_debit"
    """Cargo manual del admin."""

    @property
    def is_credit(self) -> bool:
        return self in {
            CreditEntryKind.TOPUP,
            CreditEntryKind.SPEND_REVERSAL,
            CreditEntryKind.ADJUSTMENT_CREDIT,
        }
