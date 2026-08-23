"""Cableado compartido de los tests de casos de uso.

`world` monta el sistema completo con adaptadores in-memory: los mismos casos de
uso que corren en produccion, sin Postgres, Stripe ni Firebase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import pytest

from app.application.ports import PostalCodeInfo
from app.application.use_cases import (
    CreateLead,
    GetLeadDetail,
    GetProfessionalProfile,
    HandlePaymentEvent,
    ListCategories,
    ListLeads,
    ListMyPurchases,
    ReleaseExpiredReservations,
    RequestPhotoUpload,
    StartLeadPurchase,
    SyncUserFromIdentity,
    UpsertProfessionalProfile,
)
from app.domain.models import Category, Professional, User
from app.domain.value_objects import Coordinates, Money, PostalCode
from tests.factories import BARCELONA, MADRID, NOW, make_category, make_professional, make_user
from tests.fakes import (
    FakeClock,
    FakePaymentGateway,
    FakeStorage,
    FakeTokenVerifier,
    InMemoryCategoryRepository,
    InMemoryLeadRepository,
    InMemoryPostalCodeRepository,
    InMemoryProcessedEventRepository,
    InMemoryProfessionalRepository,
    InMemoryPurchaseRepository,
    InMemoryUnitOfWork,
    InMemoryUserRepository,
    SequentialIdGenerator,
)

WEB_URL = "https://reformahub.test"

POSTAL_CODES = [
    PostalCodeInfo(PostalCode("28001"), "Madrid", "Madrid", MADRID),
    PostalCodeInfo(
        PostalCode("28801"), "Alcala de Henares", "Madrid", Coordinates(40.4818, -3.3644)
    ),
    PostalCodeInfo(PostalCode("08001"), "Barcelona", "Barcelona", BARCELONA),
]


@dataclass
class World:
    """Contenedor de todo el sistema en memoria, listo para actuar en un test."""

    clock: FakeClock
    ids: SequentialIdGenerator
    uow: InMemoryUnitOfWork
    leads: InMemoryLeadRepository
    purchases: InMemoryPurchaseRepository
    professionals: InMemoryProfessionalRepository
    users: InMemoryUserRepository
    categories: InMemoryCategoryRepository
    postal_codes: InMemoryPostalCodeRepository
    processed_events: InMemoryProcessedEventRepository
    payments: FakePaymentGateway
    storage: FakeStorage
    tokens: FakeTokenVerifier

    create_lead: CreateLead = field(init=False)
    list_leads: ListLeads = field(init=False)
    lead_detail: GetLeadDetail = field(init=False)
    start_purchase: StartLeadPurchase = field(init=False)
    handle_event: HandlePaymentEvent = field(init=False)
    my_purchases: ListMyPurchases = field(init=False)
    release_reservations: ReleaseExpiredReservations = field(init=False)
    sync_user: SyncUserFromIdentity = field(init=False)
    upsert_profile: UpsertProfessionalProfile = field(init=False)
    get_profile: GetProfessionalProfile = field(init=False)
    list_categories: ListCategories = field(init=False)
    request_upload: RequestPhotoUpload = field(init=False)

    def __post_init__(self) -> None:
        self.leads.purchase_index = self.purchases
        self.create_lead = CreateLead(
            leads=self.leads,
            categories=self.categories,
            postal_codes=self.postal_codes,
            clock=self.clock,
            ids=self.ids,
            uow=self.uow,
            max_purchases=3,
        )
        self.list_leads = ListLeads(
            leads=self.leads, categories=self.categories, professionals=self.professionals
        )
        self.lead_detail = GetLeadDetail(
            leads=self.leads,
            purchases=self.purchases,
            categories=self.categories,
            professionals=self.professionals,
        )
        self.start_purchase = StartLeadPurchase(
            leads=self.leads,
            purchases=self.purchases,
            professionals=self.professionals,
            categories=self.categories,
            payments=self.payments,
            clock=self.clock,
            ids=self.ids,
            uow=self.uow,
            web_base_url=WEB_URL,
            reservation_ttl_minutes=30,
        )
        self.handle_event = HandlePaymentEvent(
            purchases=self.purchases,
            leads=self.leads,
            processed_events=self.processed_events,
            payments=self.payments,
            clock=self.clock,
            uow=self.uow,
        )
        self.my_purchases = ListMyPurchases(
            purchases=self.purchases, leads=self.leads, categories=self.categories
        )
        self.release_reservations = ReleaseExpiredReservations(
            purchases=self.purchases, payments=self.payments, clock=self.clock, uow=self.uow
        )
        self.sync_user = SyncUserFromIdentity(
            users=self.users, clock=self.clock, ids=self.ids, uow=self.uow
        )
        self.upsert_profile = UpsertProfessionalProfile(
            professionals=self.professionals,
            categories=self.categories,
            postal_codes=self.postal_codes,
            clock=self.clock,
            ids=self.ids,
            uow=self.uow,
        )
        self.get_profile = GetProfessionalProfile(
            professionals=self.professionals, categories=self.categories
        )
        self.list_categories = ListCategories(categories=self.categories)
        self.request_upload = RequestPhotoUpload(storage=self.storage)

    # ------------------------- atajos de escenario -----------------------

    def add_category(self, **kwargs: object) -> Category:
        category = make_category(**kwargs)
        self.categories.items[category.id] = category
        return category

    def add_professional(self, **kwargs: object) -> Professional:
        professional = make_professional(**kwargs)
        self.professionals.items[professional.id] = professional
        return professional

    def add_user(self, **kwargs: object) -> User:
        user = make_user(**kwargs)
        self.users.items[user.id] = user
        return user


@pytest.fixture
def world() -> World:
    uow = InMemoryUnitOfWork()
    return World(
        clock=FakeClock(NOW),
        ids=SequentialIdGenerator(),
        uow=uow,
        leads=InMemoryLeadRepository(uow=uow),
        purchases=InMemoryPurchaseRepository(),
        professionals=InMemoryProfessionalRepository(),
        users=InMemoryUserRepository(),
        categories=InMemoryCategoryRepository(),
        postal_codes=InMemoryPostalCodeRepository(POSTAL_CODES),
        processed_events=InMemoryProcessedEventRepository(),
        payments=FakePaymentGateway(),
        storage=FakeStorage(),
        tokens=FakeTokenVerifier(),
    )


@pytest.fixture
def carpentry(world: World) -> Category:
    return world.add_category(slug="carpinteria", lead_price=Money(500, "EUR"))


@pytest.fixture
def plumbing(world: World) -> Category:
    return world.add_category(
        slug="fontaneria", name_es="Fontaneria", name_en="Plumbing", lead_price=Money(700, "EUR")
    )


@pytest.fixture
def madrid_carpenter(world: World, carpentry: Category) -> Professional:
    """Carpintero con base en Madrid y 25 km de radio."""
    return world.add_professional(
        base_coordinates=MADRID, service_radius_km=25, category_ids={carpentry.id}
    )


def other_professional(world: World, category_ids: set[UUID]) -> Professional:
    return world.add_professional(base_coordinates=MADRID, category_ids=category_ids)
