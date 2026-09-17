# Reforma Hub

Marketplace **pay-per-lead** de oficios y reformas. Los clientes publican gratis lo que
necesitan (carpintería, fontanería, pintura…); los profesionales navegan las solicitudes
de su zona y **pagan por desbloquear el contacto** del cliente. Cada solicitud se vende a
un máximo de 3 profesionales, y **el precio de cada contacto lo fija el administrador**
(la categoría solo aporta un precio sugerido).

- **Fase 1 (esta):** flujo completo cliente → profesional → pago → contacto desbloqueado.
- **Fase 2:** panel de administración, ingesta manual de leads, emails transaccionales,
  páginas SEO por oficio + ciudad, wallet prepago.

Documentos de producto en [`docs/`](./docs).

> Si trabajas con un agente de IA (Claude Code, Codex, Cursor, Copilot), las convenciones e
> invariantes del proyecto están en [`AGENTS.md`](./AGENTS.md), con archivos más específicos
> en `apps/api/` y `apps/web/`.

---

## Arquitectura

| Capa | Tecnología | Por qué |
|---|---|---|
| Frontend | Next.js 15 (App Router) + TypeScript | SSR/SSG para el SEO local, i18n ES/EN por segmento de URL |
| Backend | FastAPI + arquitectura hexagonal | Dominio aislado de framework, ORM y pasarelas |
| Base de datos | PostgreSQL 16 + **PostGIS** | Filtrado por radio real en km con índices GIST |
| Autenticación | **Firebase Auth** | El backend verifica ID tokens con `firebase-admin` detrás de un puerto |
| Pagos | **Stripe Checkout** | SCA/3D Secure nativo y multidivisa |
| Almacenamiento | S3 compatible (MinIO en dev, Cloudflare R2 en prod) | Subida directa del navegador con URL prefirmada |

```
apps/
├── api/          FastAPI — domain / application (puertos + casos de uso) / infrastructure
└── web/          Next.js — app / components / hooks / helpers / services / types
infra/            docker-compose (PostGIS, MinIO) + config del emulador de Firebase
docs/             PRD y documento de arquitectura
```

El **dominio** (`apps/api/app/domain/`) no importa nada externo: ni SQLAlchemy, ni FastAPI,
ni Stripe. Los casos de uso hablan solo con puertos (`app/application/ports/`), y el
*composition root* (`app/infrastructure/api/dependencies.py`) es el único sitio donde se
elige la implementación concreta de cada uno.

---

## Arrancar en local

Requisitos: Docker, Node 22.22.2 + pnpm 10.34.5, Python ≥ 3.12 + [uv](https://docs.astral.sh/uv/).
Se recomienda ejecutar `nvm use` desde la raíz para seleccionar la versión de `.nvmrc`.

```bash
# 1. Infraestructura (PostGIS en :5433, BD de test en :5434, MinIO en :9000)
pnpm infra:up

# 2. Variables de entorno
cp .env.example apps/api/.env          # sección BACKEND
cp .env.example apps/web/.env.local    # sección FRONTEND

# 3. Backend
cd apps/api && uv sync
uv run alembic upgrade head            # crea el esquema (incluye CREATE EXTENSION postgis)
uv run python -m scripts.seed          # 12 oficios + catálogo de códigos postales de España
cd ../.. && pnpm api:dev               # http://localhost:8010  (docs en /docs)

# 4. Emulador de Firebase Auth (en otra terminal, no necesita service account)
npx -y firebase-tools emulators:start --only auth --project reforma-hub-dev --config infra/firebase.json

# 5. Frontend
pnpm web:dev                           # http://localhost:3010
```

> Los puertos son 8010 (API) y 3010 (web) para no chocar con otros proyectos que
> suelen ocupar 8000 y 3000.

### Pagos en local

`STRIPE_SECRET_KEY` y `STRIPE_WEBHOOK_SECRET` son obligatorias para completar una compra.
Con claves de test de Stripe:

```bash
stripe listen --forward-to localhost:8010/api/v1/webhooks/stripe
# copia el whsec_... que imprime a STRIPE_WEBHOOK_SECRET en apps/api/.env
```

Sin clave configurada, `POST /leads/{id}/purchase` responde `503 PAYMENT_GATEWAY_ERROR` y
**libera la plaza reservada** en el acto, para que un fallo de infraestructura no consuma
una de las 3 plazas del lead.

---

## Comandos

```bash
pnpm test          # backend (pytest) + frontend (vitest)
pnpm lint          # ruff + mypy strict + eslint + tsc
pnpm infra:reset   # recrea la BD desde cero (borra los datos)

cd apps/api
uv run pytest -m "not integration"          # solo unitarios, sin Docker
uv run alembic revision --autogenerate -m "..."
uv run alembic check                        # ¿el esquema y los modelos divergen?
uv run python -m app.jobs.release_reservations  # libera reservas caducadas (cron)
```

Los tests de integración y de API usan la base `db-test` (`:5434`, datos en tmpfs). Si no
está levantada se **omiten** con un mensaje indicando el comando para arrancarla.

---

## Decisiones que conviene conocer antes de tocar el código

**La reserva de plaza precede al pago.** `POST /leads/{id}/purchase` bloquea la fila del
lead (`SELECT … FOR UPDATE`), cuenta las plazas vivas y crea la compra en estado
`reserved` con un TTL de 30 min *antes* de pedir la sesión de checkout. Si el cap se
validara solo al confirmar el pago, N profesionales podrían pagar a la vez por un lead de
3 plazas y habría que reembolsar a los que sobran. El TTL evita que un checkout abandonado
bloquee el lead para siempre; lo limpian el evento `checkout.session.expired` y el job
`release_reservations`.

**El contacto se desbloquea solo con el webhook.** Volver de la pasarela al frontend no
desbloquea nada: la confirmación tiene que venir firmada por Stripe. `processed_payment_events`
hace de cerrojo de idempotencia (clave primaria + `ON CONFLICT DO NOTHING`), así que
reenviar un evento no incrementa el contador dos veces.

**La PII del cliente vive en un tipo aparte.** `Lead.public_view()` devuelve un
`LeadPublicView` que *no tiene campos* para nombre, teléfono ni email, y los schemas del
explorador solo aceptan ese tipo. Filtrar datos de contacto por descuido requeriría
cambiar el tipo, no solo olvidar un `del`.

**El consentimiento RGPD es un registro auditable.** `lead_consents` guarda versión de
política, IP y user-agent tomados del servidor (nunca del cuerpo de la petición), y el
dominio rechaza construir un lead orgánico sin él.

**El precio es una decisión por contacto, no una propiedad del oficio.** Cada categoría
tiene un precio *sugerido* (`categories.suggested_lead_price_cents`), y el admin puede
fijar otro para un lead concreto (`leads.price_override_cents`) desde
`PUT /api/v1/admin/leads/{id}/price`. Quién gana lo resuelve un solo método del dominio,
`Lead.sale_price(suggested=...)`, y el importe se congela dentro del bloqueo de fila de la
reserva: cambiar el precio después no altera compras ya creadas ni la sesión de checkout
que se emitió. Subir el precio sugerido de un oficio tampoco toca los leads que ya tienen
precio propio. La UI de administración llega en la Fase 2; de momento los endpoints se
usan desde `/docs` o con un cliente HTTP.

**Una compra reembolsada sigue ocupando plaza.** El dato personal ya se cedió al
profesional, así que la plaza no se reutiliza; para retirar un lead problemático se
deshabilita el lead completo.

**El reloj es un puerto.** `created_at` y los TTL los decide `ClockPort`, no el
`server_default` de Postgres, para que los tests de caducidad sean deterministas.

---

## Estado de la verificación

Comprobado end-to-end en local contra Postgres+PostGIS real, el emulador de Firebase Auth
y el adaptador real de Stripe (webhook firmado con HMAC): publicación con consentimiento
auditado, explorador filtrando por radio sin filtrar PII, confirmación por webhook,
idempotencia ante reenvíos, agotamiento del lead a las 3 compras y `409 LEAD_CAP_REACHED`
al cuarto profesional.

**Lo único no ejercitado contra el servicio real es la sesión de Stripe Checkout**, que
requiere una clave de test de Stripe. El camino está cubierto por los tests con pasarela
falsa y por los tests del adaptador real de webhooks.
