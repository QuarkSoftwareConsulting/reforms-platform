"""Tests de integracion del repositorio de leads: PostGIS y bloqueo de fila."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports import LeadSearchFilters
from app.domain.models import (
    Category,
    LeadSource,
    LeadStatus,
    Professional,
    Purchase,
    PurchaseStatus,
)
from app.domain.value_objects import Coordinates, Money, PostalCode
from app.infrastructure.adapters.db.repositories import (
    SqlAlchemyLeadRepository,
    SqlAlchemyPurchaseRepository,
)
from tests.factories import BARCELONA, MADRID, make_consent, make_lead, make_lead_location

pytestmark = pytest.mark.integration

ALCALA = Coordinates(40.4818, -3.3644)


async def store_lead(session: AsyncSession, category: Category, **kwargs: object):
    repo = SqlAlchemyLeadRepository(session)
    lead = make_lead(category_id=category.id, **kwargs)
    stored = await repo.add(lead)
    await session.commit()
    return stored


class TestPersistence:
    async def test_lead_round_trips_through_postgres(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        original = await store_lead(session, carpentry)
        repo = SqlAlchemyLeadRepository(session)

        loaded = await repo.get(original.id)

        assert loaded is not None
        assert loaded.title == original.title
        assert loaded.contact.phone.value == original.contact.phone.value
        assert loaded.location.city == "Madrid"
        # PostGIS almacena las coordenadas y las devuelve sin perder precision util.
        assert loaded.location.coordinates.latitude == pytest.approx(MADRID.latitude, abs=1e-6)
        assert loaded.location.coordinates.longitude == pytest.approx(MADRID.longitude, abs=1e-6)

    async def test_consent_record_is_persisted(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        stored = await store_lead(session, carpentry)
        loaded = await SqlAlchemyLeadRepository(session).get(stored.id)

        assert loaded is not None
        assert loaded.consent is not None
        assert loaded.consent.ip_address == "83.45.12.9"
        assert loaded.consent.policy_version == "2026-01-v1"
        assert loaded.consent.max_recipients == 3

    async def test_photos_keep_their_order(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        from app.domain.models import LeadPhoto

        stored = await store_lead(
            session,
            carpentry,
            photos=[
                LeadPhoto(storage_key="leads/b.jpg", sort_order=1),
                LeadPhoto(storage_key="leads/a.jpg", sort_order=0),
            ],
        )
        loaded = await SqlAlchemyLeadRepository(session).get(stored.id)
        assert loaded is not None
        assert [p.storage_key for p in loaded.photos] == ["leads/a.jpg", "leads/b.jpg"]

    async def test_admin_lead_with_external_consent_persists(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        stored = await store_lead(
            session,
            carpentry,
            source=LeadSource.ADMIN,
            consent=make_consent(channel="Meta Lead Ads", campaign_reference="marzo-madrid"),
        )
        loaded = await SqlAlchemyLeadRepository(session).get(stored.id)
        assert loaded is not None
        assert loaded.source is LeadSource.ADMIN
        assert loaded.consent is not None
        assert loaded.consent.channel == "Meta Lead Ads"

    async def test_price_override_round_trips_with_its_currency(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        stored = await store_lead(session, carpentry, price_override=Money(2500, "EUR"))
        loaded = await SqlAlchemyLeadRepository(session).get(stored.id)

        assert loaded is not None
        assert loaded.price_override == Money(2500, "EUR")
        assert loaded.sale_price(suggested=carpentry.suggested_lead_price) == Money(2500, "EUR")

    async def test_clearing_the_price_override_nulls_both_columns(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        stored = await store_lead(session, carpentry, price_override=Money(2500, "EUR"))
        repo = SqlAlchemyLeadRepository(session)

        stored.set_price_override(None, suggested=carpentry.suggested_lead_price)
        await repo.update(stored)
        await session.commit()

        loaded = await repo.get(stored.id)
        assert loaded is not None
        assert loaded.price_override is None
        assert loaded.sale_price(suggested=carpentry.suggested_lead_price) == Money(500, "EUR")

    async def test_half_a_price_override_is_rejected_by_the_database(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        """Importe sin divisa dejaria una fila que el mapeador no sabe interpretar."""
        from sqlalchemy import text

        stored = await store_lead(session, carpentry)
        update = text("UPDATE leads SET price_override_cents = 2500 WHERE id = :id")
        with pytest.raises(IntegrityError):
            await session.execute(update, {"id": stored.id})
        await session.rollback()

    async def test_purchases_count_cannot_exceed_cap_in_the_database(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        """La BD es la ultima linea de defensa del cap, no solo el dominio."""
        stored = await store_lead(session, carpentry, max_purchases=2)
        repo = SqlAlchemyLeadRepository(session)

        stored.purchases_count = 5  # se salta las reglas del dominio a proposito
        with pytest.raises(IntegrityError):
            await repo.update(stored)
        await session.rollback()


class TestGeoSearch:
    async def test_st_dwithin_filters_by_radius(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        near = await store_lead(session, carpentry)
        far = await store_lead(
            session,
            carpentry,
            location=make_lead_location(
                postal_code=PostalCode("08001"),
                city="Barcelona",
                province="Barcelona",
                coordinates=BARCELONA,
            ),
        )

        repo = SqlAlchemyLeadRepository(session)
        rows = await repo.search(
            LeadSearchFilters(category_ids={carpentry.id}, center=MADRID, radius_km=25)
        )
        found = {row.lead.id for row in rows}

        assert near.id in found
        assert far.id not in found

    async def test_distance_is_returned_in_kilometres(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        await store_lead(
            session,
            carpentry,
            location=make_lead_location(
                postal_code=PostalCode("28801"),
                city="Alcala de Henares",
                coordinates=ALCALA,
            ),
        )
        rows = await SqlAlchemyLeadRepository(session).search(
            LeadSearchFilters(category_ids={carpentry.id}, center=MADRID, radius_km=50)
        )
        assert rows[0].distance_km == pytest.approx(28, abs=3)

    async def test_widening_the_radius_finds_more_leads(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        await store_lead(
            session,
            carpentry,
            location=make_lead_location(
                postal_code=PostalCode("28801"),
                city="Alcala de Henares",
                coordinates=ALCALA,
            ),
        )
        repo = SqlAlchemyLeadRepository(session)

        narrow = await repo.search(
            LeadSearchFilters(category_ids={carpentry.id}, center=MADRID, radius_km=20)
        )
        wide = await repo.search(
            LeadSearchFilters(category_ids={carpentry.id}, center=MADRID, radius_km=40)
        )
        assert len(narrow) == 0
        assert len(wide) == 1

    async def test_only_published_leads_are_returned(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        await store_lead(session, carpentry, status=LeadStatus.DISABLED)
        await store_lead(session, carpentry, status=LeadStatus.EXHAUSTED, purchases_count=3)
        visible = await store_lead(session, carpentry)

        repo = SqlAlchemyLeadRepository(session)
        filters = LeadSearchFilters(category_ids={carpentry.id}, center=MADRID, radius_km=25)

        rows = await repo.search(filters)
        assert [row.lead.id for row in rows] == [visible.id]
        assert await repo.count(filters) == 1

    async def test_search_flags_leads_already_purchased(
        self, session: AsyncSession, carpentry: Category, madrid_carpenter: Professional
    ) -> None:
        purchased = await store_lead(session, carpentry)
        other = await store_lead(session, carpentry)

        purchases = SqlAlchemyPurchaseRepository(session)
        await purchases.add(
            Purchase(
                id=uuid4(),
                lead_id=purchased.id,
                professional_id=madrid_carpenter.id,
                price=Money(500, "EUR"),
                status=PurchaseStatus.PAID,
                created_at=datetime.now(UTC),
                paid_at=datetime.now(UTC),
            )
        )
        await session.commit()

        rows = await SqlAlchemyLeadRepository(session).search(
            LeadSearchFilters(category_ids={carpentry.id}, center=MADRID, radius_km=25),
            requester_professional_id=madrid_carpenter.id,
        )
        flags = {row.lead.id: row.purchased_by_requester for row in rows}
        assert flags[purchased.id] is True
        assert flags[other.id] is False

    async def test_pagination_and_ordering_by_recency(
        self, session: AsyncSession, carpentry: Category
    ) -> None:
        base = datetime.now(UTC)
        for index in range(5):
            await store_lead(session, carpentry, created_at=base - timedelta(hours=index))

        repo = SqlAlchemyLeadRepository(session)
        page = await repo.search(
            LeadSearchFilters(
                category_ids={carpentry.id}, center=MADRID, radius_km=25, limit=2, offset=0
            )
        )
        assert len(page) == 2
        assert page[0].lead.created_at > page[1].lead.created_at


class TestRowLocking:
    async def test_for_update_serializes_concurrent_transactions(
        self, engine, carpentry: Category, session: AsyncSession
    ) -> None:
        """Comprueba con Postgres real que `get_for_update` bloquea de verdad.

        Dos sesiones distintas piden el mismo lead con FOR UPDATE. La segunda debe
        quedarse esperando hasta que la primera cierre su transaccion; si el
        bloqueo no existiera, ambas avanzarian en paralelo.
        """
        stored = await store_lead(session, carpentry)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        order: list[str] = []

        async def first() -> None:
            async with factory() as s1:
                await SqlAlchemyLeadRepository(s1).get_for_update(stored.id)
                order.append("primera-bloquea")
                await asyncio.sleep(0.3)
                order.append("primera-commit")
                await s1.commit()

        async def second() -> None:
            await asyncio.sleep(0.05)  # asegura que la primera bloquea antes
            async with factory() as s2:
                await SqlAlchemyLeadRepository(s2).get_for_update(stored.id)
                order.append("segunda-obtiene-bloqueo")
                await s2.commit()

        await asyncio.wait_for(asyncio.gather(first(), second()), timeout=10)

        assert order == ["primera-bloquea", "primera-commit", "segunda-obtiene-bloqueo"]
