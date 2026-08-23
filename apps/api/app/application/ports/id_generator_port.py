"""Puerto de generacion de identificadores, para tests reproducibles."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class IdGeneratorPort(ABC):
    @abstractmethod
    def new_id(self) -> UUID: ...
