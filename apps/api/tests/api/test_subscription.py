"""Tests HTTP de la mensualidad: sin ella no se ven ni se compran solicitudes."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.application.ports import PaymentEventType
from app.domain.models import Category
from tests.api.test_lead_lifecycle import (
    CLIENT_PHONE,
    activate_subscription,
    create_profile,
    publish_lead,
)
from tests.fakes import FakePaymentGateway
from tests.fakes.payments import VALID_SIGNATURE

pytestmark = pytest.mark.integration


async def account(api: AsyncClient, headers: dict[str, str]) -> dict:
    response = await api.get("/me/account", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class TestWithoutSubscription:
    async def test_professional_can_browse_but_not_buy(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth, subscribed=False)

        listing = await api.get("/leads", headers=pro_auth)
        assert listing.status_code == 200
        assert [item["id"] for item in listing.json()["items"]] == [created["id"]]
        detail = await api.get(f"/leads/{created['id']}", headers=pro_auth)
        assert detail.status_code == 200
        assert detail.json()["contact"] is None

        response = await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)
        assert response.status_code == 402
        assert response.json()["code"] == "SUBSCRIPTION_REQUIRED"

    async def test_me_reports_the_inactive_account(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        await create_profile(api, carpentry_category, pro_auth, subscribed=False)
        me = (await api.get("/me", headers=pro_auth)).json()
        assert me["account"]["status"] == "none"
        assert me["account"]["is_active"] is False
        assert me["account"]["topup_amount"]["amount_cents"] == 1800

    async def test_returning_from_checkout_does_not_activate(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        """Solo el webhook activa la cuenta: iniciar el checkout no basta."""
        await create_profile(api, carpentry_category, pro_auth, subscribed=False)
        started = await api.post("/me/subscription/checkout", headers=pro_auth)
        assert started.status_code == 200
        assert (await account(api, pro_auth))["is_active"] is False

    async def test_portal_without_subscription_is_refused(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        await create_profile(api, carpentry_category, pro_auth, subscribed=False)
        response = await api.post("/me/subscription/portal", headers=pro_auth)
        assert response.status_code == 402


class TestWithSubscription:
    async def test_topup_is_credited_once_and_listed(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        await create_profile(api, carpentry_category, pro_auth, subscribed=False)
        started = await api.post("/me/subscription/checkout", headers=pro_auth)
        customer_id = started.json()["checkout_url"].split("customer=")[1]

        payload = FakePaymentGateway.subscription_event_payload(
            event_id="evt_inv_dup",
            event_type=PaymentEventType.INVOICE_PAID,
            customer_id=customer_id,
            invoice_id="in_dup",
            amount_cents=1800,
        )
        for _ in range(2):
            response = await api.post(
                "/webhooks/stripe", content=payload, headers={"Stripe-Signature": VALID_SIGNATURE}
            )
            assert response.status_code == 200

        state = await account(api, pro_auth)
        assert state["status"] == "active"
        assert state["is_active"] is True
        assert state["balance"]["amount_cents"] == 1800
        assert [entry["kind"] for entry in state["entries"]] == ["topup"]

    async def test_second_subscription_is_refused(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        await create_profile(api, carpentry_category, pro_auth)
        response = await api.post("/me/subscription/checkout", headers=pro_auth)
        assert response.status_code == 409
        assert response.json()["code"] == "SUBSCRIPTION_ALREADY_EXISTS"

    async def test_balance_pays_the_contact_without_checkout(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        pro_auth: dict[str, str],
        fake_gateway: FakePaymentGateway,
    ) -> None:
        created = await publish_lead(api, carpentry_category)  # precio 5 EUR
        await create_profile(api, carpentry_category, pro_auth, subscribed=False)
        await activate_subscription(api, pro_auth, topup_cents=1800)

        response = await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["paid_with_credit"] is True
        assert body["checkout_url"] is None
        assert body["amount_due"]["amount_cents"] == 0
        assert fake_gateway.requests == [], "no se abre checkout de compra"

        detail = (await api.get(f"/leads/{created['id']}", headers=pro_auth)).json()
        assert detail["is_unlocked"] is True
        assert detail["contact"]["phone"] == CLIENT_PHONE
        assert (await account(api, pro_auth))["balance"]["amount_cents"] == 1300

    async def test_partial_balance_opens_checkout_for_the_rest(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        pro_auth: dict[str, str],
        fake_gateway: FakePaymentGateway,
    ) -> None:
        created = await publish_lead(api, carpentry_category)  # precio 5 EUR
        await create_profile(api, carpentry_category, pro_auth, subscribed=False)
        await activate_subscription(api, pro_auth, topup_cents=300)

        body = (await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)).json()

        assert body["paid_with_credit"] is False
        assert body["credit_applied"]["amount_cents"] == 300
        assert fake_gateway.requests[-1].amount.amount_cents == 200
        detail = (await api.get(f"/leads/{created['id']}", headers=pro_auth)).json()
        assert detail["is_unlocked"] is False, "sin webhook de la parte cobrada no se desbloquea"


class TestAdminCredit:
    async def test_admin_adjusts_balance_and_professional_cannot(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        pro_auth: dict[str, str],
        admin_auth: dict[str, str],
    ) -> None:
        profile = await create_profile(api, carpentry_category, pro_auth)
        path = f"/admin/professionals/{profile['id']}/credit-adjustments"
        payload = {"amount_cents": 1800, "note": "Compensacion lead duplicado"}

        forbidden = await api.post(path, json=payload, headers=pro_auth)
        assert forbidden.status_code == 403

        response = await api.post(path, json=payload, headers=admin_auth)
        assert response.status_code == 201, response.text
        assert response.json()["balance"]["amount_cents"] == 1800

        listing = (await api.get("/admin/professionals", headers=admin_auth)).json()
        row = next(item for item in listing["items"] if item["id"] == profile["id"])
        assert row["account"]["is_active"] is True
        assert row["account"]["balance"]["amount_cents"] == 1800

        metrics = (await api.get("/admin/metrics", headers=admin_auth)).json()
        assert metrics["active_accounts"] == 1

    async def test_an_adjustment_settles_the_debt_first_and_reports_what_is_left(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        pro_auth: dict[str, str],
        admin_auth: dict[str, str],
        fake_gateway: FakePaymentGateway,
    ) -> None:
        from app.application.ports import ChargeOwner

        profile = await create_profile(api, carpentry_category, pro_auth, subscribed=False)
        started = await api.post("/me/subscription/checkout", headers=pro_auth)
        customer_id = started.json()["checkout_url"].split("customer=")[1]
        fake_gateway.charge_owners["ch_x"] = ChargeOwner(customer_id=customer_id, purchase_id=None)
        await api.post(
            "/webhooks/stripe",
            content=FakePaymentGateway.dispute_event_payload(
                event_id="evt_dp_admin",
                event_type=PaymentEventType.CHARGE_DISPUTED,
                charge_id="ch_x",
                amount_cents=500,
            ),
            headers={"Stripe-Signature": VALID_SIGNATURE},
        )

        response = await api.post(
            f"/admin/professionals/{profile['id']}/credit-adjustments",
            json={"amount_cents": 300, "note": "Regularizacion parcial"},
            headers=admin_auth,
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["balance"]["amount_cents"] == 0
        assert body["debt"]["amount_cents"] == 200

    async def test_adjustment_for_unknown_professional_is_404(
        self, api: AsyncClient, admin_auth: dict[str, str]
    ) -> None:
        response = await api.post(
            f"/admin/professionals/{uuid4()}/credit-adjustments",
            json={"amount_cents": 100, "note": "Prueba"},
            headers=admin_auth,
        )
        assert response.status_code == 404


class TestAdminSubscriptionPrice:
    async def test_admin_changes_the_price_for_new_subscriptions(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        pro_auth: dict[str, str],
        admin_auth: dict[str, str],
        fake_gateway: FakePaymentGateway,
    ) -> None:
        initial = (await api.get("/admin/subscription-price", headers=admin_auth)).json()
        assert initial["is_default"] is True
        assert initial["amount"]["amount_cents"] == 1800

        forbidden = await api.put(
            "/admin/subscription-price", json={"amount_cents": 2500}, headers=pro_auth
        )
        assert forbidden.status_code == 403

        changed = await api.put(
            "/admin/subscription-price", json={"amount_cents": 2500}, headers=admin_auth
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["amount"]["amount_cents"] == 2500
        assert changed.json()["is_default"] is False

        await create_profile(api, carpentry_category, pro_auth, subscribed=False)
        me = (await api.get("/me", headers=pro_auth)).json()
        assert me["account"]["topup_amount"]["amount_cents"] == 2500
        await api.post("/me/subscription/checkout", headers=pro_auth)
        new_price_id = next(iter(fake_gateway.created_prices))
        assert fake_gateway.subscription_checkouts[-1].price_id == new_price_id

    async def test_absurd_price_is_rejected(
        self, api: AsyncClient, admin_auth: dict[str, str]
    ) -> None:
        response = await api.put(
            "/admin/subscription-price", json={"amount_cents": 10}, headers=admin_auth
        )
        assert response.status_code == 422


class TestReturnedTopUp:
    async def test_a_spent_top_up_returned_by_the_bank_is_owed_and_blocks_buying(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        pro_auth: dict[str, str],
        fake_gateway: FakePaymentGateway,
    ) -> None:
        from app.application.ports import ChargeOwner

        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth, subscribed=False)
        started = await api.post("/me/subscription/checkout", headers=pro_auth)
        customer_id = started.json()["checkout_url"].split("customer=")[1]
        await api.post(
            "/webhooks/stripe",
            content=FakePaymentGateway.subscription_event_payload(
                event_id="evt_inv_sepa",
                event_type=PaymentEventType.INVOICE_PAID,
                customer_id=customer_id,
                invoice_id="in_sepa",
                amount_cents=1800,
            ),
            headers={"Stripe-Signature": VALID_SIGNATURE},
        )
        fake_gateway.charge_owners["ch_sepa"] = ChargeOwner(
            customer_id=customer_id, purchase_id=None
        )

        response = await api.post(
            "/webhooks/stripe",
            content=FakePaymentGateway.dispute_event_payload(
                event_id="evt_dp_sepa",
                event_type=PaymentEventType.CHARGE_DISPUTED,
                charge_id="ch_sepa",
                amount_cents=1800,
            ),
            headers={"Stripe-Signature": VALID_SIGNATURE},
        )
        assert response.status_code == 200, response.text

        # Sin gastar nada: el saldo vuelve a 0 y no hay deuda, pero se ve el movimiento.
        state = await account(api, pro_auth)
        assert state["balance"]["amount_cents"] == 0
        assert state["debt"] is None
        assert sorted(entry["kind"] for entry in state["entries"]) == ["chargeback", "topup"]

        # Una segunda devolucion (otra disputa) ya no tiene saldo: queda como deuda.
        await api.post(
            "/webhooks/stripe",
            content=FakePaymentGateway.dispute_event_payload(
                event_id="evt_dp_sepa_2",
                event_type=PaymentEventType.CHARGE_DISPUTED,
                dispute_id="dp_2",
                charge_id="ch_sepa",
                amount_cents=500,
            ),
            headers={"Stripe-Signature": VALID_SIGNATURE},
        )
        state = await account(api, pro_auth)
        assert state["debt"]["amount_cents"] == 500
        assert state["is_active"] is True

        purchase = await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)
        assert purchase.status_code == 402, purchase.text
        assert purchase.json()["code"] == "CREDIT_DEBT_OUTSTANDING"
