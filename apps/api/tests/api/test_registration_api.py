"""Alta y validacion del profesional por HTTP (F02), con Firebase y Stripe falsos."""

from __future__ import annotations

from httpx import AsyncClient

from app.domain.models import Category
from tests.api.test_lead_lifecycle import (
    ADMIN_HEADERS,
    PROFILE_PAYLOAD,
    activate_subscription,
    create_profile,
    publish_lead,
)
from tests.fakes import FakePaymentGateway, FakeStorage


async def register(api: AsyncClient, category: Category, headers: dict[str, str]) -> dict:
    return await create_profile(api, category, headers, approved=False, subscribed=False)


async def attach_document(api: AsyncClient, headers: dict[str, str]) -> dict:
    upload = await api.post(
        "/me/professional/uploads",
        json={"purpose": "document", "filename": "036.pdf", "content_type": "application/pdf"},
        headers=headers,
    )
    response = await api.post(
        "/me/professional/documents",
        json={
            "kind": "tax_registration",
            "storage_key": upload.json()["storage_key"],
            "filename": "036.pdf",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestRegistrationOverHttp:
    async def test_a_new_profile_starts_incomplete_and_lists_what_is_missing(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        profile = await register(api, carpentry_category, pro_auth)
        assert profile["verification"]["status"] == "incomplete"
        assert profile["verification"]["missing"] == ["document_tax_registration"]

        response = await api.post("/me/professional/submit", headers=pro_auth)
        assert response.status_code == 409
        assert response.json()["code"] == "PROFILE_INCOMPLETE"
        assert response.json()["details"] == {"missing": ["document_tax_registration"]}

    async def test_documents_go_to_the_private_bucket_and_are_not_linked_to_the_owner(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        pro_auth: dict[str, str],
        private_storage: FakeStorage,
    ) -> None:
        await register(api, carpentry_category, pro_auth)
        upload = await api.post(
            "/me/professional/uploads",
            json={"purpose": "document", "filename": "dni.pdf", "content_type": "application/pdf"},
            headers=pro_auth,
        )
        assert upload.json()["upload_url"].startswith(private_storage.base_url)

        await attach_document(api, pro_auth)
        profile = (await api.get("/me/professional", headers=pro_auth)).text
        # El profesional ve sus documentos, pero ninguna URL al bucket privado.
        assert "036.pdf" in profile
        assert private_storage.base_url not in profile

    async def test_the_base_outside_madrid_is_rejected(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        response = await api.put(
            "/me/professional",
            json={
                **PROFILE_PAYLOAD,
                "category_ids": [str(carpentry_category.id)],
                "postal_code": "08001",
            },
            headers=pro_auth,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "POSTAL_CODE_NOT_COVERED"

    async def test_a_wrong_tax_id_is_rejected(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        response = await api.put(
            "/me/professional",
            json={
                **PROFILE_PAYLOAD,
                "category_ids": [str(carpentry_category.id)],
                "tax_id": "12345678A",
            },
            headers=pro_auth,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_TAX_ID"


class TestReviewOverHttp:
    async def test_pending_sees_leads_but_cannot_buy(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        lead = await publish_lead(api, carpentry_category)
        await register(api, carpentry_category, pro_auth)
        await activate_subscription(api, pro_auth)
        await attach_document(api, pro_auth)
        submitted = await api.post("/me/professional/submit", headers=pro_auth)
        assert submitted.json()["verification"]["status"] == "pending"

        assert (await api.get("/leads", headers=pro_auth)).json()["total"] == 1
        response = await api.post(f"/leads/{lead['id']}/purchase", headers=pro_auth)
        assert response.status_code == 403
        assert response.json()["code"] == "PROFESSIONAL_NOT_APPROVED"

    async def test_admin_endpoints_are_admin_only(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        profile = await register(api, carpentry_category, pro_auth)
        for path in ("approve", "verification"):
            method = api.get if path == "verification" else api.post
            response = await method(
                f"/admin/professionals/{profile['id']}/{path}", headers=pro_auth
            )
            assert response.status_code == 403, path

    async def test_the_queue_and_the_dossier(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        pro_auth: dict[str, str],
        private_storage: FakeStorage,
    ) -> None:
        profile = await register(api, carpentry_category, pro_auth)
        await attach_document(api, pro_auth)
        await api.post("/me/professional/submit", headers=pro_auth)

        queue = await api.get(
            "/admin/professionals?verification_status=pending", headers=ADMIN_HEADERS
        )
        assert [p["id"] for p in queue.json()["items"]] == [profile["id"]]

        dossier = (
            await api.get(
                f"/admin/professionals/{profile['id']}/verification", headers=ADMIN_HEADERS
            )
        ).json()
        assert dossier["documents"][0]["download_url"].startswith(private_storage.base_url)
        assert [e["to_status"] for e in dossier["events"]] == ["pending"]

        approved = await api.post(
            f"/admin/professionals/{profile['id']}/approve", headers=ADMIN_HEADERS
        )
        assert approved.json()["verification"]["status"] == "approved"
        empty = await api.get(
            "/admin/professionals?verification_status=pending", headers=ADMIN_HEADERS
        )
        assert empty.json()["total"] == 0

    async def test_rejection_refunds_cancels_and_locks_out(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        pro_auth: dict[str, str],
        fake_gateway: FakePaymentGateway,
    ) -> None:
        profile = await register(api, carpentry_category, pro_auth)
        await activate_subscription(api, pro_auth, topup_cents=1800)
        await attach_document(api, pro_auth)
        await api.post("/me/professional/submit", headers=pro_auth)

        rejected = await api.post(
            f"/admin/professionals/{profile['id']}/reject",
            json={"reason": "El modelo 036 no es legible"},
            headers=ADMIN_HEADERS,
        )

        assert rejected.status_code == 200, rejected.text
        body = rejected.json()
        assert body["professional"]["verification"]["status"] == "rejected"
        assert body["refunded"]["amount_cents"] == 1800
        assert body["subscription_canceled"] is True
        assert len(fake_gateway.refunds) == 1
        assert (await api.get("/me/account", headers=pro_auth)).json()["balance"][
            "amount_cents"
        ] == 0

        listing = await api.get("/leads", headers=pro_auth)
        assert listing.status_code == 403
        assert listing.json()["code"] == "PROFESSIONAL_REJECTED"
