"""Adaptadores de reloj e identificadores para produccion."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.application.ports import ClockPort, IdGeneratorPort


class SystemClock(ClockPort):
    def now(self) -> datetime:
        return datetime.now(UTC)


class Uuid4Generator(IdGeneratorPort):
    def new_id(self) -> uuid.UUID:
        return uuid.uuid4()
