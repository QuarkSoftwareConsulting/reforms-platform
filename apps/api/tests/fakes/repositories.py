"""Repositorios in-memory.

`InMemoryLeadRepository.get_for_update` usa un `asyncio.Lock` por lead para imitar
el `SELECT ... FOR UPDATE` de Postgres: es lo que permite reproducir en un test la
carrera de dos profesionales comprando la ultima plaza.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID

from app.application.ports import (
    AdminLeadFilters,
    CategoryRepositoryPort,
    CreditLedgerRepositoryPort,
    LeadDashboardCounts,
    LeadRepositoryPort,
    LeadSearchFilters,
    LeadSearchRow,
    PaidPurchaseMetrics,
    PostalCodeInfo,
    PostalCodeRepositoryPort,
    ProcessedEventRepositoryPort,
    ProfessionalAccountRepositoryPort,
    ProfessionalRepositoryPort,
    PurchaseRepositoryPort,
    PurchaseReviewRepositoryPort,
    RateLimiterPort,
    SubscriptionPriceRepositoryPort,
    UnitOfWork,
    UserRepositoryPort,
)
from app.domain.exceptions import CategoryNotFoundError
from app.domain.models import (
    EXPLORER_STATUSES,
    Category,
    CreditEntry,
    CreditEntryKind,
    Lead,
    LeadStatus,
    Professional,
    ProfessionalAccount,
    Purchase,
    PurchaseReview,
    PurchaseStatus,
    SubscriptionPrice,
    User,
    VerificationEvent,
    VerificationStatus,
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
        if lead.status not in EXPLORER_STATUSES:
            return False
        if filters.category_ids and lead.category_id not in filters.category_ids:
            return False
        if filters.province and lead.location.province != filters.province:
            return False
        if (
            lead.category_id in filters.restricted_category_ids
            and lead.service_ids
            and not set(lead.service_ids) & filters.service_ids
        ):
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
        # Mismo orden que el repositorio real: abiertos primero, y dentro de cada
        # grupo los mas recientes.
        matching = sorted(
            (lead for lead in self.items.values() if self._matches(lead, filters)),
            key=lambda lead: (lead.is_closed, -lead.created_at.timestamp()),
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

    async def search_admin(self, filters: AdminLeadFilters) -> list[Lead]:
        await _round_trip()
        rows = [
            lead
            for lead in self.items.values()
            if (filters.category_id is None or lead.category_id == filters.category_id)
            and (filters.status is None or lead.status is filters.status)
            and (filters.source is None or lead.source is filters.source)
        ]
        rows.sort(key=lambda lead: lead.created_at, reverse=True)
        return rows[filters.offset : filters.offset + filters.limit]

    async def count_admin(self, filters: AdminLeadFilters) -> int:
        await _round_trip()
        return len(
            [
                lead
                for lead in self.items.values()
                if (filters.category_id is None or lead.category_id == filters.category_id)
                and (filters.status is None or lead.status is filters.status)
                and (filters.source is None or lead.source is filters.source)
            ]
        )

    async def dashboard_counts(self) -> LeadDashboardCounts:
        await _round_trip()
        values = list(self.items.values())
        return LeadDashboardCounts(
            total=len(values),
            published=sum(lead.status is LeadStatus.PUBLISHED for lead in values),
            exhausted=sum(lead.status is LeadStatus.EXHAUSTED for lead in values),
            disabled=sum(lead.status is LeadStatus.DISABLED for lead in values),
            organic=sum(lead.source.value == "organic" for lead in values),
            admin=sum(lead.source.value == "admin" for lead in values),
        )


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

    async def list_for_lead(
        self, lead_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Purchase]:
        await _round_trip()
        rows = sorted(
            (purchase for purchase in self.items.values() if purchase.lead_id == lead_id),
            key=lambda purchase: purchase.created_at,
            reverse=True,
        )
        return rows[offset : offset + limit]

    async def paid_metrics(self) -> PaidPurchaseMetrics:
        await _round_trip()
        rows = [
            purchase for purchase in self.items.values() if purchase.status is PurchaseStatus.PAID
        ]
        revenue: dict[str, int] = {}
        for purchase in rows:
            currency = purchase.price.currency
            revenue[currency] = revenue.get(currency, 0) + purchase.price.amount_cents
        return PaidPurchaseMetrics(
            count=len(rows),
            lead_count=len({purchase.lead_id for purchase in rows}),
            revenue_by_currency=revenue,
        )


class InMemoryUserRepository(UserRepositoryPort):
    def __init__(self, users: list[User] | None = None) -> None:
        self.items: dict[UUID, User] = {u.id: u for u in (users or [])}

    async def add(self, user: User) -> User:
        await _round_trip()
        self.items[user.id] = user
        return user

    async def get(self, user_id: UUID) -> User | None:
        await _round_trip()
        return self.items.get(user_id)

    async def get_by_firebase_uid(self, firebase_uid: str) -> User | None:
        await _round_trip()
        return next((u for u in self.items.values() if u.firebase_uid == firebase_uid), None)

    async def update(self, user: User) -> User:
        await _round_trip()
        self.items[user.id] = user
        return user


class InMemoryProfessionalRepository(ProfessionalRepositoryPort):
    """Perfiles. `get_for_update` imita el FOR UPDATE con un lock por profesional.

    `get_for_update` devuelve una COPIA, como dos sesiones de Postgres: sin ella no se
    reproduce la carrera entre aprobar y rechazar (cada uno escribe el estado que
    leyo). `get` sigue devolviendo la instancia, como el resto de este fake.
    """

    def __init__(
        self,
        professionals: list[Professional] | None = None,
        *,
        uow: InMemoryUnitOfWork | None = None,
    ) -> None:
        self.items: dict[UUID, Professional] = {p.id: p for p in (professionals or [])}
        self.events: list[VerificationEvent] = []
        self._locks: dict[UUID, asyncio.Lock] = {}
        self.uow = uow
        self.locking_enabled = True
        """Solo para comprobar que el test de carrera falla sin el bloqueo."""

    async def get_for_update(self, professional_id: UUID) -> Professional | None:
        await _round_trip()
        if professional_id not in self.items:
            return None
        if self.locking_enabled:
            lock = self._locks.setdefault(professional_id, asyncio.Lock())
            await lock.acquire()
            if self.uow is not None:
                self.uow.register_release(lock.release)
            else:
                lock.release()
        # Se lee DESPUES de obtener el bloqueo: ve lo que confirmo quien lo tenia.
        # Copia profunda: documentos y fotos son listas que el caso de uso muta.
        return copy.deepcopy(self.items[professional_id])

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

    async def list_admin(
        self,
        *,
        query: str | None,
        limit: int,
        offset: int,
        verification_status: VerificationStatus | None = None,
    ) -> list[Professional]:
        await _round_trip()
        query_lower = query.strip().lower() if query else None
        rows = [
            professional
            for professional in self.items.values()
            if (
                query_lower is None
                or query_lower in professional.business_name.lower()
                or query_lower in (professional.legal_name or "").lower()
                or query_lower in (professional.city or "").lower()
                or query_lower in (professional.province or "").lower()
            )
            and (
                verification_status is None
                or professional.verification_status is verification_status
            )
        ]
        if verification_status is VerificationStatus.PENDING:
            rows.sort(key=lambda professional: professional.submitted_at or professional.created_at)
        else:
            rows.sort(key=lambda professional: professional.created_at, reverse=True)
        return rows[offset : offset + limit]

    async def count_admin(
        self, *, query: str | None, verification_status: VerificationStatus | None = None
    ) -> int:
        await _round_trip()
        rows = await self.list_admin(
            query=query, limit=1_000_000, offset=0, verification_status=verification_status
        )
        return len(rows)

    async def count_all(self) -> int:
        await _round_trip()
        return len(self.items)

    async def add_verification_event(self, event: VerificationEvent) -> None:
        await _round_trip()
        self.events.append(event)

    async def list_verification_events(self, professional_id: UUID) -> list[VerificationEvent]:
        await _round_trip()
        return sorted(
            (e for e in self.events if e.professional_id == professional_id),
            key=lambda e: e.created_at,
        )


class InMemoryCategoryRepository(CategoryRepositoryPort):
    def __init__(self, categories: list[Category] | None = None) -> None:
        self.items: dict[UUID, Category] = {c.id: c for c in (categories or [])}

    async def list_active(self) -> list[Category]:
        await _round_trip()
        return sorted(
            (c for c in self.items.values() if c.active), key=lambda c: (c.sort_order, c.name_es)
        )

    async def get(self, category_id: UUID) -> Category | None:
        await _round_trip()
        return self.items.get(category_id)

    async def get_by_slug(self, slug: str) -> Category | None:
        await _round_trip()
        return next((c for c in self.items.values() if c.slug == slug), None)

    async def get_many(self, category_ids: set[UUID]) -> list[Category]:
        await _round_trip()
        return [self.items[cid] for cid in category_ids if cid in self.items]

    async def update(self, category: Category) -> Category:
        await _round_trip()
        if category.id not in self.items:
            raise CategoryNotFoundError()
        self.items[category.id] = category
        return category


class InMemoryPurchaseReviewRepository(PurchaseReviewRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[UUID, PurchaseReview] = {}

    async def add(self, review: PurchaseReview) -> PurchaseReview:
        await _round_trip()
        self.items[review.id] = review
        return review

    async def list_for_purchase(self, purchase_id: UUID) -> list[PurchaseReview]:
        await _round_trip()
        return sorted(
            (review for review in self.items.values() if review.purchase_id == purchase_id),
            key=lambda review: review.created_at,
            reverse=True,
        )


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


class InMemoryProfessionalAccountRepository(ProfessionalAccountRepositoryPort):
    """Cuentas de recarga. `get_for_update` imita el FOR UPDATE con un lock por cuenta.

    A diferencia de otros fakes, las lecturas devuelven una COPIA y solo `update`
    escribe: igual que dos sesiones de Postgres, cada transaccion ve el saldo que
    leyo. Sin eso no se podria reproducir la actualizacion perdida (dos compras
    que leen el mismo saldo y lo gastan dos veces) que el FOR UPDATE evita.
    """

    def __init__(self, *, uow: InMemoryUnitOfWork | None = None) -> None:
        self.items: dict[UUID, ProfessionalAccount] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}
        self.uow = uow
        self.lock_waits = 0
        self.locking_enabled = True
        """Solo para comprobar que el test de carrera falla sin el bloqueo."""

    async def _lock(self, professional_id: UUID) -> None:
        if not self.locking_enabled:
            return
        lock = self._locks.setdefault(professional_id, asyncio.Lock())
        if lock.locked():
            self.lock_waits += 1
        await lock.acquire()
        if self.uow is not None:
            self.uow.register_release(lock.release)
        else:
            lock.release()

    async def add(self, account: ProfessionalAccount) -> ProfessionalAccount:
        await _round_trip()
        self.items[account.professional_id] = account
        return account

    async def update(self, account: ProfessionalAccount) -> ProfessionalAccount:
        await _round_trip()
        self.items[account.professional_id] = account
        return account

    def _read(self, professional_id: UUID) -> ProfessionalAccount | None:
        account = self.items.get(professional_id)
        return copy.copy(account) if account is not None else None

    async def get(self, professional_id: UUID) -> ProfessionalAccount | None:
        await _round_trip()
        return self._read(professional_id)

    async def get_for_update(self, professional_id: UUID) -> ProfessionalAccount | None:
        await _round_trip()
        if professional_id not in self.items:
            return None
        await self._lock(professional_id)
        # Se lee DESPUES de obtener el bloqueo: ve lo que confirmo quien lo tenia.
        return self._read(professional_id)

    async def get_by_customer_for_update(self, customer_id: str) -> ProfessionalAccount | None:
        await _round_trip()
        account = next(
            (a for a in self.items.values() if a.stripe_customer_id == customer_id), None
        )
        if account is None:
            return None
        await self._lock(account.professional_id)
        return self._read(account.professional_id)

    async def get_many(self, professional_ids: set[UUID]) -> dict[UUID, ProfessionalAccount]:
        await _round_trip()
        return {pid: copy.copy(a) for pid, a in self.items.items() if pid in professional_ids}

    async def count_active(self, *, now: datetime) -> int:
        await _round_trip()
        return sum(1 for a in self.items.values() if a.is_active(now))


class InMemoryCreditLedgerRepository(CreditLedgerRepositoryPort):
    def __init__(self) -> None:
        self.entries: list[CreditEntry] = []

    async def add_if_absent(self, entry: CreditEntry) -> bool:
        await _round_trip()
        if any(e.kind is entry.kind and e.source_ref == entry.source_ref for e in self.entries):
            return False
        self.entries.append(entry)
        return True

    async def list_for_professional(
        self, professional_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[CreditEntry]:
        await _round_trip()
        rows = sorted(
            (e for e in self.entries if e.professional_id == professional_id),
            key=lambda e: e.created_at,
            reverse=True,
        )
        return rows[offset : offset + limit]

    async def latest_topup(self, professional_id: UUID) -> CreditEntry | None:
        await _round_trip()
        topups = [
            e
            for e in self.entries
            if e.professional_id == professional_id and e.kind is CreditEntryKind.TOPUP
        ]
        return max(topups, key=lambda e: e.created_at) if topups else None

    async def first_topup(self, professional_id: UUID) -> CreditEntry | None:
        await _round_trip()
        topups = [
            e
            for e in self.entries
            if e.professional_id == professional_id and e.kind is CreditEntryKind.TOPUP
        ]
        return min(topups, key=lambda e: e.created_at) if topups else None

    async def find(self, kind: CreditEntryKind, source_ref: str) -> CreditEntry | None:
        await _round_trip()
        return next(
            (e for e in self.entries if e.kind is kind and e.source_ref == source_ref), None
        )

    async def topup_totals(self) -> dict[str, int]:
        await _round_trip()
        totals: dict[str, int] = {}
        for entry in self.entries:
            if entry.kind is CreditEntryKind.TOPUP:
                currency = entry.amount.currency
                totals[currency] = totals.get(currency, 0) + entry.amount.amount_cents
        return totals

    def balance_of(self, professional_id: UUID) -> int:
        """Saldo neto (saldo menos deuda) recalculado desde el libro."""
        return sum(e.signed_cents for e in self.entries if e.professional_id == professional_id)


class InMemorySubscriptionPriceRepository(SubscriptionPriceRepositoryPort):
    def __init__(self) -> None:
        self.items: list[SubscriptionPrice] = []

    async def add(self, price: SubscriptionPrice) -> SubscriptionPrice:
        await _round_trip()
        self.items.append(price)
        return price

    async def current(self) -> SubscriptionPrice | None:
        await _round_trip()
        return max(self.items, key=lambda p: p.created_at) if self.items else None


class InMemoryRateLimiter(RateLimiterPort):
    """Ventana fija por clave, como el adaptador de Postgres."""

    def __init__(self) -> None:
        self.hits: dict[tuple[str, datetime], int] = {}

    async def allow(self, key: str, *, limit: int, window: timedelta, now: datetime) -> bool:
        await _round_trip()
        seconds = int(window.total_seconds())
        start = datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, tz=now.tzinfo)
        count = self.hits.get((key, start), 0) + 1
        self.hits[(key, start)] = count
        return count <= limit
