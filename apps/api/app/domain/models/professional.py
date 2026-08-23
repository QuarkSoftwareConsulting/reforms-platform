"""Entidades de usuario y profesional."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.exceptions import ProfessionalProfileIncompleteError, ValidationError
from app.domain.models.enums import UserRole
from app.domain.value_objects import Coordinates, Email, PhoneNumber, PostalCode

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


@dataclass(slots=True)
class Professional:
    """Perfil profesional: define QUE oficios hace y DONDE trabaja."""

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

    def __post_init__(self) -> None:
        self.business_name = self.business_name.strip()
        if not self.business_name:
            raise ValidationError("El nombre comercial es obligatorio")
        if not MIN_SERVICE_RADIUS_KM <= self.service_radius_km <= MAX_SERVICE_RADIUS_KM:
            raise ValidationError(
                f"El radio de servicio debe estar entre {MIN_SERVICE_RADIUS_KM} y "
                f"{MAX_SERVICE_RADIUS_KM} km"
            )

    @property
    def is_ready_to_browse(self) -> bool:
        """Sin oficios declarados no hay nada que mostrarle en el explorador."""
        return bool(self.category_ids)

    def assert_ready_to_browse(self) -> None:
        if not self.is_ready_to_browse:
            raise ProfessionalProfileIncompleteError(
                "Selecciona al menos un oficio para ver solicitudes"
            )

    def covers(self, coordinates: Coordinates) -> bool:
        """Comprobacion en memoria del radio de cobertura.

        El filtrado real de listados lo hace PostGIS; esto sirve para validaciones
        puntuales y para los tests de dominio.
        """
        return self.base_coordinates.distance_km_to(coordinates) <= self.service_radius_km

    def serves_category(self, category_id: UUID) -> bool:
        return category_id in self.category_ids
