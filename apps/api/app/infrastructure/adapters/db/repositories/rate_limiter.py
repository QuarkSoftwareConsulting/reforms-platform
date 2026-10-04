"""Limitador de frecuencia sobre Postgres: ventana fija por clave."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import RateLimiterPort
from app.infrastructure.adapters.db.models import RateLimitCounterRow


def window_start(now: datetime, window: timedelta) -> datetime:
    seconds = int(window.total_seconds())
    return datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, tz=UTC)


class SqlAlchemyRateLimiter(RateLimiterPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def allow(self, key: str, *, limit: int, window: timedelta, now: datetime) -> bool:
        start = window_start(now, window)
        # Un solo statement atomico: dos peticiones simultaneas no leen el mismo
        # recuento (el UPSERT serializa sobre la clave primaria).
        stmt = (
            insert(RateLimitCounterRow)
            .values(bucket_key=key, window_start=start, hits=1)
            .on_conflict_do_update(
                index_elements=[RateLimitCounterRow.bucket_key, RateLimitCounterRow.window_start],
                set_={"hits": RateLimitCounterRow.hits + 1},
            )
            .returning(RateLimitCounterRow.hits)
        )
        hits = (await self._session.execute(stmt)).scalar_one()
        # Purga de ventanas viejas en el mismo viaje: el volumen es el de los SMS
        # (pocos) y asi no hace falta otro cron. Usa el indice por fecha.
        await self._session.execute(
            delete(RateLimitCounterRow).where(RateLimitCounterRow.window_start < start - window)
        )
        return bool(hits <= limit)
