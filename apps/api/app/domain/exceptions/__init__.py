"""Excepciones de negocio.

Cada una lleva un `code` estable que el middleware de errores traduce a un status
HTTP y que el frontend usa para elegir el mensaje traducido. El dominio nunca
conoce HTTP: solo declara el codigo.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base de todos los errores de negocio."""

    code = "DOMAIN_ERROR"
    status = 400

    def __init__(self, message: str | None = None, **details: object) -> None:
        super().__init__(message or self.__class__.__doc__ or self.code)
        self.message = message or (self.__class__.__doc__ or self.code).strip()
        self.details = details


class NotFoundError(DomainError):
    """El recurso solicitado no existe."""

    code = "NOT_FOUND"
    status = 404


class ValidationError(DomainError):
    """Los datos recibidos no cumplen las reglas de negocio."""

    code = "VALIDATION_ERROR"
    status = 422


class PermissionDeniedError(DomainError):
    """No tienes permiso para realizar esta accion."""

    code = "PERMISSION_DENIED"
    status = 403


# --------------------------- Leads y compras -----------------------------


class LeadNotFoundError(NotFoundError):
    """La solicitud no existe o ya no esta disponible."""

    code = "LEAD_NOT_FOUND"


class LeadNotPurchasableError(DomainError):
    """La solicitud no esta disponible para compra."""

    code = "LEAD_NOT_PURCHASABLE"
    status = 409


class LeadCapReachedError(LeadNotPurchasableError):
    """Esta solicitud ya alcanzo el maximo de profesionales que pueden comprarla."""

    code = "LEAD_CAP_REACHED"


class LeadAlreadyPurchasedError(LeadNotPurchasableError):
    """Ya compraste el contacto de esta solicitud."""

    code = "LEAD_ALREADY_PURCHASED"


class CategoryMismatchError(LeadNotPurchasableError):
    """La solicitud no pertenece a ninguno de tus oficios."""

    code = "CATEGORY_MISMATCH"


class ContactLockedError(PermissionDeniedError):
    """Debes comprar el contacto antes de ver los datos del cliente."""

    code = "CONTACT_LOCKED"


class PurchaseNotFoundError(NotFoundError):
    """La compra no existe."""

    code = "PURCHASE_NOT_FOUND"


class PurchaseNotPayableError(DomainError):
    """La compra no se encuentra en un estado que admita confirmacion de pago."""

    code = "PURCHASE_NOT_PAYABLE"
    status = 409


# --------------------------- Perfiles y catalogo -------------------------


class ProfessionalProfileIncompleteError(DomainError):
    """Completa tu perfil (zona y oficios) antes de continuar."""

    code = "PROFILE_INCOMPLETE"
    status = 409


class ProfessionalNotFoundError(NotFoundError):
    """El profesional no existe."""

    code = "PROFESSIONAL_NOT_FOUND"


class CategoryNotFoundError(NotFoundError):
    """La categoria de oficio no existe o esta inactiva."""

    code = "CATEGORY_NOT_FOUND"


class UnknownPostalCodeError(ValidationError):
    """No reconocemos ese codigo postal."""

    code = "UNKNOWN_POSTAL_CODE"


class ConsentRequiredError(ValidationError):
    """Debes aceptar la politica de privacidad para publicar la solicitud."""

    code = "CONSENT_REQUIRED"


class PaymentGatewayError(DomainError):
    """No hemos podido iniciar el pago. Intentalo de nuevo en unos minutos."""

    code = "PAYMENT_GATEWAY_ERROR"
    status = 503


class AuthenticationError(DomainError):
    """Credenciales invalidas o token expirado."""

    code = "UNAUTHENTICATED"
    status = 401


__all__ = [
    "AuthenticationError",
    "CategoryMismatchError",
    "CategoryNotFoundError",
    "ConsentRequiredError",
    "ContactLockedError",
    "DomainError",
    "LeadAlreadyPurchasedError",
    "LeadCapReachedError",
    "LeadNotFoundError",
    "LeadNotPurchasableError",
    "NotFoundError",
    "PaymentGatewayError",
    "PermissionDeniedError",
    "ProfessionalNotFoundError",
    "ProfessionalProfileIncompleteError",
    "PurchaseNotFoundError",
    "PurchaseNotPayableError",
    "UnknownPostalCodeError",
    "ValidationError",
]
