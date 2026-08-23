"""Motor y sesiones asincronas de SQLAlchemy, y la unidad de trabajo real."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.application.ports import UnitOfWork
from app.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Unidad de trabajo sobre una AsyncSession.

    Soporta anidamiento: solo la salida del bloque mas externo hace commit, para
    que un caso de uso pueda componer varios repositorios sin transacciones
    parciales. Los bloqueos `FOR UPDATE` se sueltan al cerrar la transaccion.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._depth = 0

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def begin(self) -> None:
        self._depth += 1

    async def commit(self) -> None:
        self._depth -= 1
        if self._depth == 0:
            await self._session.commit()

    async def rollback(self) -> None:
        self._depth -= 1
        if self._depth <= 0:
            self._depth = 0
            await self._session.rollback()


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Dependencia de FastAPI: una sesion por peticion."""
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
