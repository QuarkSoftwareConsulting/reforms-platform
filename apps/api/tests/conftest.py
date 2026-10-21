"""Cableado compartido de los tests de casos de uso.

`world` monta el sistema completo con adaptadores in-memory: los mismos casos de
uso que corren en produccion, sin Postgres, Stripe ni Firebase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

import pytest

from app.application.ports import PostalCodeInfo
from app.application.use_cases import (
    AddProfessionalDocument,
    AdjustProfessionalCredit,
    ApplyChargeback,
    ApplySubscriptionEvent,
    ApproveProfessional,
    ChangeLeadAvailability,
    ChangeUserRole,
    CreateCategory,
    CreateLead,
    CreateService,
    CreditLedgerService,
    DeleteCategory,
    DeleteService,
    GetAdminMetrics,
    GetLandingServiceImage,
    GetLeadDetail,
    GetLeadPricing,
    GetMetricsTimeseries,
    GetProfessionalAccount,
    GetProfessionalProfile,
    GetVerificationDossier,
    HandlePaymentEvent,
    ListAdminLeads,
    ListAdminProfessionals,
    ListAdminPurchases,
    ListAdminUsers,
    ListCatalogForAdmin,
    ListCategories,
    ListFeatureFlags,
    ListLeadPurchasesForAdmin,
    ListLeads,
    ListMyPurchases,
    ListUserRoleEvents,
    MarkPurchaseForReview,
    OpenBillingPortal,
    OriginLimit,
    RejectProfessional,
    ReleaseExpiredReservations,
    RemoveProfessionalDocument,
    RequestCatalogImageUpload,
    RequestPhotoUpload,
    RequestProfessionalUpload,
    SetLeadPrice,
    SetSubscriptionPrice,
    StartLeadPurchase,
    StartPhoneVerification,
    StartSubscription,
    SubmitForReview,
    SubscriptionPricing,
    SyncUserFromIdentity,
    UpdateCategory,
    UpdateService,
    UpsertProfessionalProfile,
)
from app.domain.models import (
    Category,
    FlagEnvironment,
    Professional,
    ProfessionalAccount,
    SubscriptionPrice,
    User,
)
from app.domain.value_objects import Coordinates, Money, PostalCode
from tests.factories import (
    BARCELONA,
    MADRID,
    NOW,
    make_account,
    make_category,
    make_professional,
    make_user,
)
from tests.fakes import (
    FakeClock,
    FakePaymentGateway,
    FakePhoneVerifier,
    FakeStorage,
    FakeTokenVerifier,
    InMemoryCategoryRepository,
    InMemoryCreditLedgerRepository,
    InMemoryFeatureFlagRepository,
    InMemoryInvoiceRepository,
    InMemoryLeadRepository,
    InMemoryPostalCodeRepository,
    InMemoryProcessedEventRepository,
    InMemoryProfessionalAccountRepository,
    InMemoryProfessionalRepository,
    InMemoryPurchaseRepository,
    InMemoryPurchaseReviewRepository,
    InMemoryRateLimiter,
    InMemorySubscriptionPriceRepository,
    InMemoryUnitOfWork,
    InMemoryUserRepository,
    SequentialIdGenerator,
)

WEB_URL = "https://reformahub.test"
TOPUP = Money(1800, "EUR")
ADMIN_TOPUP_PRICE_ID = "price_admin_topup"
SMS_PER_ORIGIN = 3

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
    reviews: InMemoryPurchaseReviewRepository
    professionals: InMemoryProfessionalRepository
    users: InMemoryUserRepository
    categories: InMemoryCategoryRepository
    postal_codes: InMemoryPostalCodeRepository
    processed_events: InMemoryProcessedEventRepository
    accounts: InMemoryProfessionalAccountRepository
    ledger: InMemoryCreditLedgerRepository
    subscription_prices: InMemorySubscriptionPriceRepository
    payments: FakePaymentGateway
    storage: FakeStorage
    tokens: FakeTokenVerifier
    phone_verifier: FakePhoneVerifier = field(default_factory=FakePhoneVerifier)
    feature_flags: InMemoryFeatureFlagRepository = field(
        default_factory=InMemoryFeatureFlagRepository
    )
    rate_limiter: InMemoryRateLimiter = field(default_factory=InMemoryRateLimiter)
    invoices: InMemoryInvoiceRepository = field(default_factory=InMemoryInvoiceRepository)
    private_storage: FakeStorage = field(
        default_factory=lambda: FakeStorage(base_url="https://private.test/reforma-hub")
    )
    """Bucket de los documentos de alta: distinto del publico."""

    create_lead: CreateLead = field(init=False)
    """Sin verificacion por SMS, como hoy en produccion (no hay proveedor)."""
    create_lead_with_sms: CreateLead = field(init=False)
    start_phone_verification: StartPhoneVerification = field(init=False)
    submit_for_review: SubmitForReview = field(init=False)
    approve_professional: ApproveProfessional = field(init=False)
    reject_professional: RejectProfessional = field(init=False)
    verification_dossier: GetVerificationDossier = field(init=False)
    request_professional_upload: RequestProfessionalUpload = field(init=False)
    add_document: AddProfessionalDocument = field(init=False)
    remove_document: RemoveProfessionalDocument = field(init=False)
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
    list_feature_flags: ListFeatureFlags = field(init=False)
    request_upload: RequestPhotoUpload = field(init=False)
    lead_pricing: GetLeadPricing = field(init=False)
    set_lead_price: SetLeadPrice = field(init=False)
    list_catalog: ListCatalogForAdmin = field(init=False)
    create_category: CreateCategory = field(init=False)
    update_category: UpdateCategory = field(init=False)
    delete_category: DeleteCategory = field(init=False)
    create_service: CreateService = field(init=False)
    update_service: UpdateService = field(init=False)
    delete_service: DeleteService = field(init=False)
    request_catalog_image_upload: RequestCatalogImageUpload = field(init=False)
    landing_service_image: GetLandingServiceImage = field(init=False)
    list_admin_leads: ListAdminLeads = field(init=False)
    change_lead_availability: ChangeLeadAvailability = field(init=False)
    admin_metrics: GetAdminMetrics = field(init=False)
    list_lead_purchases: ListLeadPurchasesForAdmin = field(init=False)
    list_admin_professionals: ListAdminProfessionals = field(init=False)
    mark_purchase_for_review: MarkPurchaseForReview = field(init=False)
    credit: CreditLedgerService = field(init=False)
    start_subscription: StartSubscription = field(init=False)
    billing_portal: OpenBillingPortal = field(init=False)
    get_account: GetProfessionalAccount = field(init=False)
    adjust_credit: AdjustProfessionalCredit = field(init=False)
    pricing: SubscriptionPricing = field(init=False)
    set_subscription_price: SetSubscriptionPrice = field(init=False)
    change_user_role: ChangeUserRole = field(init=False)
    list_role_events: ListUserRoleEvents = field(init=False)
    list_admin_users: ListAdminUsers = field(init=False)
    list_admin_purchases: ListAdminPurchases = field(init=False)
    metrics_timeseries: GetMetricsTimeseries = field(init=False)

    def __post_init__(self) -> None:
        self.leads.purchase_index = self.purchases
        self.users.professional_index = self.professionals
        self.categories.lead_index = self.leads
        self.categories.professional_index = self.professionals
        self.credit = CreditLedgerService(accounts=self.accounts, ledger=self.ledger, ids=self.ids)
        # Como en produccion: la mensualidad la fija el admin. Sin ella nadie se
        # suscribe; los tests de ese caso vacian `subscription_prices.items`.
        self.subscription_prices.items.append(
            SubscriptionPrice(
                id=self.ids.new_id(),
                amount=TOPUP,
                stripe_price_id=ADMIN_TOPUP_PRICE_ID,
                created_at=NOW - timedelta(days=30),
            )
        )
        self.pricing = SubscriptionPricing(prices=self.subscription_prices)
        self.create_lead = CreateLead(
            leads=self.leads,
            categories=self.categories,
            postal_codes=self.postal_codes,
            clock=self.clock,
            ids=self.ids,
            uow=self.uow,
        )
        self.create_lead_with_sms = CreateLead(
            leads=self.leads,
            categories=self.categories,
            postal_codes=self.postal_codes,
            clock=self.clock,
            ids=self.ids,
            uow=self.uow,
            phone_verifier=self.phone_verifier,
        )
        self.start_phone_verification = StartPhoneVerification(
            verifier=self.phone_verifier,
            origin_limit=OriginLimit(
                limiter=self.rate_limiter,
                clock=self.clock,
                uow=self.uow,
                limit=SMS_PER_ORIGIN,
                window=timedelta(hours=1),
            ),
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
            accounts=self.accounts,
            credit=self.credit,
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
            credit=self.credit,
            subscriptions=ApplySubscriptionEvent(
                accounts=self.accounts,
                credit=self.credit,
                invoices=self.invoices,
                clock=self.clock,
                ids=self.ids,
            ),
            chargebacks=ApplyChargeback(
                accounts=self.accounts, ledger=self.ledger, credit=self.credit, clock=self.clock
            ),
        )
        self.my_purchases = ListMyPurchases(
            purchases=self.purchases, leads=self.leads, categories=self.categories
        )
        self.release_reservations = ReleaseExpiredReservations(
            purchases=self.purchases,
            payments=self.payments,
            clock=self.clock,
            uow=self.uow,
            credit=self.credit,
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
            accounts=self.accounts,
            payments=self.payments,
        )
        self.submit_for_review = SubmitForReview(
            professionals=self.professionals, clock=self.clock, ids=self.ids, uow=self.uow
        )
        self.approve_professional = ApproveProfessional(
            professionals=self.professionals, clock=self.clock, ids=self.ids, uow=self.uow
        )
        self.reject_professional = RejectProfessional(
            professionals=self.professionals,
            accounts=self.accounts,
            ledger=self.ledger,
            credit=self.credit,
            payments=self.payments,
            clock=self.clock,
            ids=self.ids,
            uow=self.uow,
        )
        self.verification_dossier = GetVerificationDossier(
            professionals=self.professionals,
            categories=self.categories,
            users=self.users,
            documents=self.private_storage,
        )
        self.request_professional_upload = RequestProfessionalUpload(
            media=self.storage, documents=self.private_storage
        )
        self.add_document = AddProfessionalDocument(
            professionals=self.professionals, clock=self.clock, ids=self.ids, uow=self.uow
        )
        self.remove_document = RemoveProfessionalDocument(
            professionals=self.professionals, documents=self.private_storage, uow=self.uow
        )
        self.get_profile = GetProfessionalProfile(
            professionals=self.professionals, categories=self.categories
        )
        self.list_categories = ListCategories(categories=self.categories)
        # Los tests corren como cualquier despliegue que no es produccion: flags de dev.
        self.list_feature_flags = ListFeatureFlags(
            flags=self.feature_flags, environment=FlagEnvironment.DEV
        )
        self.request_upload = RequestPhotoUpload(storage=self.storage)
        self.lead_pricing = GetLeadPricing(leads=self.leads, categories=self.categories)
        self.set_lead_price = SetLeadPrice(
            leads=self.leads, categories=self.categories, uow=self.uow
        )
        self.list_catalog = ListCatalogForAdmin(categories=self.categories)
        self.create_category = CreateCategory(
            categories=self.categories, ids=self.ids, uow=self.uow
        )
        self.update_category = UpdateCategory(categories=self.categories, uow=self.uow)
        self.delete_category = DeleteCategory(categories=self.categories, uow=self.uow)
        self.create_service = CreateService(categories=self.categories, ids=self.ids, uow=self.uow)
        self.update_service = UpdateService(categories=self.categories, uow=self.uow)
        self.delete_service = DeleteService(categories=self.categories, uow=self.uow)
        self.request_catalog_image_upload = RequestCatalogImageUpload(
            categories=self.categories, storage=self.storage
        )
        self.landing_service_image = GetLandingServiceImage(
            categories=self.categories, storage=self.storage
        )
        self.list_admin_leads = ListAdminLeads(leads=self.leads, categories=self.categories)
        self.change_lead_availability = ChangeLeadAvailability(leads=self.leads, uow=self.uow)
        self.admin_metrics = GetAdminMetrics(
            leads=self.leads,
            purchases=self.purchases,
            professionals=self.professionals,
            accounts=self.accounts,
            ledger=self.ledger,
            clock=self.clock,
        )
        self.list_lead_purchases = ListLeadPurchasesForAdmin(
            purchases=self.purchases, professionals=self.professionals, reviews=self.reviews
        )
        self.list_admin_professionals = ListAdminProfessionals(
            professionals=self.professionals,
            categories=self.categories,
            accounts=self.accounts,
            clock=self.clock,
        )
        self.mark_purchase_for_review = MarkPurchaseForReview(
            purchases=self.purchases,
            reviews=self.reviews,
            clock=self.clock,
            ids=self.ids,
            uow=self.uow,
        )
        self.start_subscription = StartSubscription(
            accounts=self.accounts,
            pricing=self.pricing,
            payments=self.payments,
            clock=self.clock,
            uow=self.uow,
            web_base_url=WEB_URL,
            currency="EUR",
        )
        self.billing_portal = OpenBillingPortal(
            accounts=self.accounts, payments=self.payments, web_base_url=WEB_URL
        )
        self.get_account = GetProfessionalAccount(
            accounts=self.accounts,
            ledger=self.ledger,
            pricing=self.pricing,
            clock=self.clock,
            currency="EUR",
        )
        self.set_subscription_price = SetSubscriptionPrice(
            prices=self.subscription_prices,
            pricing=self.pricing,
            payments=self.payments,
            clock=self.clock,
            ids=self.ids,
            uow=self.uow,
            currency="EUR",
        )
        self.adjust_credit = AdjustProfessionalCredit(
            professionals=self.professionals,
            accounts=self.accounts,
            credit=self.credit,
            clock=self.clock,
            ids=self.ids,
            uow=self.uow,
            currency="EUR",
        )

        self.change_user_role = ChangeUserRole(
            users=self.users, clock=self.clock, ids=self.ids, uow=self.uow
        )
        self.list_role_events = ListUserRoleEvents(users=self.users)
        self.list_admin_users = ListAdminUsers(
            users=self.users,
            professionals=self.professionals,
            accounts=self.accounts,
            clock=self.clock,
        )
        self.list_admin_purchases = ListAdminPurchases(
            purchases=self.purchases,
            leads=self.leads,
            categories=self.categories,
            professionals=self.professionals,
            reviews=self.reviews,
        )
        self.metrics_timeseries = GetMetricsTimeseries(
            leads=self.leads, purchases=self.purchases, ledger=self.ledger, clock=self.clock
        )

    # ------------------------- atajos de escenario -----------------------

    def add_category(self, **kwargs: object) -> Category:
        category = make_category(**kwargs)
        self.categories.items[category.id] = category
        return category

    def add_professional(
        self, *, subscribed: bool = True, balance_cents: int = 0, **kwargs: object
    ) -> Professional:
        """Profesional listo para operar.

        Por defecto esta al dia con la recarga y sin saldo, de modo que sus compras
        pasan por el checkout. `subscribed=False` lo deja sin cuenta de recarga.
        """
        professional = make_professional(**kwargs)
        self.professionals.items[professional.id] = professional
        if subscribed:
            self.add_account(professional, balance_cents=balance_cents)
        return professional

    def add_account(self, professional: Professional, **kwargs: object) -> ProfessionalAccount:
        account = make_account(professional_id=professional.id, **kwargs)
        self.accounts.items[professional.id] = account
        return account

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
        reviews=InMemoryPurchaseReviewRepository(),
        professionals=InMemoryProfessionalRepository(uow=uow),
        users=InMemoryUserRepository(uow=uow),
        categories=InMemoryCategoryRepository(),
        postal_codes=InMemoryPostalCodeRepository(POSTAL_CODES),
        processed_events=InMemoryProcessedEventRepository(),
        accounts=InMemoryProfessionalAccountRepository(uow=uow),
        ledger=InMemoryCreditLedgerRepository(),
        subscription_prices=InMemorySubscriptionPriceRepository(),
        payments=FakePaymentGateway(),
        storage=FakeStorage(),
        tokens=FakeTokenVerifier(),
    )


@pytest.fixture
def carpentry(world: World) -> Category:
    return world.add_category(slug="carpinteria", suggested_lead_price=Money(500, "EUR"))


@pytest.fixture
def plumbing(world: World) -> Category:
    return world.add_category(
        slug="fontaneria",
        name_es="Fontaneria",
        name_en="Plumbing",
        suggested_lead_price=Money(700, "EUR"),
    )


@pytest.fixture
def madrid_carpenter(world: World, carpentry: Category) -> Professional:
    """Carpintero con base en Madrid y 25 km de radio."""
    return world.add_professional(
        base_coordinates=MADRID, service_radius_km=25, category_ids={carpentry.id}
    )


def other_professional(world: World, category_ids: set[UUID]) -> Professional:
    return world.add_professional(base_coordinates=MADRID, category_ids=category_ids)
