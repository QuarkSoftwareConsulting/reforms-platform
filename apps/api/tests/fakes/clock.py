from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from app.application.ports import ClockPort, IdGeneratorPort


class FakeClock(ClockPort):
    """Reloj controlable: los tests avanzan el tiempo explicitamente."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs: float) -> datetime:
        self._now += timedelta(**kwargs)
        return self._now

    def set(self, value: datetime) -> None:
        self._now = value


class SequentialIdGenerator(IdGeneratorPort):
    """UUIDs deterministas (0000...0001, 0000...0002, ...) para asserts legibles."""

    def __init__(self) -> None:
        self._counter = 0
        self.issued: list[UUID] = []

    def new_id(self) -> UUID:
        self._counter += 1
        value = UUID(int=self._counter)
        self.issued.append(value)
        return value
