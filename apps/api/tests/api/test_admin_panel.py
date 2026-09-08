"""Tests HTTP del panel administrativo y sus limites de privacidad."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.domain.models import Category
from tests.api.test_lead_lifecycle import (
    CLIENT_EMAIL,
    CLIENT_NAME,
    CLIENT_PHONE,
    create_profile,
    pay,
    publish_lead,
)

pytestmark = pytest.mark.integration


def admin_payload(category: Category) -> dict[str, object]:
    return {
        "category_id": str(category.id),
        "title": "Cambiar persiana del salon",
        "description": "La persiana del salon esta atascada y necesito repararla esta semana.",
        "postal_code": "28001",
        "client_name": CLIENT_NAME,
        "client_phone": CLIENT_PHONE,
        "client_email": CLIENT_EMAIL,
        "photo_keys": [],
        "consent": {
            "policy_version": "2026-01-v1",
            "accepted_at": (datetime(2026, 3, 1, tzinfo=UTC) - timedelta(days=1)).isoformat(),
            "channel": "Meta Lead Ads",
            "campaign_reference": "madrid-marzo",
        },
    }


class TestAdminPanelApi:
    async def test_admin_ingests_and_lists_lead_without_client_pii(
        self, api: AsyncClient, carpentry_category: Category, admin_auth: dict[str, str]
    ) -> None:
        created = await api.post(
            "/admin/leads", json=admin_payload(carpentry_category), headers=admin_auth
        )
        assert created.status_code == 201, created.text

        listing = await api.get("/admin/leads?source=admin", headers=admin_auth)
        assert listing.status_code == 200
        assert listing.json()["total"] == 1
        assert CLIENT_NAME not in listing.text
        assert CLIENT_PHONE not in listing.text
        assert CLIENT_EMAIL not in listing.text

    async def test_admin_endpoints_require_admin(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        response = await api.post(
            "/admin/leads", json=admin_payload(carpentry_category), headers=pro_auth
        )
        assert response.status_code == 403
        assert response.json()["code"] == "PERMISSION_DENIED"

    async def test_admin_can_moderate_and_review_purchase(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        admin_auth: dict[str, str],
        pro_auth: dict[str, str],
    ) -> None:
        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)
        started = await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)
        assert started.status_code == 201
        await pay(api, started.json()["purchase_id"])

        disabled = await api.post(f"/admin/leads/{created['id']}/disable", headers=admin_auth)
        assert disabled.json()["status"] == "disabled"

        purchases = await api.get(f"/admin/leads/{created['id']}/purchases", headers=admin_auth)
        assert purchases.status_code == 200
        assert CLIENT_NAME not in purchases.text
        purchase_id = purchases.json()[0]["purchase"]["id"]

        review = await api.post(
            f"/admin/purchases/{purchase_id}/reviews",
            json={"note": "Comprobar posible duplicado"},
            headers=admin_auth,
        )
        assert review.status_code == 201

        metrics = await api.get("/admin/metrics", headers=admin_auth)
        assert metrics.status_code == 200
        assert metrics.json()["paid_purchases"] == 1
        assert metrics.json()["revenue_by_currency"]["EUR"]["amount_cents"] == 500
