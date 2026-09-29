"""Tests de integracion del flujo de compra con Postgres real.

Cubren lo que los fakes no pueden garantizar: el indice unico parcial, el conteo
de plazas en SQL, la idempotencia del webhook apoyada en la clave primaria de
`processed_payment_events` y el bloqueo real de la cuenta al gastar saldo.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.ports import PaymentEventType
from app.application.use_cases import (
    ApplySubscriptionEvent,
    CreditLedgerService,
    HandlePaymentEvent,
    StartLeadPurchase,
)
from app.domain.exceptions import LeadCapReachedError
from app.domain.models import (
    Category,
    CreditEntryKind,
    LeadStatus,
    Professional,
    ProfessionalAccount,
    Purchase,
    PurchaseStatus,
    User,
    UserRole,
)
from app.domain.value_objects import Email, Money, PhoneNumber, PostalCode
from app.infrastructure.adapters.clock import Uuid4Generator
from app.infrastructure.adapters.db.repositories import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyCreditLedgerRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyProcessedEventRepository,
    SqlAlchemyProfessionalAccountRepository,
    SqlAlchemyProfessionalRepository,
    SqlAlchemyPurchaseRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.adapters.db.session import SqlAlchemyUnitOfWork
from tests.factories import MADRID, make_account, make_lead
from tests.fakes import FakeClock, FakePaymentGateway

pytestmark = pytest.mark.integration

WEB_URL = "https://reformahub.test"


def credit_service(session: AsyncSession) -> CreditLedgerService:
    return CreditLedgerService(
        accounts=SqlAlchemyProfessionalAccountRepository(session),
        ledger=SqlAlchemyCreditLedgerRepository(session),
        ids=Uuid4Generator(),
    )


class BarrierAccountRepository(SqlAlchemyProfessionalAccountRepository):
    """Obliga a que dos compras lleguen a la vez a la lectura bloqueante de la cuenta.

    Sin la barrera la carrera depende del azar del planificador y el test podria
    pasar aunque faltara el FOR UPDATE. La espera va ANTES de la lectura: con el
    bloqueo, la segunda SELECT espera en Postgres a que la primera confirme.
    """

    def __init__(self, session: AsyncSession, barrier: asyncio.Barrier) -> None:
        super().__init__(session)
        self._barrier = barrier

    async def get_for_update(self, professional_id: UUID) -> ProfessionalAccount | None:
        await self._barrier.wait()
        return await super().get_for_update(professional_id)


def purchase_use_case(
    session: AsyncSession,
    clock: FakeClock,
    gateway: FakePaymentGateway,
    *,
    accounts: SqlAlchemyProfessionalAccountRepository | None = None,
):
    accounts = accounts or SqlAlchemyProfessionalAccountRepository(session)
    return StartLeadPurchase(
        leads=SqlAlchemyLeadRepository(session),
        purchases=SqlAlchemyPurchaseRepository(session),
        professionals=SqlAlchemyProfessionalRepository(session),
        categories=SqlAlchemyCategoryRepository(session),
        accounts=accounts,
        credit=CreditLedgerService(
            accounts=accounts,
            ledger=SqlAlchemyCreditLedgerRepository(session),
            ids=Uuid4Generator(),
        ),
        payments=gateway,
        clock=clock,
        # UUID reales: dos casos de uso en conexiones paralelas no deben repetir ids.
        ids=Uuid4Generator(),
        uow=SqlAlchemyUnitOfWork(session),
        web_base_url=WEB_URL,
        reservation_ttl_minutes=30,
    )


def webhook_use_case(session: AsyncSession, clock: FakeClock, gateway: FakePaymentGateway):
    return HandlePaymentEvent(
        purchases=SqlAlchemyPurchaseRepository(session),
        leads=SqlAlchemyLeadRepository(session),
        processed_events=SqlAlchemyProcessedEventRepository(session),
        payments=gateway,
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session),
        credit=credit_service(session),
        subscriptions=ApplySubscriptionEvent(
            accounts=SqlAlchemyProfessionalAccountRepository(session),
            credit=credit_service(session),
            clock=clock,
        ),
    )


async def add_professional(
    session: AsyncSession,
    category: Category,
    *,
    radius_km: int = 25,
    balance_cents: int | None = 0,
) -> Professional:
    """Profesional con la recarga al dia (`balance_cents=None`: sin cuenta)."""
    users = SqlAlchemyUserRepository(session)
    professionals = SqlAlchemyProfessionalRepository(session)
    suffix = uuid4().hex[:8]
    user = await users.add(
        User(
            id=uuid4(),
            firebase_uid=f"fb-{suffix}",
            email=Email(f"pro-{suffix}@example.com"),
            role=UserRole.PROFESSIONAL,
            created_at=datetime.now(UTC),
        )
    )
    professional = await professionals.add(
        Professional(
            id=uuid4(),
            user_id=user.id,
            business_name=f"Taller {suffix}",
            phone=PhoneNumber("+34600111222"),
            base_postal_code=PostalCode("28001"),
            base_coordinates=MADRID,
            service_radius_km=radius_km,
            created_at=datetime.now(UTC),
            city="Madrid",
            province="Madrid",
            category_ids={category.id},
        )
    )
    if balance_cents is not None:
        await SqlAlchemyProfessionalAccountRepository(session).add(
            make_account(professional_id=professional.id, balance_cents=balance_cents)
        )
    await session.commit()
    return professional


class TestPartialUniqueIndex:
    async def test_database_rejects_two_active_purchases_of_the_same_lead(
        self, session: AsyncSession, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        leads = SqlAlchemyLeadRepository(session)
        purchases = SqlAlchemyPurchaseRepository(session)
        lead = await leads.add(make_lead(category_id=carpentry.id))
        await session.commit()

        def build(status: PurchaseStatus) -> Purchase:
            return Purchase(
                id=uuid4(),
                lead_id=lead.id,
                professional_id=madrid_carpenter.id,
                price=Money(500, "EUR"),
                status=status,
                created_at=datetime.now(UTC),
                reserved_until=datetime.now(UTC) + timedelta(minutes=30),
            )

        await purchases.add(build(PurchaseStatus.RESERVED))
        await session.commit()

        # El indice unico parcial salta ya en el flush, sin esperar al commit.
        with pytest.raises(IntegrityError):
            await purchases.add(build(PurchaseStatus.RESERVED))
        await session.rollback()

    async def test_expired_purchase_does_not_block_a_retry(
        self, session: AsyncSession, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        """Tras un checkout abandonado, el profesional debe poder reintentar."""
        leads = SqlAlchemyLeadRepository(session)
        purchases = SqlAlchemyPurchaseRepository(session)
        lead = await leads.add(make_lead(category_id=carpentry.id))
        await purchases.add(
            Purchase(
                id=uuid4(),
                lead_id=lead.id,
                professional_id=madrid_carpenter.id,
                price=Money(500, "EUR"),
                status=PurchaseStatus.EXPIRED,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

        retry = await purchases.add(
            Purchase(
                id=uuid4(),
                lead_id=lead.id,
                professional_id=madrid_carpenter.id,
                price=Money(500, "EUR"),
                status=PurchaseStatus.RESERVED,
                created_at=datetime.now(UTC),
                reserved_until=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        await session.commit()
        assert retry.status is PurchaseStatus.RESERVED


class TestSlotCounting:
    async def test_expired_reservations_are_not_counted_as_occupied(
        self, session: AsyncSession, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        leads = SqlAlchemyLeadRepository(session)
        purchases = SqlAlchemyPurchaseRepository(session)
        lead = await leads.add(make_lead(category_id=carpentry.id))
        now = datetime.now(UTC)

        await purchases.add(
            Purchase(
                id=uuid4(),
                lead_id=lead.id,
                professional_id=madrid_carpenter.id,
                price=Money(500, "EUR"),
                status=PurchaseStatus.RESERVED,
                created_at=now - timedelta(hours=2),
                reserved_until=now - timedelta(hours=1),
            )
        )
        await session.commit()

        assert await purchases.count_occupied_slots(lead.id, now=now) == 0
        assert (
            await purchases.find_active_for_lead_and_professional(
                lead.id, madrid_carpenter.id, now=now
            )
            is None
        )

    async def test_refunded_purchases_still_occupy_a_slot(
        self, session: AsyncSession, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        leads = SqlAlchemyLeadRepository(session)
        purchases = SqlAlchemyPurchaseRepository(session)
        lead = await leads.add(make_lead(category_id=carpentry.id))
        now = datetime.now(UTC)
        await purchases.add(
            Purchase(
                id=uuid4(),
                lead_id=lead.id,
                professional_id=madrid_carpenter.id,
                price=Money(500, "EUR"),
                status=PurchaseStatus.REFUNDED,
                created_at=now,
                paid_at=now,
            )
        )
        await session.commit()
        assert await purchases.count_occupied_slots(lead.id, now=now) == 1


class TestEndToEndPurchase:
    async def test_full_flow_reserves_pays_and_exhausts_the_lead(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        clock = FakeClock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC))
        gateway = FakePaymentGateway()
        leads = SqlAlchemyLeadRepository(session)

        lead = await leads.add(make_lead(category_id=carpentry.id, max_purchases=2))
        await session.commit()

        start = purchase_use_case(session, clock, gateway)
        webhook = webhook_use_case(session, clock, gateway)

        for index in range(2):
            professional = await add_professional(session, carpentry)
            reservation = await start.execute(lead_id=lead.id, professional_id=professional.id)
            outcome = await webhook.execute(
                payload=FakePaymentGateway.event_payload(
                    event_id=f"evt_{index}",
                    event_type=PaymentEventType.CHECKOUT_COMPLETED,
                    purchase_id=reservation.purchase_id,
                ),
                signature="valid-signature",
            )
            assert outcome.handled is True

        refreshed = await leads.get(lead.id)
        assert refreshed is not None
        assert refreshed.purchases_count == 2
        assert refreshed.status is LeadStatus.EXHAUSTED

        third = await add_professional(session, carpentry)
        with pytest.raises(LeadCapReachedError):
            await start.execute(lead_id=lead.id, professional_id=third.id)

    async def test_webhook_replay_does_not_double_count(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        clock = FakeClock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC))
        gateway = FakePaymentGateway()
        leads = SqlAlchemyLeadRepository(session)
        lead = await leads.add(make_lead(category_id=carpentry.id, max_purchases=3))
        await session.commit()

        professional = await add_professional(session, carpentry)
        reservation = await purchase_use_case(session, clock, gateway).execute(
            lead_id=lead.id, professional_id=professional.id
        )
        webhook = webhook_use_case(session, clock, gateway)
        payload = FakePaymentGateway.event_payload(
            event_id="evt_replay",
            event_type=PaymentEventType.CHECKOUT_COMPLETED,
            purchase_id=reservation.purchase_id,
        )

        first = await webhook.execute(payload=payload, signature="valid-signature")
        second = await webhook.execute(payload=payload, signature="valid-signature")

        assert first.handled is True
        assert second.duplicate is True

        refreshed = await leads.get(lead.id)
        assert refreshed is not None
        assert refreshed.purchases_count == 1

    async def test_concurrent_buyers_of_the_last_slot_with_real_locking(
        self, engine: AsyncEngine, session: AsyncSession, carpentry: Category
    ) -> None:
        """La carrera del cap contra Postgres real, en dos conexiones distintas."""
        clock = FakeClock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC))
        gateway = FakePaymentGateway()
        leads = SqlAlchemyLeadRepository(session)
        lead = await leads.add(make_lead(category_id=carpentry.id, max_purchases=1))
        pro_a = await add_professional(session, carpentry)
        pro_b = await add_professional(session, carpentry)
        await session.commit()

        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

        async def buy(professional_id: object) -> object:
            async with factory() as own_session:
                use_case = purchase_use_case(own_session, clock, gateway)
                return await use_case.execute(
                    lead_id=lead.id,
                    professional_id=professional_id,  # type: ignore[arg-type]
                )

        results = await asyncio.wait_for(
            asyncio.gather(buy(pro_a.id), buy(pro_b.id), return_exceptions=True),
            timeout=20,
        )

        successes = [r for r in results if not isinstance(r, BaseException)]
        failures = [r for r in results if isinstance(r, BaseException)]

        assert len(successes) == 1, f"deberia venderse una sola plaza, no {len(successes)}"
        assert isinstance(failures[0], LeadCapReachedError)


class TestCreditWithRealLocking:
    async def test_the_same_balance_cannot_be_spent_twice_across_connections(
        self, engine: AsyncEngine, session: AsyncSession, carpentry: Category
    ) -> None:
        """Dos compras simultaneas en conexiones distintas con saldo para una sola.

        Sin el FOR UPDATE de la cuenta ambas leerian el saldo completo y lo
        gastarian dos veces (actualizacion perdida).
        """
        clock = FakeClock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC))
        gateway = FakePaymentGateway()
        leads = SqlAlchemyLeadRepository(session)
        lead_a = await leads.add(make_lead(category_id=carpentry.id))
        lead_b = await leads.add(make_lead(category_id=carpentry.id))
        buyer = await add_professional(session, carpentry, balance_cents=500)
        await session.commit()

        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        barrier = asyncio.Barrier(2)

        async def buy(lead_id: object) -> object:
            async with factory() as own_session:
                use_case = purchase_use_case(
                    own_session,
                    clock,
                    gateway,
                    accounts=BarrierAccountRepository(own_session, barrier),
                )
                return await use_case.execute(
                    lead_id=lead_id,  # type: ignore[arg-type]
                    professional_id=buyer.id,
                )

        results = await asyncio.wait_for(asyncio.gather(buy(lead_a.id), buy(lead_b.id)), timeout=20)

        assert sorted(r.paid_with_credit for r in results) == [False, True]  # type: ignore[attr-defined]
        async with factory() as check:
            account = await SqlAlchemyProfessionalAccountRepository(check).get(buyer.id)
            entries = await SqlAlchemyCreditLedgerRepository(check).list_for_professional(buyer.id)
        assert account is not None
        assert account.balance.amount_cents == 0
        assert [e.kind for e in entries] == [CreditEntryKind.SPEND]

    async def test_resent_invoice_is_credited_once(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        clock = FakeClock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC))
        gateway = FakePaymentGateway()
        buyer = await add_professional(session, carpentry, balance_cents=0)
        account = await SqlAlchemyProfessionalAccountRepository(session).get(buyer.id)
        assert account is not None
        assert account.stripe_customer_id is not None
        webhook = webhook_use_case(session, clock, gateway)

        # El mismo cobro llega con dos event_id distintos: el libro es el cerrojo.
        for event_id in ("evt_a", "evt_b"):
            await webhook.execute(
                payload=FakePaymentGateway.subscription_event_payload(
                    event_id=event_id,
                    event_type=PaymentEventType.INVOICE_PAID,
                    customer_id=account.stripe_customer_id,
                    invoice_id="in_unico",
                    amount_cents=1800,
                ),
                signature="valid-signature",
            )

        refreshed = await SqlAlchemyProfessionalAccountRepository(session).get(buyer.id)
        assert refreshed is not None
        assert refreshed.balance.amount_cents == 1800

    async def test_database_rejects_a_negative_balance(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        """Ultima barrera: aunque el dominio fallara, Postgres no acepta saldo negativo."""
        from sqlalchemy import text

        buyer = await add_professional(session, carpentry, balance_cents=100)
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "UPDATE professional_accounts SET balance_cents = -1 "
                    "WHERE professional_id = :pid"
                ),
                {"pid": buyer.id},
            )
        await session.rollback()
