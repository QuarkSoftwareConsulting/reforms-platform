"""Composition root: cablea puertos con adaptadores.

Es el unico sitio donde la eleccion de tecnologia se hace explicita. Los casos de
uso se construyen por peticion con la sesion de esa peticion, de modo que cada
transaccion queda aislada. No se usa libreria de DI: un contenedor de ~100 lineas
es mas facil de leer y de sustituir en los tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.ports import (
    AuthenticatedIdentity,
    ClockPort,
    IdGeneratorPort,
    PaymentPort,
    PhoneVerificationPort,
    StoragePort,
    TokenVerifierPort,
)
from app.application.use_cases import (
    AddProfessionalDocument,
    AdjustProfessionalCredit,
    ApplyChargeback,
    ApplySubscriptionEvent,
    ApproveProfessional,
    ChangeLeadAvailability,
    CreateLead,
    CreditLedgerService,
    GetAdminMetrics,
    GetLeadDetail,
    GetLeadPricing,
    GetProfessionalAccount,
    GetProfessionalProfile,
    GetVerificationDossier,
    HandlePaymentEvent,
    ListAdminLeads,
    ListAdminProfessionals,
    ListCategories,
    ListLeadPurchasesForAdmin,
    ListLeads,
    ListMyPurchases,
    MarkPurchaseForReview,
    OpenBillingPortal,
    RejectProfessional,
    ReleaseExpiredReservations,
    RemoveProfessionalDocument,
    RequestPhotoUpload,
    RequestProfessionalUpload,
    SetCategorySuggestedPrice,
    SetLeadPrice,
    SetSubscriptionPrice,
    StartLeadPurchase,
    StartPhoneVerification,
    StartSubscription,
    SubmitForReview,
    SubscriptionPricing,
    SyncUserFromIdentity,
    UpsertProfessionalProfile,
)
from app.config import Settings, get_settings
from app.domain.exceptions import DomainError, ProfessionalNotFoundError
from app.domain.models import Professional, ServiceArea, User
from app.domain.value_objects import Money
from app.infrastructure.adapters.db.repositories import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyCreditLedgerRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyPostalCodeRepository,
    SqlAlchemyProcessedEventRepository,
    SqlAlchemyProfessionalAccountRepository,
    SqlAlchemyProfessionalRepository,
    SqlAlchemyPurchaseRepository,
    SqlAlchemyPurchaseReviewRepository,
    SqlAlchemySubscriptionPriceRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.adapters.db.session import SqlAlchemyUnitOfWork
from app.infrastructure.adapters.sms import ConsolePhoneVerifier
from app.infrastructure.adapters.storage.gcs_adapter import GCSStorage
from app.infrastructure.adapters.storage.s3_adapter import S3Storage


def create_storage(settings: Settings) -> StoragePort:
    if settings.storage_backend == "gcs":
        return GCSStorage(
            bucket=settings.gcs_bucket,
            signed_url_expires_seconds=settings.gcs_signed_url_expires_seconds,
        )
    return S3Storage(
        bucket=settings.s3_bucket,
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
        region=settings.s3_region,
        public_base_url=settings.s3_public_base_url,
        presign_expires_seconds=settings.s3_presign_expires_seconds,
    )


def create_document_storage(settings: Settings) -> StoragePort:
    """Bucket privado de los documentos de alta. Nunca se sirve con URL publica."""
    if settings.storage_backend == "gcs":
        return GCSStorage(
            bucket=settings.gcs_private_bucket,
            signed_url_expires_seconds=settings.gcs_signed_url_expires_seconds,
        )
    return S3Storage(
        bucket=settings.s3_private_bucket,
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
        region=settings.s3_region,
        presign_expires_seconds=settings.s3_presign_expires_seconds,
    )


def create_phone_verifier(settings: Settings, clock: ClockPort) -> PhoneVerificationPort | None:
    """`None` desactiva la verificacion por SMS: el formulario publica sin codigo."""
    if settings.phone_verification_backend == "console":
        return ConsolePhoneVerifier(clock=clock)
    return None


@dataclass(slots=True)
class Infrastructure:
    """Recursos de proceso: se crean al arrancar y se comparten entre peticiones."""

    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    payments: PaymentPort
    storage: StoragePort
    token_verifier: TokenVerifierPort
    clock: ClockPort
    ids: IdGeneratorPort
    # De proceso: el adaptador de consola guarda los codigos en memoria.
    phone_verifier: PhoneVerificationPort | None = None
    document_storage: StoragePort | None = None
    """Bucket privado. `None` solo en tests que no tocan documentos."""

    @property
    def documents(self) -> StoragePort:
        if self.document_storage is None:
            raise RuntimeError("Falta configurar el almacenamiento privado de documentos")
        return self.document_storage


def get_infrastructure(request: Request) -> Infrastructure:
    infra: Infrastructure = request.app.state.infrastructure
    return infra


InfraDep = Annotated[Infrastructure, Depends(get_infrastructure)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_session(infra: InfraDep) -> AsyncIterator[AsyncSession]:
    async with infra.session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]


@dataclass(slots=True)
class RequestContainer:
    """Todos los casos de uso listos para una peticion concreta."""

    infra: Infrastructure
    session: AsyncSession
    uow: SqlAlchemyUnitOfWork

    users: SqlAlchemyUserRepository
    professionals: SqlAlchemyProfessionalRepository
    leads: SqlAlchemyLeadRepository
    purchases: SqlAlchemyPurchaseRepository
    reviews: SqlAlchemyPurchaseReviewRepository
    categories: SqlAlchemyCategoryRepository
    postal_codes: SqlAlchemyPostalCodeRepository
    processed_events: SqlAlchemyProcessedEventRepository
    accounts: SqlAlchemyProfessionalAccountRepository
    ledger: SqlAlchemyCreditLedgerRepository
    subscription_prices: SqlAlchemySubscriptionPriceRepository

    @classmethod
    def build(cls, infra: Infrastructure, session: AsyncSession) -> RequestContainer:
        return cls(
            infra=infra,
            session=session,
            uow=SqlAlchemyUnitOfWork(session),
            users=SqlAlchemyUserRepository(session),
            professionals=SqlAlchemyProfessionalRepository(session),
            leads=SqlAlchemyLeadRepository(session),
            purchases=SqlAlchemyPurchaseRepository(session),
            reviews=SqlAlchemyPurchaseReviewRepository(session),
            categories=SqlAlchemyCategoryRepository(session),
            postal_codes=SqlAlchemyPostalCodeRepository(session),
            processed_events=SqlAlchemyProcessedEventRepository(session),
            accounts=SqlAlchemyProfessionalAccountRepository(session),
            ledger=SqlAlchemyCreditLedgerRepository(session),
            subscription_prices=SqlAlchemySubscriptionPriceRepository(session),
        )

    @property
    def pricing(self) -> SubscriptionPricing:
        settings = self.infra.settings
        return SubscriptionPricing(
            prices=self.subscription_prices,
            default_amount=Money(settings.subscription_topup_cents, settings.default_currency),
            default_price_id=settings.stripe_topup_price_id,
        )

    @property
    def credit(self) -> CreditLedgerService:
        return CreditLedgerService(accounts=self.accounts, ledger=self.ledger, ids=self.infra.ids)

    # ------------------------------ Casos de uso -------------------------

    @property
    def create_lead(self) -> CreateLead:
        return CreateLead(
            leads=self.leads,
            categories=self.categories,
            postal_codes=self.postal_codes,
            clock=self.infra.clock,
            ids=self.infra.ids,
            uow=self.uow,
            max_purchases=self.infra.settings.lead_max_purchases,
            service_area=ServiceArea.from_prefixes(self.infra.settings.covered_postal_prefixes),
            phone_verifier=self.infra.phone_verifier,
        )

    @property
    def start_phone_verification(self) -> StartPhoneVerification:
        return StartPhoneVerification(verifier=self.infra.phone_verifier)

    @property
    def list_leads(self) -> ListLeads:
        return ListLeads(
            leads=self.leads, categories=self.categories, professionals=self.professionals
        )

    @property
    def lead_detail(self) -> GetLeadDetail:
        return GetLeadDetail(
            leads=self.leads,
            purchases=self.purchases,
            categories=self.categories,
            professionals=self.professionals,
        )

    @property
    def start_purchase(self) -> StartLeadPurchase:
        return StartLeadPurchase(
            leads=self.leads,
            purchases=self.purchases,
            professionals=self.professionals,
            categories=self.categories,
            accounts=self.accounts,
            credit=self.credit,
            payments=self.infra.payments,
            clock=self.infra.clock,
            ids=self.infra.ids,
            uow=self.uow,
            web_base_url=self.infra.settings.public_web_url,
            reservation_ttl_minutes=self.infra.settings.purchase_reservation_ttl_minutes,
            enforce_category_match=self.infra.settings.enforce_category_match,
        )

    @property
    def lead_pricing(self) -> GetLeadPricing:
        return GetLeadPricing(leads=self.leads, categories=self.categories)

    @property
    def set_lead_price(self) -> SetLeadPrice:
        return SetLeadPrice(leads=self.leads, categories=self.categories, uow=self.uow)

    @property
    def set_category_price(self) -> SetCategorySuggestedPrice:
        return SetCategorySuggestedPrice(categories=self.categories, uow=self.uow)

    @property
    def admin_leads(self) -> ListAdminLeads:
        return ListAdminLeads(leads=self.leads, categories=self.categories)

    @property
    def change_lead_availability(self) -> ChangeLeadAvailability:
        return ChangeLeadAvailability(leads=self.leads, uow=self.uow)

    @property
    def admin_metrics(self) -> GetAdminMetrics:
        return GetAdminMetrics(
            leads=self.leads,
            purchases=self.purchases,
            professionals=self.professionals,
            accounts=self.accounts,
            ledger=self.ledger,
            clock=self.infra.clock,
        )

    @property
    def lead_purchases_for_admin(self) -> ListLeadPurchasesForAdmin:
        return ListLeadPurchasesForAdmin(
            purchases=self.purchases, professionals=self.professionals, reviews=self.reviews
        )

    @property
    def admin_professionals(self) -> ListAdminProfessionals:
        return ListAdminProfessionals(
            professionals=self.professionals,
            categories=self.categories,
            accounts=self.accounts,
            clock=self.infra.clock,
        )

    @property
    def mark_purchase_for_review(self) -> MarkPurchaseForReview:
        return MarkPurchaseForReview(
            purchases=self.purchases,
            reviews=self.reviews,
            clock=self.infra.clock,
            ids=self.infra.ids,
            uow=self.uow,
        )

    @property
    def handle_payment_event(self) -> HandlePaymentEvent:
        return HandlePaymentEvent(
            purchases=self.purchases,
            leads=self.leads,
            processed_events=self.processed_events,
            payments=self.infra.payments,
            clock=self.infra.clock,
            uow=self.uow,
            credit=self.credit,
            subscriptions=ApplySubscriptionEvent(
                accounts=self.accounts, credit=self.credit, clock=self.infra.clock
            ),
            chargebacks=ApplyChargeback(
                accounts=self.accounts,
                ledger=self.ledger,
                credit=self.credit,
                clock=self.infra.clock,
            ),
        )

    @property
    def my_purchases(self) -> ListMyPurchases:
        return ListMyPurchases(
            purchases=self.purchases, leads=self.leads, categories=self.categories
        )

    @property
    def release_reservations(self) -> ReleaseExpiredReservations:
        return ReleaseExpiredReservations(
            purchases=self.purchases,
            payments=self.infra.payments,
            clock=self.infra.clock,
            uow=self.uow,
            credit=self.credit,
        )

    @property
    def start_subscription(self) -> StartSubscription:
        return StartSubscription(
            accounts=self.accounts,
            pricing=self.pricing,
            payments=self.infra.payments,
            clock=self.infra.clock,
            uow=self.uow,
            web_base_url=self.infra.settings.public_web_url,
            currency=self.infra.settings.default_currency,
        )

    @property
    def billing_portal(self) -> OpenBillingPortal:
        return OpenBillingPortal(
            accounts=self.accounts,
            payments=self.infra.payments,
            web_base_url=self.infra.settings.public_web_url,
        )

    @property
    def get_account(self) -> GetProfessionalAccount:
        return GetProfessionalAccount(
            accounts=self.accounts,
            ledger=self.ledger,
            pricing=self.pricing,
            clock=self.infra.clock,
        )

    @property
    def set_subscription_price(self) -> SetSubscriptionPrice:
        return SetSubscriptionPrice(
            prices=self.subscription_prices,
            pricing=self.pricing,
            payments=self.infra.payments,
            clock=self.infra.clock,
            ids=self.infra.ids,
            uow=self.uow,
            currency=self.infra.settings.default_currency,
        )

    @property
    def adjust_credit(self) -> AdjustProfessionalCredit:
        return AdjustProfessionalCredit(
            professionals=self.professionals,
            accounts=self.accounts,
            credit=self.credit,
            clock=self.infra.clock,
            ids=self.infra.ids,
            uow=self.uow,
            currency=self.infra.settings.default_currency,
        )

    @property
    def sync_user(self) -> SyncUserFromIdentity:
        return SyncUserFromIdentity(
            users=self.users, clock=self.infra.clock, ids=self.infra.ids, uow=self.uow
        )

    @property
    def upsert_profile(self) -> UpsertProfessionalProfile:
        return UpsertProfessionalProfile(
            professionals=self.professionals,
            categories=self.categories,
            postal_codes=self.postal_codes,
            clock=self.infra.clock,
            ids=self.infra.ids,
            uow=self.uow,
            service_area=ServiceArea.from_prefixes(self.infra.settings.covered_postal_prefixes),
        )

    @property
    def request_professional_upload(self) -> RequestProfessionalUpload:
        return RequestProfessionalUpload(media=self.infra.storage, documents=self.infra.documents)

    @property
    def add_professional_document(self) -> AddProfessionalDocument:
        return AddProfessionalDocument(
            professionals=self.professionals,
            clock=self.infra.clock,
            ids=self.infra.ids,
            uow=self.uow,
        )

    @property
    def remove_professional_document(self) -> RemoveProfessionalDocument:
        return RemoveProfessionalDocument(
            professionals=self.professionals, documents=self.infra.documents, uow=self.uow
        )

    @property
    def submit_for_review(self) -> SubmitForReview:
        return SubmitForReview(
            professionals=self.professionals,
            clock=self.infra.clock,
            ids=self.infra.ids,
            uow=self.uow,
        )

    @property
    def approve_professional(self) -> ApproveProfessional:
        return ApproveProfessional(
            professionals=self.professionals,
            clock=self.infra.clock,
            ids=self.infra.ids,
            uow=self.uow,
        )

    @property
    def reject_professional(self) -> RejectProfessional:
        return RejectProfessional(
            professionals=self.professionals,
            accounts=self.accounts,
            ledger=self.ledger,
            credit=self.credit,
            payments=self.infra.payments,
            clock=self.infra.clock,
            ids=self.infra.ids,
            uow=self.uow,
        )

    @property
    def verification_dossier(self) -> GetVerificationDossier:
        return GetVerificationDossier(
            professionals=self.professionals,
            categories=self.categories,
            users=self.users,
            documents=self.infra.documents,
        )

    @property
    def get_profile(self) -> GetProfessionalProfile:
        return GetProfessionalProfile(professionals=self.professionals, categories=self.categories)

    @property
    def list_categories(self) -> ListCategories:
        return ListCategories(categories=self.categories)

    @property
    def request_photo_upload(self) -> RequestPhotoUpload:
        return RequestPhotoUpload(storage=self.infra.storage)


def get_container(infra: InfraDep, session: SessionDep) -> RequestContainer:
    return RequestContainer.build(infra, session)


ContainerDep = Annotated[RequestContainer, Depends(get_container)]


# ------------------------------- Autenticacion ---------------------------


async def get_identity(
    infra: InfraDep,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedIdentity:
    """Valida el ID token de Firebase del header Authorization."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Falta el token de autenticacion"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        return await infra.token_verifier.verify(token)
    except DomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": exc.code, "message": exc.message},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


IdentityDep = Annotated[AuthenticatedIdentity, Depends(get_identity)]


async def get_current_user(container: ContainerDep, identity: IdentityDep) -> User:
    """Espeja la identidad de Firebase en nuestra tabla `users` y la devuelve."""
    return await container.sync_user.execute(identity)


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_professional(container: ContainerDep, user: CurrentUserDep) -> Professional:
    professional = await container.professionals.get_by_user_id(user.id)
    if professional is None:
        raise ProfessionalNotFoundError(
            "Completa tu perfil profesional antes de acceder a las solicitudes"
        )
    return professional


CurrentProfessionalDep = Annotated[Professional, Depends(get_current_professional)]


async def require_admin(user: CurrentUserDep) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PERMISSION_DENIED", "message": "Se requiere rol de administrador"},
        )
    return user


AdminDep = Annotated[User, Depends(require_admin)]


def get_locale(accept_language: Annotated[str | None, Header()] = None) -> str:
    """Idioma de la respuesta a partir de Accept-Language (es por defecto)."""
    if accept_language and accept_language.lower().strip().startswith("en"):
        return "en"
    return "es"


LocaleDep = Annotated[str, Depends(get_locale)]
