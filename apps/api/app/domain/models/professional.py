"""Entidades de usuario y profesional."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.exceptions import (
    ProfessionalNotApprovedError,
    ProfessionalProfileIncompleteError,
    ProfessionalRejectedError,
    ValidationError,
    VerificationLockedError,
    VerificationTransitionError,
)
from app.domain.models.enums import (
    DocumentKind,
    ProfessionalType,
    UserRole,
    VerificationStatus,
)
from app.domain.value_objects import Coordinates, Email, PhoneNumber, PostalCode, TaxId

MIN_SERVICE_RADIUS_KM = 1
MAX_SERVICE_RADIUS_KM = 300


@dataclass(slots=True)
class User:
    """Cuenta de la plataforma. La autenticacion la delega a Firebase.

    Guardamos el `firebase_uid` como identidad externa y mantenemos nuestro propio
    `id` para que el resto del dominio no dependa del proveedor de auth.
    """

    id: UUID
    firebase_uid: str
    email: Email
    role: UserRole
    created_at: datetime
    display_name: str | None = None

    def __post_init__(self) -> None:
        if not self.firebase_uid.strip():
            raise ValidationError("firebase_uid es obligatorio")

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN


MAX_WORK_PHOTOS = 8
MAX_DOCUMENTS = 10
MAX_REJECTION_REASON = 1000

# Que documentos exige cada tipo de alta (F02): autonomos y empresas, los modelos de
# la Agencia Tributaria; el trabajador independiente, su documento de identidad.
REQUIRED_DOCUMENT: dict[ProfessionalType, DocumentKind] = {
    ProfessionalType.SELF_EMPLOYED: DocumentKind.TAX_REGISTRATION,
    ProfessionalType.COMPANY: DocumentKind.TAX_REGISTRATION,
    ProfessionalType.INDEPENDENT: DocumentKind.IDENTITY,
}


@dataclass(frozen=True, slots=True)
class ProfessionalDocument:
    """Documento de alta. Vive en el bucket privado: solo lo abre el admin."""

    id: UUID
    kind: DocumentKind
    storage_key: str
    filename: str
    uploaded_at: datetime


@dataclass(frozen=True, slots=True)
class VerificationEvent:
    """Cambio de estado de la validacion. Append-only: es la auditoria del admin."""

    id: UUID
    professional_id: UUID
    from_status: VerificationStatus
    to_status: VerificationStatus
    created_at: datetime
    actor_user_id: UUID | None = None
    """`None` si lo hizo el propio profesional (enviar a revision)."""
    note: str | None = None


@dataclass(slots=True)
class Professional:
    """Perfil profesional: QUE oficios hace, DONDE trabaja y si esta validado."""

    id: UUID
    user_id: UUID
    business_name: str
    phone: PhoneNumber
    base_postal_code: PostalCode
    base_coordinates: Coordinates
    service_radius_km: int
    created_at: datetime
    city: str | None = None
    province: str | None = None
    category_ids: set[UUID] = field(default_factory=set)
    service_ids: set[UUID] = field(default_factory=set)
    """Servicios concretos que ofrece dentro de sus oficios. Vacio en un oficio = todos."""

    # --- Alta (F02) ---
    professional_type: ProfessionalType | None = None
    legal_name: str | None = None
    """Razon social, o nombre y apellidos si es persona fisica. Se factura a este nombre."""
    tax_id: TaxId | None = None
    address: str | None = None
    """Direccion de la empresa o domicilio."""
    profile_photo_key: str | None = None
    logo_key: str | None = None
    work_photo_keys: list[str] = field(default_factory=list)
    documents: list[ProfessionalDocument] = field(default_factory=list)

    # --- Validacion ---
    verification_status: VerificationStatus = VerificationStatus.INCOMPLETE
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        self.business_name = self.business_name.strip()
        if not self.business_name:
            raise ValidationError("El nombre comercial es obligatorio")
        if not MIN_SERVICE_RADIUS_KM <= self.service_radius_km <= MAX_SERVICE_RADIUS_KM:
            raise ValidationError(
                f"El radio de servicio debe estar entre {MIN_SERVICE_RADIUS_KM} y "
                f"{MAX_SERVICE_RADIUS_KM} km"
            )
        self.legal_name = (self.legal_name or "").strip() or None
        self.address = (self.address or "").strip() or None
        if len(self.work_photo_keys) > MAX_WORK_PHOTOS:
            raise ValidationError(f"Maximo {MAX_WORK_PHOTOS} fotos de trabajos")
        if len(self.documents) > MAX_DOCUMENTS:
            raise ValidationError(f"Maximo {MAX_DOCUMENTS} documentos")
        if (
            self.tax_id is not None
            and self.professional_type is ProfessionalType.COMPANY
            and not self.tax_id.is_company
        ):
            raise ValidationError("Una empresa se identifica con su CIF")

    # ----------------------------- Consultas -----------------------------

    @property
    def is_ready_to_browse(self) -> bool:
        """Sin oficios declarados no hay nada que mostrarle en el explorador."""
        return bool(self.category_ids)

    @property
    def is_approved(self) -> bool:
        return self.verification_status is VerificationStatus.APPROVED

    def assert_ready_to_browse(self) -> None:
        # Un rechazado queda fuera de la plataforma: se le reembolso y se cancelo
        # su recarga. El resto ve solicitudes aunque todavia no pueda comprar.
        if self.verification_status is VerificationStatus.REJECTED:
            raise ProfessionalRejectedError()
        if not self.is_ready_to_browse:
            raise ProfessionalProfileIncompleteError(
                "Selecciona al menos un oficio para ver solicitudes"
            )

    def assert_can_purchase(self) -> None:
        """Compra solo quien esta aprobado (F02). La recarga se comprueba aparte."""
        self.assert_ready_to_browse()
        if not self.is_approved:
            raise ProfessionalNotApprovedError()

    def missing_for_review(self) -> list[str]:
        """Lo que falta para poder enviar el alta a revision, como claves estables.

        El frontend las traduce; el admin nunca recibe un expediente a medias.
        """
        missing: list[str] = []
        if not self.category_ids:
            missing.append("categories")
        if self.professional_type is None:
            missing.append("professional_type")
        if self.legal_name is None:
            missing.append("legal_name")
        if self.tax_id is None and self.professional_type is not ProfessionalType.INDEPENDENT:
            # El independiente puede identificarse con pasaporte, que no es un NIF.
            missing.append("tax_id")
        if self.address is None:
            missing.append("address")
        required = REQUIRED_DOCUMENT.get(self.professional_type) if self.professional_type else None
        if required is not None and not any(d.kind is required for d in self.documents):
            missing.append(f"document_{required.value}")
        return missing

    def covers(self, coordinates: Coordinates) -> bool:
        """Comprobacion en memoria del radio de cobertura.

        El filtrado real de listados lo hace PostGIS; esto sirve para validaciones
        puntuales y para los tests de dominio.
        """
        return self.base_coordinates.distance_km_to(coordinates) <= self.service_radius_km

    def serves_category(self, category_id: UUID) -> bool:
        return category_id in self.category_ids

    # ----------------------------- Alta ----------------------------------

    @property
    def identity_locked(self) -> bool:
        """Enviado el alta, tipo, razon social y NIF quedan fijos: es lo que se valido."""
        return self.verification_status is not VerificationStatus.INCOMPLETE

    def set_identity(
        self,
        *,
        professional_type: ProfessionalType | None,
        legal_name: str | None,
        tax_id: TaxId | None,
    ) -> None:
        unchanged = (
            professional_type == self.professional_type
            and (legal_name or "").strip() == (self.legal_name or "")
            and tax_id == self.tax_id
        )
        if unchanged:
            return
        if self.identity_locked:
            raise VerificationLockedError()
        self.professional_type = professional_type
        self.legal_name = legal_name
        self.tax_id = tax_id
        self.__post_init__()

    def add_document(self, document: ProfessionalDocument) -> None:
        if self.identity_locked:
            raise VerificationLockedError()
        if len(self.documents) >= MAX_DOCUMENTS:
            raise ValidationError(f"Maximo {MAX_DOCUMENTS} documentos")
        self.documents.append(document)

    def remove_document(self, document_id: UUID) -> ProfessionalDocument:
        if self.identity_locked:
            raise VerificationLockedError()
        document = next((d for d in self.documents if d.id == document_id), None)
        if document is None:
            raise ValidationError("El documento no existe")
        self.documents.remove(document)
        return document

    # ----------------------------- Validacion ----------------------------

    def _transition(
        self,
        to: VerificationStatus,
        *,
        allowed_from: set[VerificationStatus],
        event_id: UUID,
        now: datetime,
        actor_user_id: UUID | None,
        note: str | None = None,
    ) -> VerificationEvent:
        if self.verification_status not in allowed_from:
            raise VerificationTransitionError(
                f"No se puede pasar de {self.verification_status} a {to}"
            )
        event = VerificationEvent(
            id=event_id,
            professional_id=self.id,
            from_status=self.verification_status,
            to_status=to,
            created_at=now,
            actor_user_id=actor_user_id,
            note=note,
        )
        self.verification_status = to
        return event

    def submit_for_review(self, *, event_id: UUID, now: datetime) -> VerificationEvent:
        missing = self.missing_for_review()
        if missing:
            raise ProfessionalProfileIncompleteError(
                "Faltan datos para enviar el alta a revision", missing=missing
            )
        event = self._transition(
            VerificationStatus.PENDING,
            allowed_from={VerificationStatus.INCOMPLETE},
            event_id=event_id,
            now=now,
            actor_user_id=None,
        )
        self.submitted_at = now
        return event

    def approve(self, *, event_id: UUID, now: datetime, admin_user_id: UUID) -> VerificationEvent:
        event = self._transition(
            VerificationStatus.APPROVED,
            allowed_from={VerificationStatus.PENDING},
            event_id=event_id,
            now=now,
            actor_user_id=admin_user_id,
        )
        self.reviewed_at = now
        self.rejection_reason = None
        return event

    def reject(
        self, *, event_id: UUID, now: datetime, admin_user_id: UUID, reason: str
    ) -> VerificationEvent:
        reason = reason.strip()
        if not reason:
            raise ValidationError("Indica el motivo del rechazo")
        if len(reason) > MAX_REJECTION_REASON:
            raise ValidationError(f"El motivo no puede superar {MAX_REJECTION_REASON} caracteres")
        event = self._transition(
            VerificationStatus.REJECTED,
            allowed_from={VerificationStatus.PENDING},
            event_id=event_id,
            now=now,
            actor_user_id=admin_user_id,
            note=reason,
        )
        self.reviewed_at = now
        self.rejection_reason = reason
        return event
