"""Tests HTTP del catalogo gestionado desde el panel de admin."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.domain.models import Category
from tests.api.test_lead_lifecycle import create_profile

pytestmark = pytest.mark.integration

NEW_CATEGORY = {"name_es": "Jardinería", "name_en": "Gardening", "suggested_price_cents": 700}


async def create(api: AsyncClient, headers: dict[str, str], **overrides: object) -> dict:
    payload = {**NEW_CATEGORY, **overrides}
    response = await api.post("/admin/categories", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def public_slugs(response_json: list[dict]) -> list[str]:
    return [category["slug"] for category in response_json]


class TestCatalogApi:
    async def test_only_admins_manage_the_catalog(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        category_id = carpentry_category.id
        for method, url in (
            ("GET", "/admin/catalog"),
            ("POST", "/admin/categories"),
            ("PUT", f"/admin/categories/{category_id}"),
            ("DELETE", f"/admin/categories/{category_id}"),
            ("POST", f"/admin/categories/{category_id}/services"),
        ):
            response = await api.request(method, url, json=NEW_CATEGORY, headers=pro_auth)
            assert response.status_code == 403, (method, url, response.text)

    async def test_a_new_category_and_service_reach_the_public_catalog(
        self, api: AsyncClient, admin_auth: dict[str, str]
    ) -> None:
        created = await create(api, admin_auth)
        assert created["slug"] == "jardineria"
        assert created["suggested_lead_price"]["amount_cents"] == 700

        with_service = await api.post(
            f"/admin/categories/{created['id']}/services",
            json={"name_es": "Poda de árboles", "name_en": "Tree pruning"},
            headers=admin_auth,
        )
        assert with_service.status_code == 201, with_service.text
        assert [s["slug"] for s in with_service.json()["services"]] == ["poda-de-arboles"]

        public = (await api.get("/categories", headers={"Accept-Language": "en"})).json()
        gardening = next(c for c in public if c["slug"] == "jardineria")
        assert gardening["name"] == "Gardening"
        assert [s["name"] for s in gardening["services"]] == ["Tree pruning"]

    async def test_deactivating_hides_it_from_the_public_but_not_from_the_admin(
        self, api: AsyncClient, admin_auth: dict[str, str]
    ) -> None:
        created = await create(api, admin_auth)

        response = await api.put(
            f"/admin/categories/{created['id']}",
            json={
                "name_es": "Jardinería y paisajismo",
                "name_en": "Gardening",
                "suggested_price_cents": 900,
                "sort_order": 3,
                "active": False,
            },
            headers=admin_auth,
        )
        assert response.status_code == 200, response.text
        assert response.json()["slug"] == "jardineria", "renombrar no cambia la URL"

        assert "jardineria" not in public_slugs((await api.get("/categories")).json())
        catalog = (await api.get("/admin/catalog", headers=admin_auth)).json()
        stored = next(c for c in catalog if c["id"] == created["id"])
        assert stored["active"] is False
        assert stored["name_es"] == "Jardinería y paisajismo"
        assert stored["suggested_lead_price"]["amount_cents"] == 900

    async def test_duplicate_and_invalid_names_have_their_own_codes(
        self, api: AsyncClient, admin_auth: dict[str, str]
    ) -> None:
        await create(api, admin_auth)

        duplicate = await api.post("/admin/categories", json=NEW_CATEGORY, headers=admin_auth)
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "CATALOG_SLUG_TAKEN"

        invalid = await api.post(
            "/admin/categories", json={**NEW_CATEGORY, "name_es": "   "}, headers=admin_auth
        )
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "CATALOG_NAME_INVALID"
        assert invalid.json()["details"] == {"min": 1, "max": 120}

    async def test_unused_is_deleted_used_is_refused(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        admin_auth: dict[str, str],
        pro_auth: dict[str, str],
    ) -> None:
        created = await create(api, admin_auth)
        deleted = await api.delete(f"/admin/categories/{created['id']}", headers=admin_auth)
        assert deleted.status_code == 204
        catalog = (await api.get("/admin/catalog", headers=admin_auth)).json()
        assert created["id"] not in [c["id"] for c in catalog]

        # Un profesional la tiene en su perfil: borrarla dejaria su perfil sin oficio.
        await create_profile(api, carpentry_category, pro_auth)
        refused = await api.delete(f"/admin/categories/{carpentry_category.id}", headers=admin_auth)
        assert refused.status_code == 409
        assert refused.json()["code"] == "CATALOG_ITEM_IN_USE"

    async def test_service_lifecycle(
        self, api: AsyncClient, carpentry_category: Category, admin_auth: dict[str, str]
    ) -> None:
        service = carpentry_category.services[0]
        url = f"/admin/categories/{carpentry_category.id}/services/{service.id}"

        edited = await api.put(
            url,
            json={
                "name_es": "Puertas a medida",
                "name_en": "Doors",
                "sort_order": 9,
                "active": False,
            },
            headers=admin_auth,
        )
        assert edited.status_code == 200, edited.text
        public = (await api.get("/categories")).json()
        carpentry = next(c for c in public if c["id"] == str(carpentry_category.id))
        assert service.slug not in [s["slug"] for s in carpentry["services"]]

        assert (await api.delete(url, headers=admin_auth)).status_code == 204
        gone = await api.delete(url, headers=admin_auth)
        assert gone.status_code == 404
        assert gone.json()["code"] == "SERVICE_NOT_FOUND"

    async def test_featured_service_reaches_the_landing_with_a_stable_image_url(
        self, api: AsyncClient, carpentry_category: Category, admin_auth: dict[str, str]
    ) -> None:
        service = carpentry_category.services[0]
        base = f"/admin/categories/{carpentry_category.id}/services/{service.id}"

        upload = await api.post(
            f"{base}/image-upload",
            json={"filename": "puertas.webp", "content_type": "image/webp", "size_bytes": 1000},
            headers=admin_auth,
        )
        assert upload.status_code == 200, upload.text
        key = upload.json()["storage_key"]
        assert key.startswith(f"catalog/services/{service.id}/")

        body = {"name_es": "Puertas", "name_en": "Doors", "sort_order": 1, "active": True}
        no_photo = await api.put(base, json={**body, "featured": True}, headers=admin_auth)
        assert no_photo.status_code == 422
        assert no_photo.json()["code"] == "FEATURED_SERVICE_NEEDS_IMAGE"

        featured = await api.put(
            base,
            json={
                **body,
                "featured": True,
                "image_key": key,
                "landing_name_es": "Puertas a medida",
                "landing_name_en": "Custom doors",
            },
            headers=admin_auth,
        )
        assert featured.status_code == 200, featured.text
        stored = next(s for s in featured.json()["services"] if s["id"] == str(service.id))
        assert stored["featured"] is True
        assert stored["image_url"].endswith(key)

        public = (await api.get("/categories", headers={"Accept-Language": "en"})).json()
        carpentry = next(c for c in public if c["id"] == str(carpentry_category.id))
        card = next(s for s in carpentry["services"] if s["id"] == str(service.id))
        assert card["featured"] is True
        assert card["landing_name"] == "Custom doors"

        image = await api.get(f"/catalog/services/{service.id}/image", follow_redirects=False)
        assert image.status_code == 302
        assert image.headers["location"].endswith(key)
        assert image.headers["cache-control"] == "public, max-age=300"

        other = carpentry_category.services[1]
        missing = await api.get(f"/catalog/services/{other.id}/image", follow_redirects=False)
        assert missing.status_code == 404
