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

    VERIFICATION_REFUND = "verification_refund"
    """Retirada del saldo del primer cobro, reembolsado al rechazar la validacion."""

    CHARGEBACK = "chargeback"
    """Retirada de una recarga que el banco devolvio (adeudo SEPA devuelto o disputa).

    Es el unico cargo que puede superar el saldo: el dinero ya salio de nuestra cuenta
    aunque el profesional haya gastado el saldo, y lo que falte queda como deuda."""

    CHARGEBACK_REVERSAL = "chargeback_reversal"
    """La pasarela nos devolvio el importe de una devolucion (disputa ganada)."""

    @property
    def is_credit(self) -> bool:
        return self in {
            CreditEntryKind.TOPUP,
            CreditEntryKind.SPEND_REVERSAL,
            CreditEntryKind.ADJUSTMENT_CREDIT,
            CreditEntryKind.CHARGEBACK_REVERSAL,
        }

    @property
    def may_create_debt(self) -> bool:
        return self is CreditEntryKind.CHARGEBACK


class PropertyType(StrEnum):
    """Tipo de inmueble de la solicitud (formulario F01, paso 2)."""

    FLAT = "flat"
    HOUSE = "house"
    COMMERCIAL = "commercial"
    OFFICE = "office"
    COMMUNITY = "community"
    INDUSTRIAL = "industrial"
    LAND = "land"


class ProjectSchedule(StrEnum):
    """Respuesta a "Cual es la programacion actual de tu proyecto?" (el plazo)."""

    ASAP = "asap"
    WITHIN_WEEKS = "within_weeks"
    """En 2-4 semanas."""

    WITHIN_MONTHS = "within_months"
    """En 1-3 meses."""

    GATHERING_QUOTES = "gathering_quotes"
    """Solo esta pidiendo precios."""


class ProfessionalType(StrEnum):
    """Como se da de alta el profesional (F02). Decide que documentos aporta."""

    SELF_EMPLOYED = "self_employed"
    """Autonomo: modelos de alta de la Agencia Tributaria."""

    COMPANY = "company"
    """Empresa: modelos de alta de la Agencia Tributaria."""

    INDEPENDENT = "independent"
    """Trabajador independiente: documento de identidad (DNI, TIE o pasaporte)."""


class VerificationStatus(StrEnum):
    INCOMPLETE = "incomplete"
    """Faltan datos o documentos; aun no se ha enviado a revision."""

    PENDING = "pending"
    """En revision por el admin. Ve solicitudes, no compra."""

    APPROVED = "approved"

    REJECTED = "rejected"
    """Rechazado: se reembolsa el primer cobro y se cancela la recarga."""


class DocumentKind(StrEnum):
    TAX_REGISTRATION = "tax_registration"
    """Modelos de la Agencia Tributaria (036/037, alta censal)."""

    IDENTITY = "identity"
    """DNI, TIE o pasaporte."""
