# AGENTS.md — Backend (`apps/api`)

Reglas específicas del backend. Complementan (y en caso de conflicto, tienen prioridad
sobre) el [`AGENTS.md` raíz](../../AGENTS.md), que contiene los invariantes de negocio que
**no** se repiten aquí. Léelo antes.

FastAPI + arquitectura hexagonal, Python 3.13, gestionado con **uv**.

---

## Mapa de capas

```
app/
├── domain/                 NÚCLEO. Cero imports externos.
│   ├── value_objects/      Money, Coordinates, PostalCode, Email, PhoneNumber
│   ├── models/             Lead, Professional, Purchase, Category, User + enums
│   └── exceptions/         DomainError y descendientes, cada uno con `code` y `status`
├── application/
│   ├── ports/              Interfaces abstractas (repositorios, pagos, storage, reloj…)
│   ├── use_cases/          Un archivo por interacción de negocio
│   └── dto/                Entradas/salidas de casos de uso (dataclasses, no Pydantic)
├── infrastructure/
│   ├── adapters/db/        SQLAlchemy 2.0 async + PostGIS: models, mappers, repositories
│   ├── adapters/payments/  Stripe
│   ├── adapters/auth/      Firebase Auth
│   ├── adapters/storage/   S3 / MinIO / R2
│   └── api/                Routers v1, schemas Pydantic, middlewares, dependencies
├── config/                 Settings (pydantic-settings) y logging estructurado
├── jobs/                   Comandos para cron
└── main.py                 Ensamblado de la app
```

**Regla de dependencias, en una línea:** las flechas apuntan siempre hacia dentro.
`infrastructure` → `application` → `domain`. Nunca al revés.

---

## Cómo añadir cosas

### Un caso de uso

1. Si necesita un servicio externo nuevo, define primero el **puerto** en
   `application/ports/` — una clase abstracta con el vocabulario del negocio, no el de la
   librería (`create_checkout_session`, no `stripe_create_session`).
2. Escribe el caso de uso en `application/use_cases/` como `@dataclass(slots=True)` con los
   puertos como campos y un método `execute()`. Sin estado entre llamadas.
3. **Tests con fakes primero** (`tests/fakes/`), antes de tocar infraestructura. Si el caso
   de uso no se puede probar sin BD, las dependencias están mal puestas.
4. Impleméntalo en `infrastructure/adapters/`.
5. Cablealo en `infrastructure/api/dependencies.py` (una `@property` en `RequestContainer`).
6. Exponlo en un router de `infrastructure/api/v1/` y añade su test en `tests/api/`.

### Un código de error

El `code` es el contrato con el frontend. Tres archivos, siempre los tres:

```python
# 1. app/domain/exceptions/__init__.py
class LeadExpiredError(DomainError):
    """La solicitud ha caducado."""  # el docstring es el mensaje por defecto

    code = "LEAD_EXPIRED"  # estable: el frontend lo usa como clave
    status = 409  # el middleware lo traduce a HTTP
```
```jsonc
// 2. apps/web/messages/es.json  →  "errors": { "LEAD_EXPIRED": "..." }
// 3. apps/web/messages/en.json  →  la misma clave, traducida
```

Añádelo también a `__all__`. El middleware (`api/middlewares/error_handler.py`) no necesita
cambios: lee `code` y `status` de la excepción.

### Una migración

```bash
uv run alembic revision --autogenerate -m "descripcion corta"
```

**Revisa siempre el archivo generado.** `--autogenerate` falla de forma sistemática en tres
cosas en este proyecto:

- No añade `import geoalchemy2` aunque las columnas `Geography` lo referencien → `NameError`.
- No emite `CREATE EXTENSION IF NOT EXISTS postgis` (necesario en Postgres gestionado, donde
  el script de `docker-compose` no corre).
- No borra los tipos `ENUM` en el `downgrade` (`DROP TYPE`), porque `drop_table` no lo hace.

Usa `alembic/versions/*_initial_schema.py` como referencia y verifica:

```bash
uv run alembic upgrade head && uv run alembic downgrade base && uv run alembic upgrade head
uv run alembic check      # debe decir "No new upgrade operations detected"
```

---

## Repositorios: lo que hay que saber

- **Escrituras devuelven la entidad de dominio recibida**, no un re-mapeo de la fila. Tras
  el `flush`, una columna geográfica sigue conteniendo el `WKTElement` que asignaste; leerla
  con `to_shape()` reventaría. No lo "arregles".
- **Lecturas usan `select(...).execution_options(populate_existing=True)`** (patrón
  `_load_row`), no `session.get(..., options=[...])`: `get` devuelve la instancia cacheada
  ignorando los eager loads y la relación no cargada explota con `MissingGreenlet`.
- **Parámetros geográficos con `to_geography()`** (`mappers.py`), que devuelve un
  `WKTElement`. Un string se bindea como `VARCHAR` y Postgres rechaza `ST_DWithin`.
- `created_at` se asigna explícitamente desde el dominio en los `apply_*` de `mappers.py`:
  el `server_default` de Postgres sería un segundo reloj y rompería los TTL.
- El precio de venta se resuelve en un solo sitio: `Lead.sale_price(suggested=...)`. Los
  repositorios guardan el `price_override` con su divisa al lado (`price_override_cents` +
  `price_override_currency`) para que mapear la fila no exija cargar también el oficio; la
  BD obliga a que ambas columnas estén o falten juntas.
- El conteo de plazas vivas está en un solo sitio: `_occupying_slot_clause()` en
  `purchase_repository.py`. Si cambias qué estados ocupan plaza, cámbialo ahí **y** en
  `PurchaseStatus.occupies_slot` (dominio), y comprueba el índice único parcial
  `uq_lead_purchases_active` de la migración.

---

## Tests

```bash
uv run pytest -m "not integration"     # 190 tests, sin Docker, < 3 s
uv run pytest                          # 251 tests (necesita `pnpm infra:up`)
uv run pytest tests/unit/domain -x -q  # iteración rápida sobre las reglas
```

- Construye entidades con las factorías de `tests/factories.py`. Si añades un campo
  obligatorio al dominio, se arregla en un solo sitio.
- Los tests de casos de uso usan la fixture `world` (`tests/conftest.py`): monta el sistema
  completo con adaptadores in-memory. Los atajos `world.add_lead/add_professional/…` evitan
  15 líneas de setup por test.
- `pytest.ini_options` tiene `asyncio_mode = "auto"`: no hace falta decorar los tests async.
  El *loop scope* es `session` porque el engine de la BD de test es de ámbito sesión.
- Los repositorios fake hacen `await _round_trip()` al principio de cada método para ceder
  el control al event loop. Es lo que hace que los tests de concurrencia prueben algo. Si
  añades un método a un fake, añade también esa llamada.

---

## Configuración

Todo por variables de entorno vía `config/settings.py` (pydantic-settings). Para añadir una:
campo tipado con default seguro para desarrollo, y documéntala en `.env.example` (raíz).

`Settings.assert_production_ready()` se ejecuta al arrancar y **niega el arranque** en
producción si falta un secreto crítico o si el emulador de Firebase está configurado. Es
deliberado: es mejor no arrancar que aceptar pagos que no se pueden confirmar o tokens que
no se pueden verificar. Si añades un secreto imprescindible, añádelo a esa comprobación.

---

## SDK externos: cuidado

- **Stripe** es sincrónico → toda llamada va en `asyncio.to_thread(...)`. Y devuelve
  `StripeObject`, **no** `dict`: en `parse_webhook_event` se serializa con
  `json.loads(str(event.data.object))` porque `to_dict()` es superficial (deja `metadata`
  como `StripeObject`) y `_to_dict_recursive` es privado.
- **Cualquier fallo de Stripe** se traduce a `PaymentGatewayError` (503) dentro del
  adaptador. Nunca dejes escapar una excepción de librería: se convierte en un 500 sin
  contexto para el profesional.
- **Firebase** `verify_id_token` hace red y es sincrónico → también en `to_thread`. El
  emulador se activa con `FIREBASE_AUTH_EMULATOR_HOST` y usa `EmulatorCredentials`
  (`firebase_admin.credentials.GoogleAuthCredentials` es la base abstracta, no una
  credencial usable).
- Los adaptadores externos llevan `ignore_missing_imports` en mypy porque no traen stubs.
  Eso no es permiso para usar `Any` en las capas de dentro.
