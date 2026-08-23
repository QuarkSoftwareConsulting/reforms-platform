"""Test HTTP del ciclo completo: publicar, explorar, comprar y desbloquear.

El invariante que mas se vigila aqui: ningun endpoint puede devolver los datos de
contacto del cliente sin una compra pagada.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.application.ports import AuthenticatedIdentity, PaymentEventType
from app.domain.models import Category
from tests.api.conftest import PRO_TOKEN
from tests.fakes import FakeTokenVerifier
from tests.fakes.payments import VALID_SIGNATURE, FakePaymentGateway

pytestmark = pytest.mark.integration

CLIENT_NAME = "Ana Lopez"
CLIENT_PHONE = "+34611223344"
CLIENT_EMAIL = "ana.lopez@example.com"

LEAD_PAYLOAD = {
    "title": "Reparar armario de cocina",
    "description": (
        "Se ha descolgado la puerta del armario alto de la cocina y necesito "
        "que la vuelvan a montar y ajusten las bisagras."
    ),
    "postal_code": "28001",
    "client_name": CLIENT_NAME,
    "client_phone": CLIENT_PHONE,
    "client_email": CLIENT_EMAIL,
    "photo_keys": [],
    "consent": {"accepted": True},
}

PROFILE_PAYLOAD = {
    "business_name": "Carpinteria Lopez",
    "phone": "+34600111222",
    "postal_code": "28001",
    "service_radius_km": 25,
}


async def publish_lead(api: AsyncClient, category: Category, **overrides: object) -> dict:
    payload = {**LEAD_PAYLOAD, "category_id": str(category.id), **overrides}
    response = await api.post("/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def create_profile(
    api: AsyncClient, category: Category, headers: dict[str, str], **overrides: object
) -> dict:
    payload = {**PROFILE_PAYLOAD, "category_ids": [str(category.id)], **overrides}
    response = await api.put("/me/professional", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def pay(api: AsyncClient, purchase_id: str, event_id: str = "evt_1") -> None:
    """Simula la confirmacion de Stripe llamando al webhook real."""
    response = await api.post(
        "/webhooks/stripe",
        content=FakePaymentGateway.event_payload(
            event_id=event_id,
            event_type=PaymentEventType.CHECKOUT_COMPLETED,
            purchase_id=UUID(purchase_id),
        ),
        headers={"Stripe-Signature": VALID_SIGNATURE},
    )
    assert response.status_code == 200, response.text
    assert response.json()["handled"] is True


class TestPublicPublication:
    async def test_client_publishes_without_an_account(
        self, api: AsyncClient, carpentry_category: Category
    ) -> None:
        created = await publish_lead(api, carpentry_category)

        assert created["status"] == "published"
        assert created["city"] == "Madrid"
        assert created["province"] == "Madrid"

    async def test_publication_without_consent_is_rejected(
        self, api: AsyncClient, carpentry_category: Category
    ) -> None:
        response = await api.post(
            "/leads",
            json={
                **LEAD_PAYLOAD,
                "category_id": str(carpentry_category.id),
                "consent": {"accepted": False},
            },
        )
        assert response.status_code == 422
        assert response.json()["code"] == "CONSENT_REQUIRED"

    async def test_unknown_postal_code_is_rejected(
        self, api: AsyncClient, carpentry_category: Category
    ) -> None:
        response = await api.post(
            "/leads",
            json={
                **LEAD_PAYLOAD,
                "category_id": str(carpentry_category.id),
                "postal_code": "99999",
            },
        )
        assert response.status_code == 422
        assert response.json()["code"] == "UNKNOWN_POSTAL_CODE"

    async def test_photo_key_outside_the_leads_prefix_is_rejected(
        self, api: AsyncClient, carpentry_category: Category
    ) -> None:
        response = await api.post(
            "/leads",
            json={
                **LEAD_PAYLOAD,
                "category_id": str(carpentry_category.id),
                "photo_keys": ["../../etc/passwd"],
            },
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"

    async def test_short_description_is_rejected(
        self, api: AsyncClient, carpentry_category: Category
    ) -> None:
        response = await api.post(
            "/leads",
            json={
                **LEAD_PAYLOAD,
                "category_id": str(carpentry_category.id),
                "description": "corto",
            },
        )
        assert response.status_code == 422


class TestAuthorization:
    async def test_explorer_requires_authentication(self, api: AsyncClient) -> None:
        response = await api.get("/leads")
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHENTICATED"

    async def test_invalid_token_is_rejected(self, api: AsyncClient) -> None:
        response = await api.get("/leads", headers={"Authorization": "Bearer basura"})
        assert response.status_code == 401

    async def test_malformed_authorization_header_is_rejected(self, api: AsyncClient) -> None:
        response = await api.get("/leads", headers={"Authorization": PRO_TOKEN})
        assert response.status_code == 401

    async def test_professional_without_profile_is_told_to_complete_it(
        self, api: AsyncClient, pro_auth: dict[str, str]
    ) -> None:
        response = await api.get("/leads", headers=pro_auth)
        assert response.status_code == 404
        assert response.json()["code"] == "PROFESSIONAL_NOT_FOUND"

    async def test_me_endpoint_reports_missing_profile(
        self, api: AsyncClient, pro_auth: dict[str, str]
    ) -> None:
        response = await api.get("/me", headers=pro_auth)
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "pro@example.com"
        assert body["role"] == "professional"
        assert body["professional"] is None

    async def test_admin_claim_is_mirrored_as_admin_role(
        self, api: AsyncClient, admin_auth: dict[str, str]
    ) -> None:
        response = await api.get("/me", headers=admin_auth)
        assert response.status_code == 200
        assert response.json()["role"] == "admin"


class TestExplorerHidesPii:
    async def test_listing_never_exposes_client_contact(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)

        response = await api.get("/leads", headers=pro_auth)
        assert response.status_code == 200
        body = response.text

        assert CLIENT_NAME not in body
        assert CLIENT_PHONE not in body
        assert CLIENT_EMAIL not in body
        assert response.json()["total"] == 1

    async def test_listing_shows_distance_price_and_masked_hints(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)

        item = (await api.get("/leads", headers=pro_auth)).json()["items"][0]

        assert item["city"] == "Madrid"
        assert item["postal_code_prefix"] == "28"
        assert item["distance_km"] == pytest.approx(0, abs=1)
        assert item["price"]["amount_cents"] == 500
        assert item["remaining_slots"] == 3
        assert item["masked_phone"].endswith("44")
        assert item["already_purchased"] is False

    async def test_detail_hides_contact_before_paying(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)

        response = await api.get(f"/leads/{created['id']}", headers=pro_auth)
        assert response.status_code == 200
        body = response.json()

        assert body["is_unlocked"] is False
        assert body["contact"] is None
        assert CLIENT_PHONE not in response.text

    async def test_leads_outside_the_radius_are_not_listed(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        await publish_lead(api, carpentry_category, postal_code="08001")
        await create_profile(api, carpentry_category, pro_auth)

        assert (await api.get("/leads", headers=pro_auth)).json()["total"] == 0

    async def test_widening_the_radius_reveals_farther_leads(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        await publish_lead(api, carpentry_category, postal_code="28801")
        await create_profile(api, carpentry_category, pro_auth, service_radius_km=10)

        narrow = await api.get("/leads", headers=pro_auth)
        wide = await api.get("/leads?radius_km=50", headers=pro_auth)

        assert narrow.json()["total"] == 0
        assert wide.json()["total"] == 1


class TestPurchaseFlow:
    async def test_purchase_reserves_and_returns_a_checkout_url(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        pro_auth: dict[str, str],
        fake_gateway: FakePaymentGateway,
    ) -> None:
        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)

        response = await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)
        assert response.status_code == 201, response.text
        body = response.json()

        assert body["checkout_url"].startswith("https://checkout.test/")
        assert body["amount"]["amount_cents"] == 500
        assert body["expires_at"] is not None
        assert len(fake_gateway.requests) == 1

    async def test_contact_stays_locked_until_the_webhook_confirms(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        """Volver de la pasarela no basta: la confirmacion la da Stripe firmada."""
        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)
        await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)

        detail = await api.get(f"/leads/{created['id']}", headers=pro_auth)
        assert detail.json()["is_unlocked"] is False
        assert detail.json()["purchase"]["status"] == "reserved"

    async def test_paid_purchase_unlocks_the_contact(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)
        purchase = (await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)).json()

        await pay(api, purchase["purchase_id"])

        detail = (await api.get(f"/leads/{created['id']}", headers=pro_auth)).json()
        assert detail["is_unlocked"] is True
        assert detail["contact"]["name"] == CLIENT_NAME
        assert detail["contact"]["phone"] == CLIENT_PHONE
        assert detail["contact"]["email"] == CLIENT_EMAIL

    async def test_history_lists_the_unlocked_contact(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)
        purchase = (await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)).json()
        await pay(api, purchase["purchase_id"])

        history = (await api.get("/me/purchases", headers=pro_auth)).json()

        assert len(history) == 1
        assert history[0]["is_unlocked"] is True
        assert history[0]["contact"]["phone"] == CLIENT_PHONE
        assert history[0]["purchase"]["status"] == "paid"

    async def test_buying_the_same_lead_twice_is_rejected(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)
        await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)

        response = await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)
        assert response.status_code == 409
        assert response.json()["code"] == "LEAD_ALREADY_PURCHASED"

    async def test_lead_of_another_trade_cannot_be_purchased(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str], api_engine
    ) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from app.infrastructure.adapters.db.models import CategoryRow

        factory = async_sessionmaker(api_engine, expire_on_commit=False)
        plumbing = CategoryRow(
            id=uuid4(),
            slug="fontaneria",
            name_es="Fontaneria",
            name_en="Plumbing",
            lead_price_cents=700,
            currency="EUR",
            active=True,
        )
        async with factory() as session:
            session.add(plumbing)
            await session.commit()

        response = await api.post("/leads", json={**LEAD_PAYLOAD, "category_id": str(plumbing.id)})
        plumbing_lead = response.json()
        await create_profile(api, carpentry_category, pro_auth)

        purchase = await api.post(f"/leads/{plumbing_lead['id']}/purchase", headers=pro_auth)
        assert purchase.status_code == 409
        assert purchase.json()["code"] == "CATEGORY_MISMATCH"


class TestWebhookSecurity:
    async def test_unsigned_webhook_is_rejected(self, api: AsyncClient) -> None:
        response = await api.post(
            "/webhooks/stripe",
            content=FakePaymentGateway.event_payload(
                event_id="evt_forged", event_type=PaymentEventType.CHECKOUT_COMPLETED
            ),
            headers={"Stripe-Signature": "firma-falsa"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHENTICATED"

    async def test_replayed_webhook_is_reported_as_duplicate(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)
        purchase = (await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)).json()

        payload = FakePaymentGateway.event_payload(
            event_id="evt_replay",
            event_type=PaymentEventType.CHECKOUT_COMPLETED,
            purchase_id=UUID(purchase["purchase_id"]),
        )
        headers = {"Stripe-Signature": VALID_SIGNATURE}

        first = await api.post("/webhooks/stripe", content=payload, headers=headers)
        second = await api.post("/webhooks/stripe", content=payload, headers=headers)

        assert first.json()["handled"] is True
        assert second.json()["duplicate"] is True

        detail = (await api.get(f"/leads/{created['id']}", headers=pro_auth)).json()
        assert detail["lead"]["remaining_slots"] == 2, "solo se debe contar una venta"

    async def test_irrelevant_event_is_acknowledged_but_not_handled(self, api: AsyncClient) -> None:
        response = await api.post(
            "/webhooks/stripe",
            content=FakePaymentGateway.event_payload(
                event_id="evt_noise",
                event_type=PaymentEventType.IGNORED,
                raw_type="customer.updated",
            ),
            headers={"Stripe-Signature": VALID_SIGNATURE},
        )
        assert response.status_code == 200
        assert response.json() == {"received": True, "handled": False, "duplicate": False}


class TestCatalogAndProfile:
    async def test_categories_are_public(
        self, api: AsyncClient, carpentry_category: Category
    ) -> None:
        response = await api.get("/categories")
        assert response.status_code == 200
        assert [c["slug"] for c in response.json()] == ["carpinteria"]

    async def test_category_names_follow_accept_language(
        self, api: AsyncClient, carpentry_category: Category
    ) -> None:
        spanish = await api.get("/categories")
        english = await api.get("/categories", headers={"Accept-Language": "en-US,en;q=0.9"})

        assert spanish.json()[0]["name"] == "Carpinteria"
        assert english.json()[0]["name"] == "Carpentry"

    async def test_profile_can_be_updated_without_duplicating(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        first = await create_profile(api, carpentry_category, pro_auth)
        second = await create_profile(
            api, carpentry_category, pro_auth, service_radius_km=60, postal_code="08001"
        )

        assert first["id"] == second["id"]
        assert second["service_radius_km"] == 60
        assert second["city"] == "Barcelona"

    async def test_invalid_radius_is_rejected_by_the_schema(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        response = await api.put(
            "/me/professional",
            json={
                **PROFILE_PAYLOAD,
                "category_ids": [str(carpentry_category.id)],
                "service_radius_km": 5000,
            },
            headers=pro_auth,
        )
        assert response.status_code == 422

    async def test_profile_requires_at_least_one_trade(
        self, api: AsyncClient, pro_auth: dict[str, str]
    ) -> None:
        response = await api.put(
            "/me/professional",
            json={**PROFILE_PAYLOAD, "category_ids": []},
            headers=pro_auth,
        )
        assert response.status_code == 422

    async def test_postal_code_lookup_is_public(self, api: AsyncClient) -> None:
        response = await api.get("/postal-codes/28001")
        assert response.status_code == 200
        assert response.json()["city"] == "Madrid"

    async def test_presign_returns_upload_target(self, api: AsyncClient) -> None:
        response = await api.post(
            "/leads/photos/presign",
            json={"filename": "cocina.jpg", "content_type": "image/jpeg"},
        )
        assert response.status_code == 200
        assert response.json()["storage_key"].startswith("leads/")


class TestLeadCapOverHttp:
    async def test_fourth_professional_gets_cap_reached(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        fake_tokens: FakeTokenVerifier,
    ) -> None:
        """Tres compras agotan el lead; la cuarta recibe 409 LEAD_CAP_REACHED."""
        created = await publish_lead(api, carpentry_category)

        for index in range(4):
            token = f"token-pro-{index}"
            fake_tokens.register(
                token,
                AuthenticatedIdentity(
                    provider_uid=f"fb-pro-{index}", email=f"pro{index}@example.com"
                ),
            )
            headers = {"Authorization": f"Bearer {token}"}
            await create_profile(api, carpentry_category, headers)

            response = await api.post(f"/leads/{created['id']}/purchase", headers=headers)
            if index < 3:
                assert response.status_code == 201, response.text
                await pay(api, response.json()["purchase_id"], event_id=f"evt_{index}")
            else:
                assert response.status_code == 409
                assert response.json()["code"] == "LEAD_CAP_REACHED"
