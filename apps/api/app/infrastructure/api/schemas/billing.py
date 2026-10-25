"""Schemas de la recarga mensual y del saldo del profesional."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.infrastructure.api.schemas.common import ApiModel, MoneyOut

SubscriptionStatusOut = Literal["none", "pending", "active", "past_due", "canceled"]


class CreditEntryOut(ApiModel):
    kind: str
    amount: MoneyOut
    signed_amount_cents: int
    created_at: datetime


class AccountOut(ApiModel):
    """Estado de la recarga. `is_active` es lo que decide si puede comprar."""

    status: SubscriptionStatusOut
    is_active: bool
    balance: MoneyOut
    topup_amount: MoneyOut | None
    """`null` si el admin aun no fijo la mensualidad: nadie se puede suscribir."""
    current_period_end: datetime | None = None
    can_manage_billing: bool
    entries: list[CreditEntryOut] = Field(default_factory=list)
    debt: MoneyOut | None = None
    """Recarga devuelta por el banco ya gastada. Con deuda no se compra, aunque
    `is_active` sea verdadero; se salda con la siguiente recarga."""


class SubscriptionCheckoutOut(ApiModel):
    checkout_url: str


class BillingPortalOut(ApiModel):
    url: str


class CreditAdjustmentIn(ApiModel):
    """Ajuste manual de saldo. Positivo abona, negativo carga."""

    amount_cents: int = Field(ge=-100_000, le=100_000)
    note: str = Field(min_length=3, max_length=500)


class AdminAccountOut(ApiModel):
    status: SubscriptionStatusOut
    is_active: bool
    balance: MoneyOut
    debt: MoneyOut | None = None
    current_period_end: datetime | None = None


class SubscriptionPriceOut(ApiModel):
    """Mensualidad vigente para las suscripciones nuevas."""

    amount: MoneyOut | None
    updated_at: datetime | None = None
    configured: bool
    """False si el admin aun no la fijo: nadie se puede suscribir."""


class PublicSubscriptionPriceOut(ApiModel):
    """Lo que la landing anuncia. Sin el `stripe_price_id` ni quien lo fijo."""

    amount: MoneyOut | None
    """`null` si el admin aun no la fijo."""


class SetSubscriptionPriceIn(ApiModel):
    amount_cents: int = Field(ge=50, le=100_000)
