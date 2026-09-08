#!/usr/bin/env python
"""Aplica a una migracion de Alembic los arreglos que --autogenerate nunca hace.

`alembic revision --autogenerate` produce en este proyecto migraciones que fallan
al ejecutarse, siempre por las mismas tres razones:

1. Referencia `geoalchemy2.types.Geography` sin importar `geoalchemy2` -> NameError.
2. No emite `CREATE EXTENSION IF NOT EXISTS postgis`, asi que la migracion no
   funciona en un Postgres donde el script de docker-compose no ha corrido (RDS,
   Neon, Supabase, un CI limpio).
3. `drop_table` no borra los tipos ENUM que `create_table` creo, asi que el
   `downgrade` deja basura y un `upgrade` posterior falla con "type already exists".

Este script las corrige. Es idempotente: pasarlo dos veces no cambia nada.

Uso:
    uv run python -m scripts.fix_migration                    # la mas reciente
    uv run python -m scripts.fix_migration --check            # solo informa, no escribe
    uv run python -m scripts.fix_migration alembic/versions/abc_x.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"

EXTENSION_STATEMENT = 'op.execute("CREATE EXTENSION IF NOT EXISTS postgis")'
GREEN, YELLOW, DIM, RESET = "\033[32m", "\033[33m", "\033[2m", "\033[0m"


def display_path(path: Path) -> str:
    """Ruta relativa al cwd si se puede; si no, la absoluta."""
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def newest_migration() -> Path:
    candidates = sorted(
        (p for p in VERSIONS_DIR.glob("*.py") if p.name != "__init__.py"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise SystemExit(f"No hay migraciones en {VERSIONS_DIR}")
    return candidates[-1]


def find_enum_names(source: str) -> list[str]:
    """Nombres de los tipos ENUM que la migracion crea.

    Alembic los emite como `sa.Enum("a", "b", name="lead_status")` y, si el modelo
    usa el dialecto explicitamente, como `postgresql.ENUM(...)`. Se cubren ambos.
    """
    names = re.findall(
        r"(?:sa\.Enum|postgresql\.ENUM)\([^)]*?name=[\"\']([a-z_]+)[\"\']",
        source,
        re.DOTALL,
    )
    # Se preserva el orden de aparicion, sin duplicados.
    return list(dict.fromkeys(names))


def add_geoalchemy_import(source: str) -> tuple[str, str | None]:
    if "geoalchemy2" not in source:
        return source, None
    if re.search(r"^import geoalchemy2$", source, re.MULTILINE):
        return source, None
    fixed = source.replace(
        "import sqlalchemy as sa", "import geoalchemy2\nimport sqlalchemy as sa", 1
    )
    if fixed == source:
        return source, None
    return fixed, "anadido `import geoalchemy2` (lo referencia pero no lo importaba)"


def add_postgis_extension(source: str) -> tuple[str, str | None]:
    if "geoalchemy2" not in source:
        return source, None
    if "CREATE EXTENSION IF NOT EXISTS postgis" in source:
        return source, None
    match = re.search(r"^def upgrade\(\) -> None:\n", source, re.MULTILINE)
    if match is None:
        return source, None
    insert_at = match.end()
    fixed = f"{source[:insert_at]}    {EXTENSION_STATEMENT}\n\n{source[insert_at:]}"
    return fixed, "anadido CREATE EXTENSION postgis al principio de upgrade()"


def add_enum_drops(source: str) -> tuple[str, str | None]:
    enums = find_enum_names(source)
    if not enums:
        return source, None
    if "DROP TYPE IF EXISTS" in source:
        return source, None

    match = re.search(r"^def downgrade\(\) -> None:\n", source, re.MULTILINE)
    if match is None:
        return source, None

    # Se anade al final del cuerpo de downgrade, tras el ultimo drop_table.
    body_start = match.end()
    body = source[body_start:]
    # El cuerpo termina en la primera linea de nivel 0 (o al final del archivo).
    end_match = re.search(r"^\S", body, re.MULTILINE)
    body_end = body_start + (end_match.start() if end_match else len(body))

    # Se borran en orden inverso al de creacion, por simetria con las tablas.
    tuple_literal = ", ".join(f'"{name}"' for name in reversed(enums))
    block = (
        "    # Los tipos ENUM no los borra drop_table: hay que hacerlo a mano o el\n"
        "    # siguiente upgrade falla con 'type already exists'.\n"
        f"    for enum_name in ({tuple_literal}):\n"
        '        op.execute(f"DROP TYPE IF EXISTS {enum_name}")\n'
    )
    fixed = f"{source[:body_end].rstrip()}\n{block}{source[body_end:]}"
    return fixed, f"anadido DROP TYPE para {len(enums)} enum(s): {', '.join(enums)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path", nargs="?", type=Path, help="migracion a arreglar (por defecto, la mas reciente)"
    )
    parser.add_argument("--check", action="store_true", help="informa de lo que falta sin escribir")
    args = parser.parse_args()

    path = args.path or newest_migration()
    if not path.exists():
        raise SystemExit(f"No existe {path}")

    original = path.read_text(encoding="utf-8")
    source = original
    applied: list[str] = []

    for fixer in (add_geoalchemy_import, add_postgis_extension, add_enum_drops):
        source, note = fixer(source)
        if note:
            applied.append(note)

    print(f"{DIM}{display_path(path)}{RESET}")

    if not applied:
        print(f"  {GREEN}Nada que arreglar.{RESET}")
        return 0

    for note in applied:
        print(f"  {YELLOW}·{RESET} {note}")

    if args.check:
        print(f"\n{YELLOW}--check: no se ha escrito nada.{RESET} Ejecutalo sin --check.")
        return 1

    path.write_text(source, encoding="utf-8")
    print(f"\n{GREEN}Migracion actualizada.{RESET} Revisa el diff y verifica con:")
    print(
        f"  {DIM}uv run ruff format alembic/versions --quiet\n"
        f"  uv run alembic upgrade head && uv run alembic downgrade base "
        f"&& uv run alembic upgrade head\n"
        f"  uv run alembic check{RESET}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
