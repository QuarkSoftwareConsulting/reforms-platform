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


class ProfessionalNotApprovedError(DomainError):
    """Tu perfil todavia no esta aprobado: podras comprar contactos cuando lo validemos."""

    code = "PROFESSIONAL_NOT_APPROVED"
    status = 403


class ProfessionalRejectedError(DomainError):
    """Tu solicitud de alta fue rechazada."""

    code = "PROFESSIONAL_REJECTED"
    status = 403


class VerificationTransitionError(DomainError):
    """Ese cambio de estado de la validacion no es posible ahora."""

    code = "INVALID_VERIFICATION_TRANSITION"
    status = 409


class RejectionAwaitingPaymentError(DomainError):
    """El primer cobro de la recarga sigue en proceso: no se puede rechazar todavia.

    Un adeudo SEPA en proceso no se puede anular: se confirmaria despues del rechazo,
    abonando saldo a un rechazado sin que nadie lo reembolse.
    """

    code = "REJECTION_AWAITING_PAYMENT"
    status = 409


class VerificationLockedError(DomainError):
    """Estos datos ya se enviaron a revision y no se pueden cambiar."""

    code = "VERIFICATION_LOCKED"
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


class InvalidTaxIdError(ValidationError):
    """El NIF, NIE o CIF no es valido: revisa la letra o el digito de control."""

    code = "INVALID_TAX_ID"


class InvalidServiceError(ValidationError):
    """El servicio elegido no pertenece a la categoria de la solicitud."""

    code = "INVALID_SERVICE"


class PostalCodeNotCoveredError(ValidationError):
    """Todavia no damos servicio en ese codigo postal."""

    code = "POSTAL_CODE_NOT_COVERED"


class InvalidSalePriceError(ValidationError):
    """El precio de venta indicado no es valido."""

    code = "INVALID_SALE_PRICE"


class CurrencyMismatchError(ValidationError):
    """El precio debe estar en la misma divisa que el oficio."""

    code = "CURRENCY_MISMATCH"


class ConsentRequiredError(ValidationError):
    """Debes aceptar la politica de privacidad para publicar la solicitud."""

    code = "CONSENT_REQUIRED"


# --------------------------- Recarga y saldo -----------------------------


class SubscriptionRequiredError(DomainError):
    """Activa la recarga mensual para poder comprar contactos."""

    code = "SUBSCRIPTION_REQUIRED"
    status = 402


class SubscriptionAlreadyExistsError(DomainError):
    """Ya tienes una recarga mensual en curso. Gestionala desde tu cuenta."""

    code = "SUBSCRIPTION_ALREADY_EXISTS"
    status = 409


class InsufficientCreditError(DomainError):
    """No tienes saldo suficiente para esta operacion."""

    code = "INSUFFICIENT_CREDIT"
    status = 409


class ProfessionalAccountNotFoundError(NotFoundError):
    """No encontramos la cuenta de recarga del profesional."""

    code = "ACCOUNT_NOT_FOUND"


class PhoneNotMobileError(ValidationError):
    """Para verificar el telefono por SMS hace falta un movil espanol."""

    code = "PHONE_NOT_MOBILE"


class PhoneNotVerifiedError(ValidationError):
    """El codigo de verificacion del telefono no es correcto o ha caducado."""

    code = "PHONE_NOT_VERIFIED"


class TooManyVerificationAttemptsError(DomainError):
    """Demasiados codigos pedidos para este telefono. Prueba mas tarde."""

    code = "TOO_MANY_VERIFICATION_ATTEMPTS"
    status = 429


class PhoneVerificationUnavailableError(DomainError):
    """No hemos podido enviar el SMS de verificacion."""

    code = "PHONE_VERIFICATION_UNAVAILABLE"
    status = 503


class PaymentGatewayError(DomainError):
    """No hemos podido iniciar el pago. Intentalo de nuevo en unos minutos."""

    code = "PAYMENT_GATEWAY_ERROR"
    status = 503


class AuthenticationError(DomainError):
    """Credenciales invalidas o token expirado."""

    code = "UNAUTHENTICATED"
    status = 401


# ------------------------------- Roles ------------------------------------


class UserNotFoundError(NotFoundError):
    """El usuario no existe."""

    code = "USER_NOT_FOUND"


class CannotChangeOwnRoleError(DomainError):
    """Un admin no puede cambiar su propio rol: lo hace otro admin."""

    code = "CANNOT_CHANGE_OWN_ROLE"
    status = 409


class LastAdminError(DomainError):
    """No se puede degradar al ultimo admin: nadie podria gestionar la plataforma."""

    code = "LAST_ADMIN"
    status = 409


__all__ = [
    "AuthenticationError",
    "CannotChangeOwnRoleError",
    "CategoryMismatchError",
    "CategoryNotFoundError",
    "ConsentRequiredError",
    "ContactLockedError",
    "CurrencyMismatchError",
    "DomainError",
    "InsufficientCreditError",
    "InvalidSalePriceError",
    "InvalidServiceError",
    "InvalidTaxIdError",
    "LastAdminError",
    "LeadAlreadyPurchasedError",
    "LeadCapReachedError",
    "LeadNotFoundError",
    "LeadNotPurchasableError",
    "NotFoundError",
    "PaymentGatewayError",
    "PermissionDeniedError",
    "PhoneNotMobileError",
    "PhoneNotVerifiedError",
    "PhoneVerificationUnavailableError",
    "PostalCodeNotCoveredError",
    "ProfessionalAccountNotFoundError",
    "ProfessionalNotApprovedError",
    "ProfessionalNotFoundError",
    "ProfessionalProfileIncompleteError",
    "ProfessionalRejectedError",
    "PurchaseNotFoundError",
    "PurchaseNotPayableError",
    "RejectionAwaitingPaymentError",
    "SubscriptionAlreadyExistsError",
    "SubscriptionRequiredError",
    "TooManyVerificationAttemptsError",
    "UnknownPostalCodeError",
    "UserNotFoundError",
    "ValidationError",
    "VerificationLockedError",
    "VerificationTransitionError",
]
