"""Listado global de compras y actividad diaria del dashboard."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.application.dto import AdminPurchaseQuery
from app.domain.exceptions import ValidationError
from app.domain.models import CreditEntry, CreditEntryKind, PurchaseStatus
from app.domain.value_objects import Money
from tests.conftest import World
from tests.factories import NOW, make_lead, make_purchase


class TestListAdminPurchases:
    async def test_lists_who_bought_what_without_client_contact(
        self, world: World, carpentry
    ) -> None:
        lead = make_lead(category_id=carpentry.id)
        world.leads.items[lead.id] = lead
        professional = world.add_professional(business_name="Reformas Sol")
        older = make_purchase(
            lead_id=lead.id,
            professional_id=professional.id,
            status=PurchaseStatus.PAID,
            paid_at=NOW,
            created_at=NOW - timedelta(days=2),
        )
        newer = make_purchase(
            lead_id=lead.id,
            professional_id=professional.id,
            status=PurchaseStatus.RESERVED,
            created_at=NOW,
        )
        world.purchases.items.update({older.id: older, newer.id: newer})

        result = await world.list_admin_purchases.execute(AdminPurchaseQuery())

        assert result.total == 2
        assert [item.purchase.id for item in result.items] == [newer.id, older.id]
        item = result.items[1]
        assert item.professional is not None
        assert item.professional.business_name == "Reformas Sol"
        assert item.lead is not None
        assert item.lead.title == lead.title
        assert item.category == carpentry
        assert lead.contact.phone.value not in repr(result)

    async def test_filters_by_status_professional_and_dates(self, world: World, carpentry) -> None:
        lead = make_lead(category_id=carpentry.id)
        world.leads.items[lead.id] = lead
        first = world.add_professional()
        second = world.add_professional()
        purchases = [
            make_purchase(
                lead_id=lead.id,
                professional_id=first.id,
                status=PurchaseStatus.PAID,
                created_at=NOW - timedelta(days=10),
            ),
            make_purchase(
                lead_id=lead.id,
                professional_id=first.id,
                status=PurchaseStatus.PAID,
                created_at=NOW,
            ),
            make_purchase(
                lead_id=lead.id,
                professional_id=second.id,
                status=PurchaseStatus.EXPIRED,
                created_at=NOW,
            ),
        ]
        world.purchases.items.update({purchase.id: purchase for purchase in purchases})

        paid = await world.list_admin_purchases.execute(
            AdminPurchaseQuery(status=PurchaseStatus.PAID)
        )
        by_professional = await world.list_admin_purchases.execute(
            AdminPurchaseQuery(professional_id=second.id)
        )
        recent = await world.list_admin_purchases.execute(
            AdminPurchaseQuery(from_day=NOW.date(), to_day=NOW.date())
        )

        assert paid.total == 2
        assert [item.purchase.id for item in by_professional.items] == [purchases[2].id]
        assert {item.purchase.id for item in recent.items} == {purchases[1].id, purchases[2].id}

    async def test_days_are_cut_in_madrid_time_both_ends_included(
        self, world: World, carpentry
    ) -> None:
        """Sea cual sea la zona del servidor: 23:30 UTC del 28-feb es 1-mar en Madrid."""
        lead = make_lead(category_id=carpentry.id)
        world.leads.items[lead.id] = lead
        late_night = make_purchase(
            lead_id=lead.id, created_at=datetime(2026, 2, 28, 23, 30, tzinfo=UTC)
        )
        end_of_day = make_purchase(
            lead_id=lead.id, created_at=datetime(2026, 3, 1, 22, 59, tzinfo=UTC)
        )
        next_day = make_purchase(
            lead_id=lead.id, created_at=datetime(2026, 3, 1, 23, 0, tzinfo=UTC)
        )
        world.purchases.items.update({p.id: p for p in (late_night, end_of_day, next_day)})

        march_first = await world.list_admin_purchases.execute(
            AdminPurchaseQuery(from_day=date(2026, 3, 1), to_day=date(2026, 3, 1))
        )
        february = await world.list_admin_purchases.execute(
            AdminPurchaseQuery(to_day=date(2026, 2, 28))
        )

        assert {item.purchase.id for item in march_first.items} == {late_night.id, end_of_day.id}
        assert february.total == 0

    async def test_rejects_an_inverted_date_range(self, world: World) -> None:
        with pytest.raises(ValidationError):
            await world.list_admin_purchases.execute(
                AdminPurchaseQuery(from_day=date(2026, 3, 2), to_day=date(2026, 3, 1))
            )


class TestMetricsTimeseries:
    async def test_defaults_to_the_last_30_days_with_empty_days(self, world: World) -> None:
        result = await world.metrics_timeseries.execute(start=None, end=None)

        assert result.timezone == "Europe/Madrid"
        assert result.end == NOW.date()
        assert result.start == NOW.date() - timedelta(days=29)
        assert len(result.points) == 30
        assert all(point.paid_purchases == 0 for point in result.points)

    async def test_buckets_by_madrid_day_not_utc(self, world: World, carpentry) -> None:
        # 23:30 UTC del 28-feb son las 00:30 del 1-mar en Madrid (UTC+1 en invierno).
        late_night = datetime(2026, 2, 28, 23, 30, tzinfo=UTC)
        lead = make_lead(category_id=carpentry.id, created_at=late_night)
        world.leads.items[lead.id] = lead
        paid = make_purchase(
            lead_id=lead.id,
            status=PurchaseStatus.PAID,
            price=Money(500, "EUR"),
            paid_at=late_night,
        )
        reserved = make_purchase(lead_id=lead.id, status=PurchaseStatus.RESERVED, paid_at=None)
        world.purchases.items.update({paid.id: paid, reserved.id: reserved})
        world.ledger.entries.append(
            CreditEntry(
                id=world.ids.new_id(),
                professional_id=world.ids.new_id(),
                kind=CreditEntryKind.TOPUP,
                amount=Money(1800, "EUR"),
                source_ref="in_1",
                created_at=NOW,
            )
        )

        result = await world.metrics_timeseries.execute(
            start=date(2026, 2, 28), end=date(2026, 3, 1)
        )

        feb, mar = result.points
        assert (feb.day, feb.leads_created, feb.paid_purchases) == (date(2026, 2, 28), 0, 0)
        assert mar.day == date(2026, 3, 1)
        assert mar.leads_created == 1
        assert mar.paid_purchases == 1
        assert mar.revenue_by_currency == {"EUR": 500}
        assert mar.topups == 1
        assert mar.topup_revenue_by_currency == {"EUR": 1800}

    async def test_rejects_inverted_or_too_long_ranges(self, world: World) -> None:
        with pytest.raises(ValidationError):
            await world.metrics_timeseries.execute(start=date(2026, 3, 2), end=date(2026, 3, 1))
        with pytest.raises(ValidationError):
            await world.metrics_timeseries.execute(start=date(2024, 1, 1), end=date(2026, 3, 1))
