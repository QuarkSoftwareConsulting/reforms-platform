"""Puertos de persistencia.

El dominio y los casos de uso solo conocen estas interfaces; la implementacion
concreta con SQLAlchemy/PostGIS vive en infrastructure/adapters/db.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.models import Category, Lead, Professional, Purchase, User
from app.domain.value_objects import Coordinates, PostalCode


@dataclass(frozen=True, slots=True)
class PostalCodeInfo:
    """Fila del catalogo de codigos postales usada para geolocalizar sin geocoder."""

    code: PostalCode
    city: str
    province: str
    coordinates: Coordinates


@dataclass(frozen=True, slots=True)
class LeadSearchFilters:
    """Filtros del explorador de proyectos."""

    category_ids: set[UUID] | None = None
    center: Coordinates | None = None
    radius_km: int | None = None
    province: str | None = None
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class LeadSearchRow:
    """Resultado de busqueda: el lead mas los datos derivados que necesita la UI."""

    lead: Lead
    distance_km: float | None
    purchased_by_requester: bool


class LeadRepositoryPort(ABC):
    @abstractmethod
    async def add(self, lead: Lead) -> Lead: ...

    @abstractmethod
    async def get(self, lead_id: UUID) -> Lead | None: ...

    @abstractmethod
    async def get_for_update(self, lead_id: UUID) -> Lead | None:
        """Carga el lead con `SELECT ... FOR UPDATE`.

        Es la pieza que serializa las compras concurrentes: sin este bloqueo dos
        profesionales podrian pasar la validacion del cap a la vez.
        """

    @abstractmethod
    async def update(self, lead: Lead) -> Lead: ...

    @abstractmethod
    async def search(
        self, filters: LeadSearchFilters, *, requester_professional_id: UUID | None = None
    ) -> list[LeadSearchRow]: ...

    @abstractmethod
    async def count(self, filters: LeadSearchFilters) -> int: ...


class PurchaseRepositoryPort(ABC):
    @abstractmethod
    async def add(self, purchase: Purchase) -> Purchase: ...

    @abstractmethod
    async def get(self, purchase_id: UUID) -> Purchase | None: ...

    @abstractmethod
    async def get_by_checkout_session(self, session_id: str) -> Purchase | None: ...

    @abstractmethod
    async def update(self, purchase: Purchase) -> Purchase: ...

    @abstractmethod
    async def count_occupied_slots(self, lead_id: UUID, *, now: datetime) -> int:
        """Plazas vivas del lead: pagadas, reembolsadas y reservas no caducadas."""

    @abstractmethod
    async def find_active_for_lead_and_professional(
        self, lead_id: UUID, professional_id: UUID, *, now: datetime
    ) -> Purchase | None:
        """Compra vigente del profesional sobre ese lead (para no venderle dos veces)."""

    @abstractmethod
    async def list_for_professional(
        self, professional_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Purchase]: ...

    @abstractmethod
    async def list_expired_reservations(self, *, now: datetime, limit: int = 100) -> list[Purchase]:
        """Reservas cuyo TTL caduco y cuyas plazas hay que liberar."""

    @abstractmethod
    async def has_paid_purchase(self, lead_id: UUID, professional_id: UUID) -> bool: ...


class UserRepositoryPort(ABC):
    @abstractmethod
    async def add(self, user: User) -> User: ...

    @abstractmethod
    async def get_by_firebase_uid(self, firebase_uid: str) -> User | None: ...

    @abstractmethod
    async def update(self, user: User) -> User: ...


class ProfessionalRepositoryPort(ABC):
    @abstractmethod
    async def add(self, professional: Professional) -> Professional: ...

    @abstractmethod
    async def get(self, professional_id: UUID) -> Professional | None: ...

    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> Professional | None: ...

    @abstractmethod
    async def update(self, professional: Professional) -> Professional: ...


class CategoryRepositoryPort(ABC):
    @abstractmethod
    async def list_active(self) -> list[Category]: ...

    @abstractmethod
    async def get(self, category_id: UUID) -> Category | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Category | None: ...

    @abstractmethod
    async def get_many(self, category_ids: set[UUID]) -> list[Category]: ...


class PostalCodeRepositoryPort(ABC):
    @abstractmethod
    async def get(self, code: PostalCode) -> PostalCodeInfo | None: ...


class ProcessedEventRepositoryPort(ABC):
    """Registro de eventos de pasarela ya procesados (idempotencia del webhook)."""

    @abstractmethod
    async def mark_processed(
        self, event_id: str, event_type: str, payload: dict[str, object]
    ) -> bool:
        """Registra el evento y devuelve True si es la primera vez que se ve.

        Si devuelve False el evento ya se proceso y el caso de uso debe abortar sin
        repetir efectos.
        """
