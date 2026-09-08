---
name: nueva-migracion
description: Crea y verifica una migracion de Alembic en Reforma Hub, aplicando los arreglos que --autogenerate nunca hace (import de geoalchemy2, CREATE EXTENSION postgis, DROP TYPE de los enums) y comprobando que upgrade y downgrade son reversibles. Usar siempre que se cambie un modelo ORM de apps/api/app/infrastructure/adapters/db/models, se añada o renombre una columna o tabla, aparezca un error UndefinedColumnError o "type already exists", o `alembic check` detecte divergencia entre modelos y esquema.
---

# Nueva migracion de Alembic

En este proyecto `--autogenerate` **no produce migraciones ejecutables**. Falla siempre por
las mismas tres cosas, y por eso este procedimiento no es opcional.

## 1 · Comprobar el punto de partida

```bash
cd apps/api
uv run alembic check       # ¿ya hay divergencia pendiente de otro cambio?
uv run alembic current     # ¿en qué revision esta la BD?
```

Si `alembic check` ya reporta cambios que **no** son tuyos, para y avisa: alguien tiene un
cambio de modelo a medio migrar y generar encima mezclaria dos migraciones en una.

## 2 · Generar

```bash
uv run alembic revision --autogenerate -m "descripcion corta en espanol"
```

## 3 · Aplicar los arreglos mecanicos

```bash
uv run python -m scripts.fix_migration          # sobre la migracion mas reciente
uv run python -m scripts.fix_migration --check  # solo informa, sin escribir
```

Arregla, de forma idempotente:

| Problema | Consecuencia si no se arregla |
|---|---|
| Referencia `geoalchemy2.types.Geography` sin importarlo | `NameError` al ejecutar |
| Falta `CREATE EXTENSION IF NOT EXISTS postgis` | falla en Postgres gestionado o CI limpio |
| `drop_table` no borra los tipos `ENUM` | el `upgrade` siguiente da "type already exists" |

Luego formatea: `uv run ruff format alembic/versions --quiet`.

## 4 · Revisar a mano (esto no lo hace ningun script)

Lee el archivo generado completo. `--autogenerate` compara esquemas, no entiende intenciones:

- **Renombrar una columna** lo detecta como `drop_column` + `add_column`: **pierde los
  datos**. Sustituyelo por `op.alter_column(..., new_column_name=...)`.
- **Renombrar una tabla** igual: usa `op.rename_table`.
- **Columna nueva `NOT NULL` en una tabla con filas**: falla. Añadela nullable, rellena con
  `op.execute("UPDATE …")` y luego `alter_column(nullable=False)`.
- **Indices parciales y expresiones** (`postgresql_where`, `text("created_at DESC")`) a veces
  se emiten mal o se duplican. Comparalos con lo que declara el modelo.
- **`CheckConstraint`** nuevos fallan si los datos existentes no los cumplen.
- **Columnas geograficas**: comprueba que el indice GIST se crea
  (`postgresql_using="gist"`), o las consultas por radio haran *full scan*.

Usa `alembic/versions/*_initial_schema.py` como referencia de cómo debe quedar.

## 5 · Verificar que es reversible

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run alembic check          # debe decir "No new upgrade operations detected"
```

Un `downgrade` que no vuelve a un estado limpio es una migracion que no se puede revertir en
produccion. Si `upgrade` tras `downgrade` falla, casi siempre es un `ENUM` o una extension
que el `downgrade` no borro.

## 6 · Cerrar el cambio

```bash
uv run pytest -m integration    # los repositorios tocan el esquema de verdad
cd ../.. && pnpm lint && pnpm test
```

Y si el cambio afecta a leads, compras o precios, ejecuta tambien la skill
`verificar-flujo-compra`: `alembic check` confirma que el esquema cuadra con los modelos, no
que el flujo de negocio siga funcionando.

## Errores frecuentes y su causa

| Sintoma | Causa |
|---|---|
| `UndefinedColumnError: column X does not exist` | cambiaste el modelo ORM y no generaste migracion |
| `NameError: name 'geoalchemy2' is not defined` | falta el paso 3 |
| `type "lead_status" already exists` | un `downgrade` anterior no borro el enum |
| `alembic check` limpio pero el API da 500 | uvicorn tiene el código viejo en memoria: reinicialo |
| Autogenerate no detecta nada | el modelo no esta importado en `db/models/__init__.py` |
