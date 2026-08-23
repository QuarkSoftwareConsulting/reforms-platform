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
