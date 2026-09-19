"""La lectura de fotos no debe hacer red en el event loop de los endpoints."""

from __future__ import annotations

import threading
from unittest.mock import AsyncMock, Mock

import pytest

from app.application.dto import (
    AdminLeadItem,
    AdminLeadListResult,
    LeadDetail,
    LeadListItem,
    LeadListResult,
)
from app.infrastructure.api.v1 import admin, leads
from tests.factories import make_category, make_lead, make_professional


@pytest.mark.parametrize("endpoint", ["list", "detail", "admin"])
async def test_photo_serialization_runs_in_worker_and_preserves_contract(endpoint: str) -> None:
    loop_thread = threading.get_ident()
    category = make_category()
    lead = make_lead(category_id=category.id)
    view = lead.public_view()
    price = category.suggested_lead_price
    container = Mock()
    count = 0

    def public_url(key: str) -> str:
        nonlocal count
        assert threading.get_ident() != loop_thread
        assert key == lead.photos[0].storage_key
        count += 1
        return f"https://storage.googleapis.com/private/{key}?signature={count}"

    container.infra.storage.public_url.side_effect = public_url
    container.list_leads.execute = AsyncMock(
        return_value=LeadListResult([LeadListItem(view, category, price, None, False)], 1, 20, 0)
    )
    container.lead_detail.execute = AsyncMock(
        return_value=LeadDetail(view, category, price, None, None, None)
    )
    container.admin_leads.execute = AsyncMock(
        return_value=AdminLeadListResult(
            [AdminLeadItem(view, category, price, lead.status, lead.source, 0, 3)], 1, 20, 0
        )
    )

    for expected in (1, 2):
        if endpoint == "list":
            result = await leads.list_leads(container, make_professional(), "es")
            item = result.items[0]
        elif endpoint == "detail":
            result = await leads.get_lead(lead.id, container, make_professional(), "es")
            assert result.contact is None
            item = result.lead
        else:
            result = await admin.list_admin_leads(container, "es", Mock())
            item = result.items[0]
        assert item.photo_urls == [
            f"https://storage.googleapis.com/private/{lead.photos[0].storage_key}?signature={expected}"
        ]
        assert "client_phone" not in item.model_dump()
    assert lead.photos[0].storage_key == "leads/x/1.jpg"
