# AGENTS.md — Reforma Hub

Guía para agentes de IA (Claude Code, Codex, Cursor, Copilot…) que trabajen en este
repositorio. Los humanos empiezan por [`README.md`](./README.md); este archivo cubre lo
que un agente necesita para **no romper nada**.

Hay archivos `AGENTS.md` más específicos en [`apps/api/`](./apps/api/AGENTS.md) y
[`apps/web/`](./apps/web/AGENTS.md). **Gana el más cercano al archivo que estés editando**:
si tocas el backend, las reglas de `apps/api/AGENTS.md` tienen prioridad sobre las de aquí.

---

## 1. Qué es este producto

Marketplace **pay-per-lead** de oficios. El cliente publica gratis lo que necesita; el
profesional paga por desbloquear su contacto. **El precio de cada contacto lo decide el
admin**: la categoría solo aporta un precio sugerido (§4.9). **Cada solicitud se vende a un
máximo de 3 profesionales.** Esa regla, y la protección de los datos personales del cliente, son
el producto — no un detalle de implementación.

Monorepo: `apps/api` (FastAPI hexagonal, Python 3.13 + uv) y `apps/web` (Next.js 15,
TypeScript + pnpm). Estado y alcance de la fase actual: ver `README.md`.

---

## 2. Puesta en marcha

Usa Node 22.22.2 y pnpm 10.34.5. Se recomienda ejecutar `nvm use` desde la raíz;
`.nvmrc` fija Node y `packageManager` en `package.json` fija pnpm.

```bash
pnpm infra:up                       # PostGIS :5433, BD de test :5434, MinIO :9000
cp .env.example apps/api/.env       # sección BACKEND
cp .env.example apps/web/.env.local # sección FRONTEND

cd apps/api && uv sync && cd ../..
pnpm api:migrate && pnpm api:seed
pnpm api:dev                        # http://localhost:8010   (OpenAPI en /docs)
pnpm web:dev                        # http://localhost:3010
```

> **Los puertos son 8010 (API) y 3010 (web), no 8000/3000.** En esta máquina 8000 y 3000
> los ocupan otros contenedores. No los "corrijas" a los valores por defecto.

Para el login hace falta el emulador de Firebase Auth (no requiere service account):

```bash
npx -y firebase-tools emulators:start --only auth \
  --project reforma-hub-dev --config infra/firebase.json
```

---

## 3. Comandos que debes usar

| Objetivo | Comando |
|---|---|
| Todo el lint (ruff + mypy strict + eslint + tsc) | `pnpm lint` |
| Todos los tests (308 back + 61 front) | `pnpm test` |
| Backend rápido, **sin Docker** (190 tests) | `cd apps/api && uv run pytest -m "not integration"` |
| Backend completo (requiere `pnpm infra:up`) | `pnpm api:test` |
| Un solo test de backend | `cd apps/api && uv run pytest tests/unit/domain/test_lead.py -k capping` |
| Frontend en watch | `pnpm --filter web test:watch` |
| ¿Modelos y esquema divergen? | `cd apps/api && uv run alembic check` |
| Flujo de compra end-to-end contra servicios reales | `pnpm verify:flow` |
| Arreglar lo que `--autogenerate` no hace | `cd apps/api && uv run python -m scripts.fix_migration` |
| Recrear la BD desde cero | `pnpm infra:reset && pnpm api:migrate && pnpm api:seed` |

**Antes de dar por terminada cualquier tarea: `pnpm lint && pnpm test` en verde.** No
declares algo hecho si no has ejecutado esto.

Si el cambio toca leads, compras, pagos o autenticación, además: `pnpm verify:flow`. Cubre
lo que los fakes no pueden ver — ver §7.

### Procedimientos documentados

Tres tareas recurrentes tienen su procedimiento escrito paso a paso. En Claude Code son
*skills* que se invocan solas; con cualquier otra herramienta, **son documentación: ábrela y
síguela**.

| Procedimiento | Cuándo | Archivo |
|---|---|---|
| Verificar el flujo de compra | Antes de cerrar un cambio en leads, pagos o auth | `.claude/skills/verificar-flujo-compra/SKILL.md` |
| Nueva migración | Al cambiar un modelo ORM, o ante `UndefinedColumnError` | `.claude/skills/nueva-migracion/SKILL.md` |
| Nuevo caso de uso | Al añadir funcionalidad de backend o un endpoint | `.claude/skills/nuevo-caso-de-uso/SKILL.md` |

Los tests marcados `integration` se **omiten solos** si `db-test` no está levantada, con un
mensaje que indica el comando. Un `skip` no es un `pass`: si tu cambio toca repositorios,
levanta Docker y ejecútalos.

---

## 4. Invariantes: no los rompas

Estas reglas parecen rodeos innecesarios hasta que entiendes por qué existen. Si un cambio
tuyo las simplifica, el cambio está mal.

**4.1 · La plaza se reserva ANTES de cobrar.**
`StartLeadPurchase` bloquea la fila del lead (`SELECT … FOR UPDATE`), cuenta plazas vivas y
crea la compra en `reserved` con TTL de 30 min, y solo después pide la sesión de checkout.
*Por qué:* si el cap se validara al confirmar el pago, N profesionales podrían pagar a la
vez por un lead de 3 plazas y habría que reembolsar a los que sobran.
→ No muevas la validación del cap al webhook. No quites el `FOR UPDATE`.

**4.2 · Solo el webhook desbloquea el contacto.**
Volver de la pasarela al frontend no desbloquea nada. La confirmación llega firmada por
Stripe a `POST /api/v1/webhooks/stripe`.
→ Nunca marques una compra como pagada desde una petición del navegador.

**4.3 · El webhook es idempotente.**
`processed_payment_events` (clave primaria + `ON CONFLICT DO NOTHING`) es el cerrojo.
Stripe reenvía eventos; procesarlos dos veces cobraría dos plazas por una venta.
→ Cualquier manejador de eventos nuevo pasa por ese registro.

**4.4 · La PII del cliente vive en un tipo que no la contiene.**
`Lead.public_view()` devuelve `LeadPublicView`, que **no tiene campos** para nombre,
teléfono ni email. Los schemas del explorador solo aceptan ese tipo.
→ No añadas campos de contacto a `LeadPublicView` ni a `LeadPublicOut`. El único camino a
los datos reales es `Lead.contact_view(unlocked=True)`, y solo con compra `paid`.
→ Nunca registres PII en logs.

**4.5 · Sin consentimiento no hay lead orgánico.**
El dominio rechaza construir un `Lead` con `source=ORGANIC` y `consent=None`.
`lead_consents` guarda versión de política, IP y user-agent **tomados del servidor**, nunca
del cuerpo de la petición.
→ No aceptes IP ni user-agent como campos de entrada del API.

**4.6 · Una compra reembolsada sigue ocupando plaza.**
El dato personal ya se cedió al profesional. Para retirar un lead problemático se
deshabilita el lead completo, no se libera la plaza.

**4.7 · El reloj es un puerto.**
`created_at` y los TTL los decide `ClockPort`, no `datetime.now()` ni el `server_default`
de Postgres.
→ Prohibido `datetime.now()` / `datetime.utcnow()` en `app/domain/` y `app/application/`.

**4.8 · Los códigos de error son el contrato con el frontend.**
El backend devuelve `{code, message}`; el frontend traduce **por `code`**, ignorando el
`message` (que es para desarrolladores). Añadir un código exige tocar tres sitios:
`app/domain/exceptions/__init__.py`, `apps/web/messages/es.json` y `messages/en.json`.

**4.9 · El precio de un contacto lo pone el admin, no la categoría.**
`Category.suggested_lead_price` es la sugerencia; `Lead.price_override` es la decisión del
admin para ese contacto. Quién gana lo resuelve **solo** `Lead.sale_price(suggested=...)`,
y se cobra el importe congelado dentro del bloqueo de fila de `StartLeadPurchase`.
→ No leas `suggested_lead_price` para cobrar: pasa siempre por `Lead.sale_price()`.
→ Cambiar un precio no reescribe compras existentes: cada `Purchase` guarda su importe.
→ Cambiar el sugerido de un oficio no toca los leads con precio propio.
→ El precio solo se cambia por los endpoints `/admin/...`, con `AdminDep`.

---

## 5. Fronteras de la arquitectura

```
apps/api/app/
├── domain/          NÚCLEO — cero imports externos. Aquí viven las reglas.
├── application/     Puertos (interfaces) + casos de uso. Solo conoce el dominio.
└── infrastructure/  Adaptadores (SQLAlchemy, Stripe, Firebase, S3) + API HTTP.
```

- `domain/` y `application/` **no importan** `sqlalchemy`, `fastapi`, `stripe`,
  `firebase_admin`, `boto3` ni `pydantic`. Hoy hay 0 imports así; mantenlo en 0.
- mypy corre en **modo estricto** sobre esos dos paquetes. No añadas `# type: ignore`
  para salir del paso: si el tipo no cuadra, el diseño no cuadra.
- El único sitio que elige implementaciones concretas es el *composition root*:
  `app/infrastructure/api/dependencies.py`. No instancies adaptadores en otro lado.

Detalle de cómo añadir un caso de uso, un adaptador o un endpoint:
[`apps/api/AGENTS.md`](./apps/api/AGENTS.md).

---

## 6. Convenciones de código

**Idioma.** Comentarios, docstrings y mensajes de commit **en español**. Identificadores
(clases, funciones, variables, rutas, claves de i18n) **en inglés**. El código fuente es
**ASCII puro**: sin acentos ni eñes en comentarios ni docstrings (hoy: 0 archivos los
tienen). Las cadenas de cara al usuario viven en `apps/web/messages/*.json` y **sí deben
llevar acentos correctos** — ver §8.

**Comentarios.** Explican *por qué*, no *qué*. Un comentario que parafrasea la línea
siguiente es ruido; uno que explica una decisión no obvia evita que alguien la deshaga.
Imita la densidad del archivo que estés editando.

**Python.** ruff (línea 100, `target-version = py312`) + mypy. `uv run` para todo; no
invoques `python`, `pip` ni `pytest` directamente.

**TypeScript.** `strict` + `noUncheckedIndexedAccess`. `import type` para lo que solo se
usa como tipo (eslint lo exige). Alias `@/*` → `src/*`.

**Commits.** Cuerpo explicando el *por qué*, no el listado de archivos. Terminar con:
```
Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```
Rama distinta de `main` para cualquier cambio. No hagas `commit` ni `push` sin que te lo
pidan.

---

## 7. Tests

| Suite | Qué cubre | Requiere |
|---|---|---|
| `tests/unit/domain` | Reglas puras: cap, PII, dinero, transiciones | nada |
| `tests/unit/use_cases` | Orquestación con fakes in-memory de todos los puertos | nada |
| `tests/unit/test_stripe_adapter.py` | Adaptador **real** de Stripe (firma HMAC) | nada |
| `tests/integration` | Repositorios, PostGIS, índices, bloqueo de fila | Docker |
| `tests/api` | HTTP end-to-end con Firebase/Stripe/S3 falsos | Docker |
| `apps/web/tests` | Helpers, hooks y componentes (vitest + jsdom) | nada |

Tres reglas aprendidas a golpes:

1. **Los fakes deben modelar el viaje de red.** Los repositorios in-memory hacen
   `await _round_trip()` (un `asyncio.sleep(0)`) al principio de cada método. Sin ese punto
   de cesión al event loop, los tests de concurrencia pasan sin probar nada: las corrutinas
   corren de forma efectivamente atómica. No lo quites.
2. **Comprueba que tu test falla sin el arreglo.** El test de la carrera por la última
   plaza se validó desactivando el `FOR UPDATE` y confirmando que pasaban 2 compras en vez
   de 1. Un test de concurrencia que nunca se ha visto fallar no vale nada.
3. **Los fakes no detectan desajustes con los SDK reales.** Un bug de producción
   (`event.data.object` de Stripe es un `StripeObject`, no un `dict`) sobrevivió a toda la
   suite con pasarela falsa. De ahí `tests/unit/test_stripe_adapter.py`, que ejercita el
   adaptador real firmando eventos con HMAC — sin necesitar cuenta de Stripe. Si añades un
   adaptador externo, busca la forma de probarlo de verdad sin credenciales.

---

## 8. Trampas conocidas

**SQLAlchemy async**
- `session.get(Model, id, options=[selectinload(...)])` devuelve la instancia **ya cacheada
  en la sesión ignorando los `options`**; leer entonces una relación no cargada lanza
  `MissingGreenlet`. Usa `select(...).options(...).execution_options(populate_existing=True)`
  (patrón `_load_row` en los repositorios).
- Tras escribir, una columna geográfica **sigue siendo el WKT que asignaste** hasta que
  Postgres devuelve el WKB. Por eso `add()`/`update()` devuelven la entidad de dominio
  recibida en vez de re-mapear la fila. No lo "arregles" mapeando de vuelta.
- Los parámetros geográficos de `ST_DWithin`/`ST_Distance` se pasan con
  `to_geography()` (un `WKTElement`). Un string se enviaría como `VARCHAR` y Postgres
  rechazaría la consulta.

**Alembic** — `--autogenerate` produce migraciones que **hay que revisar a mano**: no añade
`import geoalchemy2` (aunque lo referencie), no crea la extensión PostGIS y no borra los
tipos `ENUM` en el `downgrade`. Compara con `alembic/versions/*_initial_schema.py` y
verifica siempre `upgrade` → `downgrade` → `upgrade` y `alembic check`.

**pnpm 10.34.5** — usa la versión fijada en `packageManager`. Los paquetes autorizados
a ejecutar scripts de instalación (`sharp`, `esbuild`…) se declaran en `allowBuilds`
dentro de `pnpm-workspace.yaml`.

**Next.js** — un componente cliente que use `useSearchParams()` necesita un `<Suspense>`
alrededor o el `build` falla al prerenderizar. Ver `publicar/page.tsx`.

**Acentos** — `apps/web/messages/*.json` es texto de cara al usuario y lleva acentos
correctos (284 claves por idioma). La regla de ASCII puro aplica **solo al código fuente**.
Lo mismo vale para `apps/api/data/categories.csv`: los nombres de oficio se muestran en la
landing y en el formulario.

---

## 9. Qué NO hacer

- No cambies los puertos 8010/3010 a 8000/3000.
- No metas lógica de negocio en endpoints, componentes React o repositorios: va al dominio
  o a un caso de uso.
- No añadas `# type: ignore` ni `any` para silenciar el tipador del núcleo.
- No incrustes cadenas de UI en los componentes: van a `messages/*.json`, en ambos idiomas.
- No commitees `.env`, service accounts de Firebase ni claves de Stripe.
- No borres ni relajes un test para que pase el pipeline. Si un test estorba, di por qué.
- No inventes datos: si no puedes verificar algo (p. ej. un pago real de Stripe sin clave),
  dilo explícitamente en tu informe en vez de dar por hecho que funciona.
