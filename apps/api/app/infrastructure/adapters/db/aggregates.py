"""Agregados por dia para el dashboard del admin."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.application.ports import DailyCount


async def daily_counts(
    session: AsyncSession,
    *,
    at: InstrumentedAttribute[datetime] | InstrumentedAttribute[datetime | None],
    start: datetime,
    end: datetime,
    tz: str,
    where: ColumnElement[bool] | None = None,
    currency: InstrumentedAttribute[str] | None = None,
    amount: InstrumentedAttribute[int] | None = None,
) -> list[DailyCount]:
    """Cuenta (y suma por divisa, si se pide) las filas de `[start, end)` por dia local.

    El dia se corta en `tz` dentro de Postgres (`timezone(tz, at)`): agrupar en UTC
    llevaria al dia anterior lo que pasa entre medianoche y la 1 (o las 2) en Madrid.
    """
    day = cast(func.timezone(tz, at), Date).label("day")
    columns: list[Any] = [day, func.count()]
    if currency is not None and amount is not None:
        columns += [currency, func.sum(amount)]
    stmt = select(*columns).where(at >= start, at < end)
    if where is not None:
        stmt = stmt.where(where)
    stmt = stmt.group_by(day, *([currency] if currency is not None else []))

    counts: dict[date, int] = {}
    amounts: dict[date, dict[str, int]] = {}
    for row in (await session.execute(stmt)).all():
        row_day: date = row[0]
        counts[row_day] = counts.get(row_day, 0) + int(row[1])
        bucket = amounts.setdefault(row_day, {})
        if currency is not None:
            bucket[row[2]] = bucket.get(row[2], 0) + int(row[3] or 0)
    return [
        DailyCount(day=row_day, count=counts[row_day], amount_by_currency=amounts[row_day])
        for row_day in sorted(counts)
    ]
