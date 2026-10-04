"""Tests HTTP de roles, directorio de usuarios, compras globales y serie diaria."""

from __future__ import annotations

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


async def user_id(api: AsyncClient, auth: dict[str, str]) -> str:
    response = await api.get("/me", headers=auth)
    assert response.status_code == 200
    return str(response.json()["user_id"])


class TestRolesApi:
    async def test_promotion_takes_effect_on_the_next_request(
        self, api: AsyncClient, admin_auth: dict[str, str], pro_auth: dict[str, str]
    ) -> None:
        pro_id = await user_id(api, pro_auth)
        await user_id(api, admin_auth)
        assert (await api.get("/admin/metrics", headers=pro_auth)).status_code == 403

        promoted = await api.put(
            f"/admin/users/{pro_id}/role",
            json={"role": "admin", "note": "soporte"},
            headers=admin_auth,
        )
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["role"] == "admin"

        # Mismo token, sin claim de admin: el rol se lee de la BD.
        assert (await api.get("/admin/metrics", headers=pro_auth)).status_code == 200
        assert (await api.get("/me", headers=pro_auth)).json()["role"] == "admin"

        demoted = await api.put(
            f"/admin/users/{pro_id}/role", json={"role": "professional"}, headers=admin_auth
        )
        assert demoted.status_code == 200
        assert (await api.get("/admin/metrics", headers=pro_auth)).status_code == 403

        events = await api.get(f"/admin/users/{pro_id}/role-events", headers=admin_auth)
        assert events.status_code == 200
        # El reloj de los tests esta congelado: los dos eventos empatan en `created_at`.
        notes = {(e["from_role"], e["to_role"]): e["note"] for e in events.json()}
        assert notes == {("professional", "admin"): "soporte", ("admin", "professional"): None}

    async def test_admin_cannot_demote_themselves(
        self, api: AsyncClient, admin_auth: dict[str, str]
    ) -> None:
        admin_id = await user_id(api, admin_auth)

        response = await api.put(
            f"/admin/users/{admin_id}/role", json={"role": "professional"}, headers=admin_auth
        )

        assert response.status_code == 409
        assert response.json()["code"] == "CANNOT_CHANGE_OWN_ROLE"

    async def test_unknown_user(self, api: AsyncClient, admin_auth: dict[str, str]) -> None:
        response = await api.put(
            "/admin/users/00000000-0000-0000-0000-000000000000/role",
            json={"role": "admin"},
            headers=admin_auth,
        )
        assert response.status_code == 404
        assert response.json()["code"] == "USER_NOT_FOUND"

    async def test_role_endpoints_require_admin(
        self, api: AsyncClient, pro_auth: dict[str, str]
    ) -> None:
        pro_id = await user_id(api, pro_auth)
        for response in (
            await api.get("/admin/users", headers=pro_auth),
            await api.put(f"/admin/users/{pro_id}/role", json={"role": "admin"}, headers=pro_auth),
            await api.get(f"/admin/users/{pro_id}/role-events", headers=pro_auth),
            await api.get("/admin/purchases", headers=pro_auth),
            await api.get("/admin/metrics/timeseries", headers=pro_auth),
        ):
            assert response.status_code == 403
            assert response.json()["code"] == "PERMISSION_DENIED"


class TestUserDirectoryApi:
    async def test_lists_users_with_professional_summary_and_filters(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        admin_auth: dict[str, str],
        pro_auth: dict[str, str],
    ) -> None:
        await create_profile(api, carpentry_category, pro_auth)
        await user_id(api, admin_auth)

        everyone = await api.get("/admin/users", headers=admin_auth)
        assert everyone.status_code == 200, everyone.text
        assert everyone.json()["total"] == 2
        by_email = {item["email"]: item for item in everyone.json()["items"]}
        assert by_email["admin@example.com"]["role"] == "admin"
        assert by_email["admin@example.com"]["professional"] is None
        assert by_email["pro@example.com"]["professional"]["business_name"]

        admins = await api.get("/admin/users?role=admin", headers=admin_auth)
        assert [item["email"] for item in admins.json()["items"]] == ["admin@example.com"]

        searched = await api.get("/admin/users?query=PRO@example", headers=admin_auth)
        assert [item["email"] for item in searched.json()["items"]] == ["pro@example.com"]


class TestPurchasesAndTimeseriesApi:
    async def test_global_purchases_and_daily_series_without_client_pii(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        admin_auth: dict[str, str],
        pro_auth: dict[str, str],
    ) -> None:
        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)
        started = await api.post(f"/leads/{created['id']}/purchase", headers=pro_auth)
        assert started.status_code == 201, started.text
        await pay(api, started.json()["purchase_id"])

        purchases = await api.get("/admin/purchases?status=paid", headers=admin_auth)
        assert purchases.status_code == 200, purchases.text
        body = purchases.json()
        assert body["total"] == 1
        [item] = body["items"]
        assert item["lead"]["id"] == created["id"]
        assert item["lead"]["category"]["slug"] == carpentry_category.slug
        assert item["professional"]["business_name"]
        for pii in (CLIENT_NAME, CLIENT_PHONE, CLIENT_EMAIL):
            assert pii not in purchases.text

        none_reserved = await api.get("/admin/purchases?status=reserved", headers=admin_auth)
        assert none_reserved.json()["total"] == 0

        # Dias en hora de Madrid, ambos incluidos (el reloj de los tests: 1-mar 12:00 UTC).
        that_day = await api.get(
            "/admin/purchases?from=2026-03-01&to=2026-03-01", headers=admin_auth
        )
        assert that_day.json()["total"] == 1
        day_before = await api.get("/admin/purchases?to=2026-02-28", headers=admin_auth)
        assert day_before.json()["total"] == 0
        inverted = await api.get(
            "/admin/purchases?from=2026-03-02&to=2026-03-01", headers=admin_auth
        )
        assert inverted.status_code == 422
        assert inverted.json()["code"] == "VALIDATION_ERROR"

        series = await api.get(
            "/admin/metrics/timeseries?from=2026-02-28&to=2026-03-01", headers=admin_auth
        )
        assert series.status_code == 200, series.text
        points = series.json()["points"]
        assert [point["day"] for point in points] == ["2026-02-28", "2026-03-01"]
        assert points[1]["leads_created"] == 1
        assert points[1]["paid_purchases"] == 1
        assert points[1]["revenue_by_currency"]["EUR"]["amount_cents"] > 0

    async def test_timeseries_rejects_inverted_range(
        self, api: AsyncClient, admin_auth: dict[str, str]
    ) -> None:
        response = await api.get(
            "/admin/metrics/timeseries?from=2026-03-02&to=2026-03-01", headers=admin_auth
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"
