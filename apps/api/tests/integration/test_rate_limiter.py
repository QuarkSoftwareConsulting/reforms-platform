"""Limitador de SMS contra Postgres: compartido entre conexiones y atomico."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.infrastructure.adapters.db.repositories import SqlAlchemyRateLimiter

NOW = datetime(2026, 3, 1, 12, 30, tzinfo=UTC)
HOUR = timedelta(hours=1)


async def test_counts_across_connections_without_losing_hits(
    engine: AsyncEngine,
    session: AsyncSession,  # vacia las tablas antes del test
) -> None:
    """Como si fueran instancias distintas del API: 12 intentos a la vez, tope 10.

    Un leer-y-sumar en dos pasos perderia intentos con la concurrencia; el UPSERT
    atomico cuenta los 12 y deja pasar exactamente 10.
    """
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def attempt() -> bool:
        async with factory() as own:
            allowed = await SqlAlchemyRateLimiter(own).allow(
                "sms-origin:83.45.12.9", limit=10, window=HOUR, now=NOW
            )
            await own.commit()
            return allowed

    results = await asyncio.wait_for(asyncio.gather(*(attempt() for _ in range(12))), timeout=20)

    assert sorted(results) == [False, False] + [True] * 10
    async with factory() as check:
        hits = await check.execute(
            text("SELECT hits FROM rate_limit_counters WHERE bucket_key = 'sms-origin:83.45.12.9'")
        )
        assert hits.scalar_one() == 12


async def test_a_new_window_starts_from_zero_and_old_ones_are_purged(
    session: AsyncSession,
) -> None:
    limiter = SqlAlchemyRateLimiter(session)
    for _ in range(3):
        await limiter.allow("k", limit=2, window=HOUR, now=NOW)
    assert not await limiter.allow("k", limit=2, window=HOUR, now=NOW)

    assert await limiter.allow("k", limit=2, window=HOUR, now=NOW + HOUR)
    # Dos ventanas despues, la primera ya no sirve para nada y se borra.
    await limiter.allow("otra", limit=2, window=HOUR, now=NOW + 2 * HOUR)
    rows = await session.execute(text("SELECT count(*) FROM rate_limit_counters"))
    assert rows.scalar_one() == 2
