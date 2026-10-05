"""Schemas de las feature flags."""

from __future__ import annotations

from pydantic import Field

from app.infrastructure.api.schemas.common import ApiModel


class FeatureFlagsOut(ApiModel):
    """Solo nombre y estado: la version y la descripcion son para quien edita la tabla."""

    flags: dict[str, bool] = Field(examples=[{"new-checkout": True, "admin.reports": False}])
