"""Schemas compartidos."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Locale = Literal["es", "en"]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ErrorResponse(ApiModel):
    """Cuerpo uniforme de error. `code` es estable y el frontend lo traduce."""

    code: str = Field(examples=["LEAD_CAP_REACHED"])
    message: str
    details: dict[str, object] | None = None


class MoneyOut(ApiModel):
    amount_cents: int
    currency: str
    formatted: str


class HealthOut(ApiModel):
    status: Literal["ok", "degraded"]
    environment: str
    database: bool
