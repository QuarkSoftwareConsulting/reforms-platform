"""Puerto de unidad de trabajo: agrupa varias escrituras en una transaccion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self


class UnitOfWork(ABC):
    """Contexto transaccional.

    Al salir sin excepcion hace commit; con excepcion hace rollback. Es lo que
    garantiza que la reserva de plaza y la creacion de la compra sean atomicas.
    """

    async def __aenter__(self) -> Self:
        await self.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()

    @abstractmethod
    async def begin(self) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
