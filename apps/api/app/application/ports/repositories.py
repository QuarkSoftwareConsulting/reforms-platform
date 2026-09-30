"""Puertos de persistencia.

El dominio y los casos de uso solo conocen estas interfaces; la implementacion
concreta con SQLAlchemy/PostGIS vive en infrastructure/adapters/db.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.models import (
    Category,
    CreditEntry,
    Lead,
    LeadSource,
    LeadStatus,
    Professional,
    ProfessionalAccount,
    Purchase,
    PurchaseReview,
    SubscriptionPrice,
    User,
    VerificationEvent,
    VerificationStatus,
)
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
    service_ids: frozenset[UUID] = frozenset()
    """Servicios que ofrece el profesional."""
    restricted_category_ids: frozenset[UUID] = frozenset()
    """Oficios en los que el profesional eligio servicios concretos.

    En esos oficios solo ve las solicitudes de sus servicios o las que no indican
    ninguno; en el resto, todas. Sin servicios elegidos no se restringe nada.
    """
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class LeadSearchRow:
    """Resultado de busqueda: el lead mas los datos derivados que necesita la UI."""

    lead: Lead
    distance_km: float | None
    purchased_by_requester: bool


@dataclass(frozen=True, slots=True)
class AdminLeadFilters:
    """Filtros del inventario administrativo, incluidas solicitudes retiradas."""

    category_id: UUID | None = None
    status: LeadStatus | None = None
    source: LeadSource | None = None
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class LeadDashboardCounts:
    total: int
    published: int
    exhausted: int
    disabled: int
    organic: int
    admin: int


@dataclass(frozen=True, slots=True)
class PaidPurchaseMetrics:
    count: int
    lead_count: int
    revenue_by_currency: dict[str, int]


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

    @abstractmethod
    async def search_admin(self, filters: AdminLeadFilters) -> list[Lead]: ...

    @abstractmethod
    async def count_admin(self, filters: AdminLeadFilters) -> int: ...

    @abstractmethod
    async def dashboard_counts(self) -> LeadDashboardCounts: ...


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

    @abstractmethod
    async def list_for_lead(
        self, lead_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Purchase]: ...

    @abstractmethod
    async def paid_metrics(self) -> PaidPurchaseMetrics: ...


class UserRepositoryPort(ABC):
    @abstractmethod
    async def add(self, user: User) -> User: ...

    @abstractmethod
    async def get(self, user_id: UUID) -> User | None: ...

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
    async def get_for_update(self, professional_id: UUID) -> Professional | None:
        """Bloquea la fila hasta el final de la transaccion (aprobar/rechazar el alta).

        Si hace falta tambien la cuenta, se bloquea DESPUES del profesional: siempre
        en ese orden, para no interbloquear.
        """

    @abstractmethod
    async def update(self, professional: Professional) -> Professional: ...

    @abstractmethod
    async def list_admin(
        self,
        *,
        query: str | None,
        limit: int,
        offset: int,
        verification_status: VerificationStatus | None = None,
    ) -> list[Professional]:
        """Con estado `pending`, es la cola de validacion: los mas antiguos primero."""

    @abstractmethod
    async def count_admin(
        self, *, query: str | None, verification_status: VerificationStatus | None = None
    ) -> int: ...

    @abstractmethod
    async def count_all(self) -> int: ...

    @abstractmethod
    async def add_verification_event(self, event: VerificationEvent) -> None:
        """Auditoria append-only de la validacion."""

    @abstractmethod
    async def list_verification_events(self, professional_id: UUID) -> list[VerificationEvent]:
        """Del mas antiguo al mas reciente."""


class CategoryRepositoryPort(ABC):
    @abstractmethod
    async def list_active(self) -> list[Category]: ...

    @abstractmethod
    async def get(self, category_id: UUID) -> Category | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Category | None: ...

    @abstractmethod
    async def get_many(self, category_ids: set[UUID]) -> list[Category]: ...

    @abstractmethod
    async def update(self, category: Category) -> Category:
        """Persiste cambios del catalogo (hoy solo el precio sugerido del oficio)."""


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


class PurchaseReviewRepositoryPort(ABC):
    """Historial append-only de revisiones solicitadas por administracion."""

    @abstractmethod
    async def add(self, review: PurchaseReview) -> PurchaseReview: ...

    @abstractmethod
    async def list_for_purchase(self, purchase_id: UUID) -> list[PurchaseReview]: ...


class ProfessionalAccountRepositoryPort(ABC):
    """Cuenta de recarga + saldo. Una por profesional, creada al iniciar la recarga."""

    @abstractmethod
    async def add(self, account: ProfessionalAccount) -> ProfessionalAccount: ...

    @abstractmethod
    async def update(self, account: ProfessionalAccount) -> ProfessionalAccount: ...

    @abstractmethod
    async def get(self, professional_id: UUID) -> ProfessionalAccount | None: ...

    @abstractmethod
    async def get_for_update(self, professional_id: UUID) -> ProfessionalAccount | None:
        """Bloquea la cuenta hasta el final de la transaccion.

        Es lo que impide gastar dos veces el mismo saldo en compras simultaneas.
        Quien bloquee tambien un lead debe bloquear primero el lead y despues la
        cuenta, siempre en ese orden, para no provocar interbloqueos.
        """

    @abstractmethod
    async def get_by_customer_for_update(self, customer_id: str) -> ProfessionalAccount | None:
        """Cuenta asociada al cliente de la pasarela, bloqueada (eventos del webhook)."""

    @abstractmethod
    async def get_many(self, professional_ids: set[UUID]) -> dict[UUID, ProfessionalAccount]: ...

    @abstractmethod
    async def count_active(self, *, now: datetime) -> int: ...


class CreditLedgerRepositoryPort(ABC):
    """Libro append-only de movimientos de saldo."""

    @abstractmethod
    async def add_if_absent(self, entry: CreditEntry) -> bool:
        """Registra el movimiento y devuelve True si no existia otro igual.

        "Igual" es el mismo `kind` con la misma `source_ref`. Si devuelve False el
        movimiento ya se habia aplicado y el caso de uso no debe tocar el saldo.
        """

    @abstractmethod
    async def list_for_professional(
        self, professional_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[CreditEntry]: ...

    @abstractmethod
    async def latest_topup(self, professional_id: UUID) -> CreditEntry | None:
        """Ultima recarga cobrada: dice cuanto paga ESTE profesional al mes."""

    @abstractmethod
    async def first_topup(self, professional_id: UUID) -> CreditEntry | None:
        """Primera recarga cobrada: la que se reembolsa si se rechaza el alta."""

    @abstractmethod
    async def topup_totals(self) -> dict[str, int]:
        """Suma de recargas cobradas por divisa (en centimos)."""


class SubscriptionPriceRepositoryPort(ABC):
    """Historial append-only del importe de la mensualidad."""

    @abstractmethod
    async def add(self, price: SubscriptionPrice) -> SubscriptionPrice: ...

    @abstractmethod
    async def current(self) -> SubscriptionPrice | None:
        """La mas reciente, o None si el admin aun no la ha fijado."""
