"""Tests de integracion del flujo de compra con Postgres real.

Cubren lo que los fakes no pueden garantizar: el indice unico parcial, el conteo
de plazas en SQL y la idempotencia del webhook apoyada en la clave primaria de
`processed_payment_events`.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.ports import PaymentEventType
from app.application.use_cases import HandlePaymentEvent, StartLeadPurchase
from app.domain.exceptions import LeadCapReachedError
from app.domain.models import (
    Category,
    LeadStatus,
    Professional,
    Purchase,
    PurchaseStatus,
    User,
    UserRole,
)
from app.domain.value_objects import Email, Money, PhoneNumber, PostalCode
from app.infrastructure.adapters.db.repositories import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyProcessedEventRepository,
    SqlAlchemyProfessionalRepository,
    SqlAlchemyPurchaseRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.adapters.db.session import SqlAlchemyUnitOfWork
from tests.factories import MADRID, make_lead
from tests.fakes import FakeClock, FakePaymentGateway, SequentialIdGenerator

pytestmark = pytest.mark.integration

WEB_URL = "https://reformahub.test"


def purchase_use_case(session: AsyncSession, clock: FakeClock, gateway: FakePaymentGateway):
    return StartLeadPurchase(
        leads=SqlAlchemyLeadRepository(session),
        purchases=SqlAlchemyPurchaseRepository(session),
        professionals=SqlAlchemyProfessionalRepository(session),
        categories=SqlAlchemyCategoryRepository(session),
        payments=gateway,
        clock=clock,
        ids=SequentialIdGenerator(),
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
    )


async def add_professional(
    session: AsyncSession, category: Category, *, radius_km: int = 25
) -> Professional:
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
