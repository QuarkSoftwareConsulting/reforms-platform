"""Puerto de reloj: permite testear la caducidad de reservas de forma determinista."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class ClockPort(ABC):
    @abstractmethod
    def now(self) -> datetime:
        """Instante actual en UTC (siempre timezone-aware)."""
