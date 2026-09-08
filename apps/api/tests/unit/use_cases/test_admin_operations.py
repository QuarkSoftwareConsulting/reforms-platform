"""Tests del backoffice sin filtrar datos de contacto del cliente."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.application.dto import ConsentInput, CreateLeadInput
from app.application.ports import AdminLeadFilters
from app.domain.exceptions import ConsentRequiredError, PurchaseNotFoundError
from app.domain.models import LeadSource, LeadStatus, PurchaseStatus
from tests.conftest import World
from tests.factories import NOW, make_lead, make_purchase


class TestAdminLeadOperations:
    async def test_manual_lead_records_external_consent(self, world: World, carpentry) -> None:
        lead = await world.create_lead.execute(
            CreateLeadInput(
                category_id=carpentry.id,
                title="Cambiar persiana del salon",
                description="La persiana del salon esta atascada y necesito repararla esta semana.",
                postal_code="28001",
                client_name="Cliente de campana",
                client_phone="+34611223344",
                consent=ConsentInput(
                    accepted=True,
                    policy_version="2026-01-v1",
                    channel="Meta Lead Ads",
                    campaign_reference="marzo-madrid",
                    accepted_at=NOW - timedelta(days=1),
                ),
            ),
            source=LeadSource.ADMIN,
        )

        assert lead.source is LeadSource.ADMIN
        assert lead.consent is not None
        assert lead.consent.channel == "Meta Lead Ads"
        assert lead.consent.campaign_reference == "marzo-madrid"

    async def test_manual_lead_requires_external_channel(self, world: World, carpentry) -> None:
        with pytest.raises(ConsentRequiredError):
            await world.create_lead.execute(
                CreateLeadInput(
                    category_id=carpentry.id,
                    title="Cambiar persiana del salon",
                    description=(
                        "La persiana del salon esta atascada y necesito repararla esta semana."
                    ),
                    postal_code="28001",
                    client_name="Cliente de campana",
                    client_phone="+34611223344",
                    consent=ConsentInput(accepted=True, policy_version="2026-01-v1"),
                ),
                source=LeadSource.ADMIN,
            )

    async def test_list_and_disable_lead_do_not_change_its_purchases(
        self, world: World, carpentry
    ) -> None:
        lead = make_lead(category_id=carpentry.id, purchases_count=1)
        world.leads.items[lead.id] = lead

        result = await world.list_admin_leads.execute(AdminLeadFilters())
        assert result.items[0].lead.id == lead.id
        assert not hasattr(result.items[0], "contact")

        updated = await world.change_lead_availability.execute(lead_id=lead.id, publish=False)
        assert updated.status is LeadStatus.DISABLED
        assert updated.purchases_count == 1

    async def test_dashboard_groups_revenue_by_currency(self, world: World, carpentry) -> None:
        first = make_lead(category_id=carpentry.id)
        second = make_lead(category_id=carpentry.id)
        world.leads.items[first.id] = first
        world.leads.items[second.id] = second
        world.purchases.items[make_purchase(lead_id=first.id, status=PurchaseStatus.PAID).id] = (
            make_purchase(lead_id=first.id, status=PurchaseStatus.PAID)
        )
        euro = make_purchase(lead_id=second.id, status=PurchaseStatus.PAID)
        world.purchases.items[euro.id] = euro

        metrics = await world.admin_metrics.execute()

        assert metrics.leads_total == 2
        assert metrics.paid_purchases == 2
        assert metrics.paid_leads == 2
        assert metrics.revenue_by_currency == {"EUR": 1000}
        assert metrics.coverage_rate == 1

    async def test_review_is_append_only_and_does_not_change_purchase(
        self, world: World, carpentry
    ) -> None:
        lead = make_lead(category_id=carpentry.id)
        purchase = make_purchase(lead_id=lead.id, status=PurchaseStatus.PAID)
        world.leads.items[lead.id] = lead
        world.purchases.items[purchase.id] = purchase
        admin = world.add_user()

        review = await world.mark_purchase_for_review.execute(
            purchase_id=purchase.id, admin_user_id=admin.id, note="Comprobar posible duplicado"
        )

        assert review.purchase_id == purchase.id
        assert world.purchases.items[purchase.id].status is PurchaseStatus.PAID
        assert len(await world.reviews.list_for_purchase(purchase.id)) == 1

    async def test_review_of_unknown_purchase_fails(self, world: World) -> None:
        with pytest.raises(PurchaseNotFoundError):
            await world.mark_purchase_for_review.execute(
                purchase_id=make_purchase().id,
                admin_user_id=world.add_user().id,
                note="Comprobar posible duplicado",
            )
