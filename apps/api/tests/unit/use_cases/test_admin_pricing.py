"""Tests de los casos de uso de precios del admin.

Cubren las dos preguntas que importan: que se cobra realmente (el precio propio
gana al sugerido) y que un cambio de precio no reescribe ventas ya cerradas.
"""

import pytest

from app.domain.exceptions import (
    CategoryNotFoundError,
    CurrencyMismatchError,
    InvalidSalePriceError,
    LeadNotFoundError,
)
from app.domain.models import Category, Professional, PurchaseStatus
from app.domain.value_objects import Money
from tests.conftest import World
from tests.factories import make_lead


@pytest.fixture
def lead(world: World, carpentry: Category):
    item = make_lead(category_id=carpentry.id)
    world.leads.items[item.id] = item
    return item


class TestSetLeadPrice:
    async def test_admin_price_replaces_the_category_suggestion(
        self, world: World, lead, carpentry: Category
    ) -> None:
        pricing = await world.set_lead_price.execute(lead_id=lead.id, price=Money(1500, "EUR"))

        assert pricing.suggested_price == carpentry.suggested_lead_price
        assert pricing.sale_price == Money(1500, "EUR")
        assert pricing.is_custom is True
        assert world.leads.items[lead.id].price_override == Money(1500, "EUR")

    async def test_null_price_restores_the_category_suggestion(self, world: World, lead) -> None:
        await world.set_lead_price.execute(lead_id=lead.id, price=Money(1500, "EUR"))
        pricing = await world.set_lead_price.execute(lead_id=lead.id, price=None)

        assert pricing.is_custom is False
        assert pricing.sale_price == Money(500, "EUR")

    async def test_price_in_another_currency_rejected(self, world: World, lead) -> None:
        with pytest.raises(CurrencyMismatchError):
            await world.set_lead_price.execute(lead_id=lead.id, price=Money(1500, "USD"))

    async def test_zero_price_rejected(self, world: World, lead) -> None:
        with pytest.raises(InvalidSalePriceError):
            await world.set_lead_price.execute(lead_id=lead.id, price=Money(0, "EUR"))

    async def test_unknown_lead_rejected(self, world: World, lead) -> None:
        from uuid import uuid4

        with pytest.raises(LeadNotFoundError):
            await world.set_lead_price.execute(lead_id=uuid4(), price=Money(900, "EUR"))

    async def test_lead_without_category_rejected(self, world: World) -> None:
        orphan = make_lead()
        world.leads.items[orphan.id] = orphan
        with pytest.raises(CategoryNotFoundError):
            await world.set_lead_price.execute(lead_id=orphan.id, price=Money(900, "EUR"))


class TestPurchaseUsesTheAdminPrice:
    async def test_reservation_is_charged_at_the_admin_price(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        await world.set_lead_price.execute(lead_id=lead.id, price=Money(2500, "EUR"))

        result = await world.start_purchase.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )

        assert result.amount == Money(2500, "EUR")
        assert world.purchases.items[result.purchase_id].price == Money(2500, "EUR")
        # La pasarela tiene que cobrar lo mismo que dice la reserva.
        assert world.payments.sessions[result.checkout_session_id].amount == Money(2500, "EUR")

    async def test_price_change_does_not_rewrite_an_existing_purchase(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        result = await world.start_purchase.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )
        await world.set_lead_price.execute(lead_id=lead.id, price=Money(9900, "EUR"))

        purchase = world.purchases.items[result.purchase_id]
        assert purchase.status is PurchaseStatus.RESERVED
        assert purchase.price == Money(500, "EUR")

    async def test_explorer_shows_the_admin_price(
        self, world: World, lead, madrid_carpenter: Professional
    ) -> None:
        await world.set_lead_price.execute(lead_id=lead.id, price=Money(1200, "EUR"))

        listing = await world.list_leads.execute(professional_id=madrid_carpenter.id)
        detail = await world.lead_detail.execute(
            lead_id=lead.id, professional_id=madrid_carpenter.id
        )

        assert [item.price for item in listing.items] == [Money(1200, "EUR")]
        assert detail.price == Money(1200, "EUR")


class TestSetCategorySuggestedPrice:
    async def test_changes_the_price_of_future_leads_without_override(
        self, world: World, lead, carpentry: Category
    ) -> None:
        await world.set_category_price.execute(category_id=carpentry.id, price=Money(800, "EUR"))

        pricing = await world.lead_pricing.execute(lead_id=lead.id)
        assert pricing.suggested_price == Money(800, "EUR")
        assert pricing.sale_price == Money(800, "EUR")
        assert pricing.is_custom is False

    async def test_does_not_touch_leads_with_their_own_price(
        self, world: World, lead, carpentry: Category
    ) -> None:
        await world.set_lead_price.execute(lead_id=lead.id, price=Money(1500, "EUR"))
        await world.set_category_price.execute(category_id=carpentry.id, price=Money(800, "EUR"))

        pricing = await world.lead_pricing.execute(lead_id=lead.id)
        assert pricing.suggested_price == Money(800, "EUR")
        assert pricing.sale_price == Money(1500, "EUR")

    async def test_zero_price_rejected(self, world: World, carpentry: Category) -> None:
        with pytest.raises(InvalidSalePriceError):
            await world.set_category_price.execute(category_id=carpentry.id, price=Money(0, "EUR"))
        assert world.categories.items[carpentry.id].suggested_lead_price == Money(500, "EUR")
