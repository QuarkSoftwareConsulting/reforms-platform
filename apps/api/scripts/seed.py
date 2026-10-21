"""Carga las semillas: categorias, servicios y catalogo de codigos postales.

Es idempotente, asi que se puede ejecutar tantas veces como haga falta. El catalogo
(categorias y servicios) es solo carga inicial: crea lo que falta y no toca lo que ya
existe, porque lo gestiona el admin desde el panel. Volver a sembrar no deshace sus
renombres, precios ni desactivaciones, ni retira lo que el admin creo.

Los servicios destacados de la landing tambien: si ninguno lo esta todavia, marca los
de `featured_services.csv` y sube sus fotos (`data/featured/`) al bucket publico.

    uv run python -m scripts.seed
    uv run python -m scripts.seed --postal-codes ruta/al/dataset-completo.csv
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import csv
import sys
import urllib.request
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports import StoragePort
from app.application.use_cases.admin_catalog import catalog_image_prefix
from app.config import get_settings
from app.infrastructure.adapters.db.models import CategoryRow, PostalCodeRow, ServiceRow
from app.infrastructure.adapters.db.session import create_engine, create_session_factory
from app.infrastructure.api.dependencies import create_storage

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


async def seed_featured_services(
    session_factory: async_sessionmaker[AsyncSession], storage: StoragePort, path: Path
) -> int:
    """Marca los destacados iniciales y sube sus fotos, solo si no hay ninguno.

    En cuanto el admin destaca algo, la landing es suya: volver a sembrar no anade los
    que el quito ni pisa las fotos que subio.
    """
    rows = read_csv(path)
    async with session_factory() as session:
        already = await session.execute(select(ServiceRow.id).where(ServiceRow.featured).limit(1))
        if not rows or already.first() is not None:
            return 0
        services = {
            (category_slug, service.slug): service
            for service, category_slug in (
                await session.execute(select(ServiceRow, CategoryRow.slug).join(CategoryRow))
            ).tuples()
        }
        uploaded: list[str] = []
        try:
            for row in rows:
                service = services.get((row["category_slug"], row["service_slug"]))
                if service is None:
                    print(
                        "featured_services.csv: no existe "
                        f"{row['category_slug']}/{row['service_slug']}"
                    )
                    continue
                image = path.parent / "featured" / row["image"]
                upload = await storage.create_presigned_upload(
                    key_prefix=catalog_image_prefix(service.id),
                    filename=row["image"],
                    content_type="image/webp",
                )
                # La misma subida firmada que usa el navegador: no hace falta otra via.
                request = urllib.request.Request(
                    upload.upload_url,
                    data=image.read_bytes(),
                    method=upload.method,
                    headers=upload.headers,
                )
                await asyncio.to_thread(urllib.request.urlopen, request, timeout=30)
                uploaded.append(upload.storage_key)
                service.image_key = upload.storage_key
                service.featured = True
                service.landing_name_es = row.get("landing_name_es") or None
                service.landing_name_en = row.get("landing_name_en") or None
            await session.commit()
        except BaseException:
            # Sin commit nada enlaza lo ya subido, y el siguiente intento lo subira de
            # nuevo con otra clave: se borra para no dejar huerfanos en el bucket.
            for key in uploaded:
                with contextlib.suppress(Exception):
                    await storage.delete(key)
            raise
    return len(uploaded)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Carga las semillas de Reforma Hub")
    parser.add_argument("--categories", type=Path, default=DATA_DIR / "categories.csv")
    parser.add_argument("--services", type=Path, default=DATA_DIR / "services.csv")
    parser.add_argument("--postal-codes", type=Path, default=DATA_DIR / "postal_codes_es.csv")
    parser.add_argument("--featured", type=Path, default=DATA_DIR / "featured_services.csv")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    try:
        categories = await seed_categories(session_factory, args.categories)
        services = await seed_services(session_factory, args.services)
        postal_codes = await seed_postal_codes(session_factory, args.postal_codes)
        try:
            featured = await seed_featured_services(
                session_factory, create_storage(settings), args.featured
            )
        except Exception as exc:
            # Sin bucket (MinIO parado, sin credenciales) el catalogo sigue sirviendo; la
            # landing no muestra tarjetas hasta que el admin suba las fotos.
            print(f"No se pudieron cargar los destacados de la landing: {exc}")
            featured = 0
    finally:
        await engine.dispose()

    print(
        f"Semillas cargadas: {categories} categorias, {services} servicios, "
        f"{postal_codes} codigos postales, {featured} destacados"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
