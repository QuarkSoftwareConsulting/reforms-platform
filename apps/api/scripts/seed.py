"""Carga las semillas: categorias, servicios y catalogo de codigos postales.

Es idempotente, asi que se puede ejecutar tantas veces como haga falta. El catalogo
(categorias y servicios) es solo carga inicial: crea lo que falta y no toca lo que ya
existe, porque lo gestiona el admin desde el panel. Volver a sembrar no deshace sus
renombres, precios ni desactivaciones, ni retira lo que el admin creo.

    uv run python -m scripts.seed
    uv run python -m scripts.seed --postal-codes ruta/al/dataset-completo.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.infrastructure.adapters.db.models import CategoryRow, PostalCodeRow, ServiceRow
from app.infrastructure.adapters.db.session import create_engine, create_session_factory

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def read_csv(path: Path) -> list[dict[str, str]]:
    """Lee un CSV ignorando las lineas de comentario que empiezan por `#`."""
    with path.open(encoding="utf-8") as handle:
        lines = [line for line in handle if not line.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


async def seed_categories(session_factory: async_sessionmaker[AsyncSession], path: Path) -> int:
    rows = read_csv(path)
    if not rows:
        return 0

    async with session_factory() as session:
        for row in rows:
            stmt = (
                insert(CategoryRow)
                .values(
                    slug=row["slug"],
                    name_es=row["name_es"],
                    name_en=row["name_en"],
                    suggested_lead_price_cents=int(row["suggested_lead_price_cents"]),
                    currency=row["currency"],
                    sort_order=int(row.get("sort_order") or 0),
                    active=True,
                )
                # Lo que ya existe es del admin (nombre, orden, precio, si esta activo).
                .on_conflict_do_nothing(index_elements=[CategoryRow.slug])
            )
            await session.execute(stmt)
        await session.commit()
    return len(rows)


async def seed_services(session_factory: async_sessionmaker[AsyncSession], path: Path) -> int:
    rows = read_csv(path)
    if not rows:
        return 0

    async with session_factory() as session:
        categories: dict[str, UUID] = dict(
            (await session.execute(select(CategoryRow.slug, CategoryRow.id))).tuples().all()
        )
        for index, row in enumerate(rows):
            category_id = categories.get(row["category_slug"])
            if category_id is None:
                raise SystemExit(f"services.csv: categoria desconocida {row['category_slug']!r}")
            stmt = (
                insert(ServiceRow)
                .values(
                    category_id=category_id,
                    slug=row["slug"],
                    name_es=row["name_es"],
                    name_en=row["name_en"],
                    sort_order=index,
                    active=True,
                )
                # Igual que con las categorias: lo que ya existe lo gestiona el admin.
                .on_conflict_do_nothing(constraint="uq_services_category_slug")
            )
            await session.execute(stmt)
        await session.commit()
    return len(rows)


async def seed_postal_codes(session_factory: async_sessionmaker[AsyncSession], path: Path) -> int:
    rows = read_csv(path)
    if not rows:
        return 0

    async with session_factory() as session:
        # Se insertan por lotes: el dataset completo de Espana ronda las 11.000 filas.
        batch_size = 500
        for start in range(0, len(rows), batch_size):
            values = [
                {
                    "code": row["code"].strip(),
                    "country": row.get("country", "ES") or "ES",
                    "city": row["city"].strip(),
                    "province": row["province"].strip(),
                    "location": (
                        f"SRID=4326;POINT({float(row['longitude'])} {float(row['latitude'])})"
                    ),
                }
                for row in rows[start : start + batch_size]
            ]
            stmt = (
                insert(PostalCodeRow)
                .values(values)
                .on_conflict_do_update(
                    index_elements=[PostalCodeRow.code],
                    set_={
                        "city": insert(PostalCodeRow).excluded.city,
                        "province": insert(PostalCodeRow).excluded.province,
                        "location": insert(PostalCodeRow).excluded.location,
                    },
                )
            )
            await session.execute(stmt)
        await session.commit()
    return len(rows)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Carga las semillas de Reforma Hub")
    parser.add_argument("--categories", type=Path, default=DATA_DIR / "categories.csv")
    parser.add_argument("--services", type=Path, default=DATA_DIR / "services.csv")
    parser.add_argument("--postal-codes", type=Path, default=DATA_DIR / "postal_codes_es.csv")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    try:
        categories = await seed_categories(session_factory, args.categories)
        services = await seed_services(session_factory, args.services)
        postal_codes = await seed_postal_codes(session_factory, args.postal_codes)
    finally:
        await engine.dispose()

    print(
        f"Semillas cargadas: {categories} categorias, {services} servicios, "
        f"{postal_codes} codigos postales"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
