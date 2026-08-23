"""Schemas de compras y del historial de contactos."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.infrastructure.api.schemas.common import ApiModel, MoneyOut
from app.infrastructure.api.schemas.leads import (
    CategoryOut,
    ClientContactOut,
    PurchaseOut,
)


class StartPurchaseOut(ApiModel):
    purchase_id: UUID
    checkout_url: str
    amount: MoneyOut
    expires_at: datetime | None = None


class PurchasedLeadOut(ApiModel):
    """Fila de "Mis contactos"."""

    lead_id: UUID
    title: str
    city: str
    province: str
    category: CategoryOut
    purchase: PurchaseOut
    is_unlocked: bool
    contact: ClientContactOut | None = None


class WebhookAckOut(ApiModel):
    received: bool
    handled: bool
    duplicate: bool = False
