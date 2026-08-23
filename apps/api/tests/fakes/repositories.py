"""Repositorios in-memory.

`InMemoryLeadRepository.get_for_update` usa un `asyncio.Lock` por lead para imitar
el `SELECT ... FOR UPDATE` de Postgres: es lo que permite reproducir en un test la
carrera de dos profesionales comprando la ultima plaza.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.application.ports import (
    CategoryRepositoryPort,
    LeadRepositoryPort,
    LeadSearchFilters,
    LeadSearchRow,
    PostalCodeInfo,
    PostalCodeRepositoryPort,
    ProcessedEventRepositoryPort,
    ProfessionalRepositoryPort,
    PurchaseRepositoryPort,
    UnitOfWork,
    UserRepositoryPort,
)
from app.domain.models import (
    Category,
    Lead,
    LeadStatus,
    Professional,
    Purchase,
    PurchaseStatus,
    User,
)
from app.domain.value_objects import PostalCode


async def _round_trip() -> None:
    """Cede el control al event loop.

    Cada llamada a un repositorio real es un viaje de red a Postgres, o sea un
    punto donde otra corrutina puede avanzar. Sin este `await` los fakes correrian
    de forma efectivamente atomica y los tests de concurrencia pasarian sin probar
    nada.
    """
    await asyncio.sleep(0)


class InMemoryUnitOfWork(UnitOfWork):
    """Transaccion simulada.

    Cuenta commits/rollbacks para poder afirmar sobre ellos y, al cerrar, libera
    los bloqueos de fila que los repositorios hayan tomado: igual que Postgres,
    que suelta los `FOR UPDATE` al terminar la transaccion.
    """

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.depth = 0
        self._on_close: list[Callable[[], None]] = []

    def register_release(self, release: Callable[[], None]) -> None:
        self._on_close.append(release)

    def _close(self) -> None:
        self.depth -= 1
        for release in self._on_close:
            release()
        self._on_close.clear()

    async def begin(self) -> None:
        await _round_trip()
        self.depth += 1

    async def commit(self) -> None:
        await _round_trip()
        self._close()
        self.commits += 1

    async def rollback(self) -> None:
        await _round_trip()
        self._close()
        self.rollbacks += 1


class InMemoryLeadRepository(LeadRepositoryPort):
    def __init__(
        self,
        leads: list[Lead] | None = None,
        *,
        uow: InMemoryUnitOfWork | None = None,
    ) -> None:
        self.items: dict[UUID, Lead] = {lead.id: lead for lead in (leads or [])}
        self._locks: dict[UUID, asyncio.Lock] = {}
        self.uow = uow
        self.purchase_index: PurchaseRepositoryPort | None = None
        self.lock_waits = 0

    async def add(self, lead: Lead) -> Lead:
        await _round_trip()
        self.items[lead.id] = lead
        return lead

    async def get(self, lead_id: UUID) -> Lead | None:
        await _round_trip()
        return self.items.get(lead_id)

    async def get_for_update(self, lead_id: UUID) -> Lead | None:
        await _round_trip()
        lead = self.items.get(lead_id)
        if lead is None:
            return None
        lock = self._locks.setdefault(lead_id, asyncio.Lock())
        if lock.locked():
            self.lock_waits += 1
        await lock.acquire()
        if self.uow is not None:
            # Se libera al cerrar la transaccion, como hace Postgres con FOR UPDATE.
            self.uow.register_release(lock.release)
        else:
            lock.release()
        return lead

    async def update(self, lead: Lead) -> Lead:
        await _round_trip()
        self.items[lead.id] = lead
        return lead

    def _matches(self, lead: Lead, filters: LeadSearchFilters) -> bool:
        if lead.status is not LeadStatus.PUBLISHED:
            return False
        if filters.category_ids and lead.category_id not in filters.category_ids:
            return False
        if filters.province and lead.location.province != filters.province:
            return False
        if filters.center is not None and filters.radius_km is not None:
            distance = filters.center.distance_km_to(lead.location.coordinates)
            if distance > filters.radius_km:
                return False
        return True

    async def search(
        self, filters: LeadSearchFilters, *, requester_professional_id: UUID | None = None
    ) -> list[LeadSearchRow]:
        await _round_trip()
        matching = sorted(
            (lead for lead in self.items.values() if self._matches(lead, filters)),
            key=lambda lead: lead.created_at,
            reverse=True,
        )
        window = matching[filters.offset : filters.offset + filters.limit]

        rows: list[LeadSearchRow] = []
        for lead in window:
            distance = (
                round(filters.center.distance_km_to(lead.location.coordinates), 1)
                if filters.center
                else None
            )
            purchased = False
            if requester_professional_id is not None and self.purchase_index is not None:
                purchased = await self.purchase_index.has_paid_purchase(
                    lead.id, requester_professional_id
                )
            rows.append(
                LeadSearchRow(lead=lead, distance_km=distance, purchased_by_requester=purchased)
            )
        return rows

    async def count(self, filters: LeadSearchFilters) -> int:
        await _round_trip()
        return sum(1 for lead in self.items.values() if self._matches(lead, filters))


class InMemoryPurchaseRepository(PurchaseRepositoryPort):
    def __init__(self, purchases: list[Purchase] | None = None) -> None:
        self.items: dict[UUID, Purchase] = {p.id: p for p in (purchases or [])}

    async def add(self, purchase: Purchase) -> Purchase:
        await _round_trip()
        self.items[purchase.id] = purchase
        return purchase

    async def get(self, purchase_id: UUID) -> Purchase | None:
        await _round_trip()
        return self.items.get(purchase_id)

    async def get_by_checkout_session(self, session_id: str) -> Purchase | None:
        await _round_trip()
        return next(
            (p for p in self.items.values() if p.stripe_checkout_session_id == session_id), None
        )

    async def update(self, purchase: Purchase) -> Purchase:
        await _round_trip()
        self.items[purchase.id] = purchase
        return purchase

    async def count_occupied_slots(self, lead_id: UUID, *, now: datetime) -> int:
        await _round_trip()
        return sum(
            1 for p in self.items.values() if p.lead_id == lead_id and p.occupies_slot_at(now)
        )

    async def find_active_for_lead_and_professional(
        self, lead_id: UUID, professional_id: UUID, *, now: datetime
    ) -> Purchase | None:
        await _round_trip()
        return next(
            (
                p
                for p in self.items.values()
                if p.lead_id == lead_id
                and p.professional_id == professional_id
                and p.occupies_slot_at(now)
            ),
            None,
        )

    async def list_for_professional(
        self, professional_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Purchase]:
        await _round_trip()
        rows = sorted(
            (p for p in self.items.values() if p.professional_id == professional_id),
            key=lambda p: p.created_at,
            reverse=True,
        )
        return rows[offset : offset + limit]

    async def list_expired_reservations(self, *, now: datetime, limit: int = 100) -> list[Purchase]:
        await _round_trip()
        return [p for p in self.items.values() if p.is_reservation_expired(now)][:limit]

    async def has_paid_purchase(self, lead_id: UUID, professional_id: UUID) -> bool:
        await _round_trip()
        return any(
            p.lead_id == lead_id
            and p.professional_id == professional_id
            and p.status is PurchaseStatus.PAID
            for p in self.items.values()
        )


class InMemoryUserRepository(UserRepositoryPort):
    def __init__(self, users: list[User] | None = None) -> None:
        self.items: dict[UUID, User] = {u.id: u for u in (users or [])}

    async def add(self, user: User) -> User:
        await _round_trip()
        self.items[user.id] = user
        return user

    async def get_by_firebase_uid(self, firebase_uid: str) -> User | None:
        await _round_trip()
        return next((u for u in self.items.values() if u.firebase_uid == firebase_uid), None)

    async def update(self, user: User) -> User:
        await _round_trip()
        self.items[user.id] = user
        return user


class InMemoryProfessionalRepository(ProfessionalRepositoryPort):
    def __init__(self, professionals: list[Professional] | None = None) -> None:
        self.items: dict[UUID, Professional] = {p.id: p for p in (professionals or [])}

    async def add(self, professional: Professional) -> Professional:
        await _round_trip()
        self.items[professional.id] = professional
        return professional

    async def get(self, professional_id: UUID) -> Professional | None:
        await _round_trip()
        return self.items.get(professional_id)

    async def get_by_user_id(self, user_id: UUID) -> Professional | None:
        await _round_trip()
        return next((p for p in self.items.values() if p.user_id == user_id), None)

    async def update(self, professional: Professional) -> Professional:
        await _round_trip()
        self.items[professional.id] = professional
        return professional


class InMemoryCategoryRepository(CategoryRepositoryPort):
    def __init__(self, categories: list[Category] | None = None) -> None:
        self.items: dict[UUID, Category] = {c.id: c for c in (categories or [])}

    async def list_active(self) -> list[Category]:
        await _round_trip()
        return [c for c in self.items.values() if c.active]

    async def get(self, category_id: UUID) -> Category | None:
        await _round_trip()
        return self.items.get(category_id)

    async def get_by_slug(self, slug: str) -> Category | None:
        await _round_trip()
        return next((c for c in self.items.values() if c.slug == slug), None)

    async def get_many(self, category_ids: set[UUID]) -> list[Category]:
        await _round_trip()
        return [self.items[cid] for cid in category_ids if cid in self.items]


class InMemoryPostalCodeRepository(PostalCodeRepositoryPort):
    def __init__(self, entries: list[PostalCodeInfo] | None = None) -> None:
        self.items: dict[str, PostalCodeInfo] = {e.code.value: e for e in (entries or [])}

    async def get(self, code: PostalCode) -> PostalCodeInfo | None:
        await _round_trip()
        return self.items.get(code.value)


class InMemoryProcessedEventRepository(ProcessedEventRepositoryPort):
    def __init__(self) -> None:
        self.seen: dict[str, dict[str, object]] = {}

    async def mark_processed(
        self, event_id: str, event_type: str, payload: dict[str, object]
    ) -> bool:
        await _round_trip()
        if event_id in self.seen:
            return False
        self.seen[event_id] = {"type": event_type, "payload": payload}
        return True
