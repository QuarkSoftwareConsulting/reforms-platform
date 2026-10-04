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
profesional paga por desbloquear su contacto. **Para comprar necesita la recarga mensual al
día** (sin ella puede ver solicitudes, pero no comprarlas); su importe lo fija el admin y
se abona como saldo para pagar contactos (§4.10). **El precio de cada contacto lo decide el admin**: la categoría solo
aporta un precio sugerido (§4.9). **Cada solicitud se vende a un máximo de 5
profesionales** (los leads anteriores a la Etapa 1 conservan sus 3). Esa regla, y la protección de los datos personales del cliente, son el
producto — no un detalle de implementación.

Monorepo: `apps/api` (FastAPI hexagonal, Python 3.13 + uv) y `apps/web` (Next.js 15,
TypeScript + pnpm). Estado y alcance de la fase actual: ver `README.md`.

**Trabajo en curso (Etapa 1):** [`docs/plan-etapa-1.md`](./docs/plan-etapa-1.md) recoge las
reglas acordadas con el cliente, qué fase está hecha y qué falta. Léelo antes de tocar
pagos, acceso o validación de profesionales, y actualízalo al cerrar una fase.

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

| Objetivo                                           | Comando                                                                  |
| -------------------------------------------------- | ------------------------------------------------------------------------ |
| Todo el lint (ruff + mypy strict + eslint + tsc)   | `pnpm lint`                                                              |
| Todos los tests (584 back + 132 front)             | `pnpm test`                                                              |
| Backend rápido, **sin Docker** (481 tests)         | `cd apps/api && uv run pytest -m "not integration"`                      |
| Backend completo (requiere `pnpm infra:up`)        | `pnpm api:test`                                                          |
| Un solo test de backend                            | `cd apps/api && uv run pytest tests/unit/domain/test_lead.py -k capping` |
| Frontend en watch                                  | `pnpm --filter web test:watch`                                           |
| ¿Modelos y esquema divergen?                       | `cd apps/api && uv run alembic check`                                    |
| Flujo de compra end-to-end contra servicios reales | `pnpm verify:flow`                                                       |
| Arreglar lo que `--autogenerate` no hace           | `cd apps/api && uv run python -m scripts.fix_migration`                  |
| Recrear la BD desde cero                           | `pnpm infra:reset && pnpm api:migrate && pnpm api:seed`                  |

**Antes de dar por terminada cualquier tarea: `pnpm lint && pnpm test` en verde.** No
declares algo hecho si no has ejecutado esto.

Si el cambio toca leads, compras, pagos o autenticación, además: `pnpm verify:flow`. Cubre
lo que los fakes no pueden ver — ver §7.

### Procedimientos documentados

Tres tareas recurrentes tienen su procedimiento escrito paso a paso. En Claude Code son
_skills_ que se invocan solas; con cualquier otra herramienta, **son documentación: ábrela y
síguela**.

| Procedimiento                | Cuándo                                                  | Archivo                                          |
| ---------------------------- | ------------------------------------------------------- | ------------------------------------------------ |
| Verificar el flujo de compra | Antes de cerrar un cambio en leads, pagos o auth        | `.claude/skills/verificar-flujo-compra/SKILL.md` |
| Nueva migración              | Al cambiar un modelo ORM, o ante `UndefinedColumnError` | `.claude/skills/nueva-migracion/SKILL.md`        |
| Nuevo caso de uso            | Al añadir funcionalidad de backend o un endpoint        | `.claude/skills/nuevo-caso-de-uso/SKILL.md`      |

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
_Por qué:_ si el cap se validara al confirmar el pago, N profesionales podrían pagar a la
vez por un lead de 5 plazas y habría que reembolsar a los que sobran.
→ No muevas la validación del cap al webhook. No quites el `FOR UPDATE`.

**4.2 · Solo dinero confirmado por el webhook desbloquea el contacto.**
Volver de la pasarela al frontend no desbloquea nada. La confirmación llega firmada por
Stripe a `POST /api/v1/webhooks/stripe`. Una compra pagada **con saldo** pasa a `paid` sin
checkout porque ese dinero ya lo confirmó el webhook al cobrar la recarga (`invoice.paid`).
→ Nunca marques una compra como pagada desde una petición del navegador.
→ Nunca abones saldo ni actives una cuenta fuera del webhook (ni al volver del checkout).

**4.3 · El webhook es idempotente.**
`processed_payment_events` (clave primaria + `ON CONFLICT DO NOTHING`) es el cerrojo.
Stripe reenvía eventos; procesarlos dos veces cobraría dos plazas por una venta.
→ Cualquier manejador de eventos nuevo pasa por ese registro.

**4.4 · La PII del cliente vive en un tipo que no la contiene.**
`Lead.public_view()` devuelve `LeadPublicView`, que **no tiene campos** para el nombre
completo, el teléfono ni el email. Los schemas del explorador solo aceptan ese tipo.
Antes de pagar solo se ven el **nombre de pila** y el **CP completo** (lo pidió el
cliente, Etapa 1), y solo si `ConsentRecord.allows_public_preview`: los consentimientos
anteriores a la política `2026-09-v2` no lo cubren y sus leads siguen sin nombre y con el
prefijo del CP.
→ No añadas campos de contacto a `LeadPublicView` ni a `LeadPublicOut`. El único camino a
los datos reales es `Lead.contact_view(unlocked=True)`, y solo con compra `paid`.
→ Mostrar un dato nuevo antes de pagar exige cambiar la política de privacidad, subir
`PRIVACY_POLICY_VERSION` y condicionarlo al consentimiento.
→ `allows_public_preview` sale de la versión aceptada (`policy_covers_public_preview`), no
de que el lead sea nuevo: una pestaña antigua o un lead del admin con la política anterior
no la cubren. Al subir la versión, decláralo en `PUBLIC_PREVIEW_POLICY_VERSIONS`;
`Settings` no arranca si la vigente falta.
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

**4.10 · Sin recarga mensual al día no se compra; el saldo se gasta una sola vez.**
`ProfessionalAccount` guarda el estado de la suscripción y el saldo. Una cuenta inactiva
**puede ver** solicitudes (listado y detalle, sin datos de contacto), pero
`StartLeadPurchase` la rechaza con `402 SUBSCRIPTION_REQUIRED`
(`account_access.require_active_account`). Así lo fijó el cliente (documento, F02).
→ No bloquees el listado ni el detalle por la recarga: ya se decidió y se descartó.
El saldo se gasta dentro del mismo bloqueo que la plaza, con la cuenta en `FOR UPDATE`
**después** del lead (siempre ese orden, para no interbloquear). Cada movimiento va a
`credit_entries`, append-only, con `UNIQUE (kind, source_ref)` como segundo cerrojo tras
`processed_payment_events`.
→ Solo `invoice.paid` activa una cuenta. Con SEPA, Stripe marca la suscripción `active`
mientras el adeudo se procesa: `sync_subscription` no la activa por eso.
→ Todo movimiento de saldo pasa por `CreditLedgerService` (compra, caducidad, webhook, job,
ajuste del admin). Si una reserva con saldo caduca o falla, se devuelve con `SPEND_REVERSAL`.
→ Una compra reembolsada no devuelve saldo sola (§4.6): lo decide el admin con un ajuste.
→ El importe lo fija el admin (`PUT /admin/subscription-price`), que crea un precio nuevo en
Stripe y una fila en `subscription_prices` (append-only; vige la más reciente). Solo afecta
a las suscripciones nuevas: quien ya paga conserva su importe. Hasta que el admin lo fije,
rige `STRIPE_TOPUP_PRICE_ID` + `SUBSCRIPTION_TOPUP_CENTS`.

**4.11 · Solo se publica dentro de la zona de cobertura.**
En la Etapa 1, la Comunidad de Madrid (CP 28xxx). `CreateLead` lo comprueba con
`ServiceArea` **antes** de consultar el catálogo de CP, para que un CP real de fuera
responda `POSTAL_CODE_NOT_COVERED` y no `UNKNOWN_POSTAL_CODE`. La zona es configuración
(`COVERED_POSTAL_PREFIXES`), no código.
→ Si falta un CP 28xxx real en `postal_codes_es.csv`, regenéralo con
`scripts/import_postal_codes.py`; no quites la comprobación.

**4.12 · El móvil del cliente se verifica por SMS antes de publicar.**
El cliente publica como invitado: el SMS es lo único que prueba que el teléfono que
vendemos existe y es suyo. Lo hace el puerto `PhoneVerificationPort`; el proveedor
genera, caduca y limita los códigos, así que no guardamos ninguno. Con
`PHONE_VERIFICATION_BACKEND=disabled` (hoy, sin proveedor) se publica sin código.
→ El código se confirma **lo último**, después de validar todo lo demás: se consume al
confirmarlo y un error en otro campo no debe obligar a pedir otro SMS.
→ `console` escribe el código en el log: `Settings` lo prohíbe fuera de development y test.

**4.13 · Compra solo quien tiene el alta aprobada; un rechazo reembolsa y cancela.**
`Professional.verification_status`: `incomplete` → `pending` (el profesional envía el alta)
→ `approved` / `rejected` (el admin). Incompleto o en revisión **ve** solicitudes pero no
compra (`403 PROFESSIONAL_NOT_APPROVED`, comprobado antes que la recarga); rechazado no ve
ni compra. Cada transición deja un `VerificationEvent` (append-only, con el admin que la
hizo). Enviado el alta, tipo, razón social, NIF y documentos quedan fijos.
→ `RejectProfessional` llama a la pasarela **antes** de guardar, con operaciones
idempotentes (clave de idempotencia en el reembolso; cancelar dos veces no falla): si la
pasarela falla no se guarda nada y el admin reintenta. Lo que impida rechazar (estado,
motivo) se comprueba antes, con `assert_can_reject`. Pasadas 24 h Stripe olvida la clave
de idempotencia: un cargo ya reembolsado cuenta como hecho. El saldo del primer cobro se retira
con `VERIFICATION_REFUND` sobre la misma factura.
→ Quien escribe el perfil (enviar, aprobar, rechazar, guardar el perfil, documentos) lo
carga con `get_for_update` dentro de la transacción: `update` reescribe el perfil entero,
estado del alta incluido. El rechazo mantiene el bloqueo durante las llamadas a Stripe.
Orden de bloqueo: **profesional antes que cuenta**.
→ Con la recarga en `pending` (adeudo SEPA en proceso) no se rechaza
(`409 REJECTION_AWAITING_PAYMENT`): ese adeudo no se puede anular y se confirmaría después,
abonando saldo a un rechazado sin reembolso.
→ Los documentos de alta (DNI, modelos de Hacienda) van al **bucket privado**
(`S3_PRIVATE_BUCKET` / `GCS_PRIVATE_BUCKET`, nunca el público) y solo salen con URLs
firmadas de corta duración en el expediente del admin. El perfil propio no las incluye.
→ Las claves de archivo llevan el id del profesional en el prefijo y se comprueban al
adjuntarlas: nadie adjunta un archivo subido por otro.

**4.14 · El rol vive en la base de datos; el claim de Firebase solo crea el primer admin.**
Hay dos roles con cuenta, `professional` y `admin` (`UserRole`). El **cliente no tiene
cuenta**: publica como invitado (§4.12) y existe solo como `ClientContact` dentro del
`Lead`; no lo añadas a `UserRole`. El admin da o quita el rol desde el panel
(`PUT /admin/users/{id}/role`, `ChangeUserRole`) y surte efecto en la siguiente petición,
sin esperar a que caduque el token. Cada cambio deja un `UserRoleEvent` (append-only, con el
admin que lo hizo, o `None` si fue la CLI).
→ `SyncUserFromIdentity` lee el claim `admin` **solo al crear** la fila `users`. Si volviera
a sincronizarlo en cada petición, un admin degradado recuperaría el acceso con su claim.
→ Nadie cambia su propio rol (`409 CANNOT_CHANGE_OWN_ROLE`) y no se degrada al último admin
(`409 LAST_ADMIN`). Para eso, quien degrada a un admin bloquea **todas** las filas de admin
(`lock_admins`, `FOR UPDATE` en orden de id) antes que la fila objetivo: bloqueando solo la
objetivo, dos admins degradándose el uno al otro dejarían cero.
→ `scripts/manage_admin.py` escribe en la BD con las mismas reglas: sirve para el primer
admin y para recuperar el acceso. No toca Firebase.

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
- El único sitio que elige implementaciones concretas es el _composition root_:
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

**Comentarios.** Explican _por qué_, no _qué_. Un comentario que parafrasea la línea
siguiente es ruido; uno que explica una decisión no obvia evita que alguien la deshaga.
Imita la densidad del archivo que estés editando.

**Python.** ruff (línea 100, `target-version = py312`) + mypy. `uv run` para todo; no
invoques `python`, `pip` ni `pytest` directamente.

**TypeScript.** `strict` + `noUncheckedIndexedAccess`. `import type` para lo que solo se
usa como tipo (eslint lo exige). Alias `@/*` → `src/*`.

**Commits.** Cuerpo explicando el _por qué_, no el listado de archivos. Sin línea
`Co-Authored-By`. Rama distinta de `main` para cualquier cambio. No hagas `commit` ni `push` sin que te lo
pidan.

---

## 7. Tests

| Suite                               | Qué cubre                                             | Requiere |
| ----------------------------------- | ----------------------------------------------------- | -------- |
| `tests/unit/domain`                 | Reglas puras: cap, PII, dinero, transiciones          | nada     |
| `tests/unit/use_cases`              | Orquestación con fakes in-memory de todos los puertos | nada     |
| `tests/unit/test_stripe_adapter.py` | Adaptador **real** de Stripe (firma HMAC)             | nada     |
| `tests/integration`                 | Repositorios, PostGIS, índices, bloqueo de fila       | Docker   |
| `tests/api`                         | HTTP end-to-end con Firebase/Stripe/S3 falsos         | Docker   |
| `apps/web/tests`                    | Helpers, hooks y componentes (vitest + jsdom)         | nada     |

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
tipos `ENUM` en el `downgrade`. Tampoco crea el tipo `ENUM` de una columna nueva
añadida con `add_column` (sí lo hace `create_table`): créalo antes con
`postgresql.ENUM(..., create_type=False).create(op.get_bind(), checkfirst=True)`, como en
`*_catalogo_de_servicios_y_datos_del_.py`. Un valor nuevo en un `ENUM` existente tampoco lo
detecta: `ALTER TYPE ... ADD VALUE IF NOT EXISTS` a mano (ver `*_validacion_del_profesional.py`).
Compara con `alembic/versions/*_initial_schema.py` y
verifica siempre `upgrade` → `downgrade` → `upgrade` y `alembic check`.

**pnpm 10.34.5** — usa la versión fijada en `packageManager`. Los paquetes autorizados
a ejecutar scripts de instalación (`sharp`, `esbuild`…) se declaran en `allowBuilds`
dentro de `pnpm-workspace.yaml`.

**Next.js** — un componente cliente que use `useSearchParams()` necesita un `<Suspense>`
alrededor o el `build` falla al prerenderizar. Ver `publicar/page.tsx`.

**Acentos** — `apps/web/messages/*.json` es texto de cara al usuario y lleva acentos
correctos (535 claves por idioma). La regla de ASCII puro aplica **solo al código fuente**.
Lo mismo vale para `apps/api/data/categories.csv`, `services.csv`: los nombres de oficio se muestran en la
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
