---
name: verificar-flujo-compra
description: Verifica de punta a punta el flujo de compra de un contacto en Reforma Hub contra los servicios reales en local (Postgres+PostGIS, emulador de Firebase Auth, adaptador real de Stripe). Usar antes de dar por terminado cualquier cambio que toque leads, compras, pagos, webhooks, el cap de 3 profesionales, la autenticacion o la exposicion de datos de contacto del cliente; tambien antes de abrir un PR o cuando el usuario pida comprobar que "el flujo sigue funcionando".
---

# Verificar el flujo de compra end-to-end

`pnpm test` cubre el sistema con fakes. Esta verificacion cubre lo que los fakes **no
pueden** ver: los desajustes con los SDK reales. El bug de produccion mas grave de este
proyecto (`event.data.object` de Stripe es un `StripeObject`, no un `dict`) paso los 222
tests unitarios y solo aparecio aqui.

## 1 · Levantar el entorno

Comprueba primero qué falta en vez de arrancarlo todo a ciegas:

```bash
docker ps --format '{{.Names}}' | grep reforma        # db, db-test, minio
curl -s localhost:8010/health                         # API
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9099/   # emulador Auth
```

Lo que falte:

```bash
pnpm infra:up                                         # contenedores
pnpm api:migrate && pnpm api:seed                     # esquema + catalogo
pnpm api:dev                                          # API en :8010
npx -y firebase-tools emulators:start --only auth \
  --project reforma-hub-dev --config infra/firebase.json
```

Arranca el API y el emulador **en segundo plano** (`run_in_background`), no en primer plano:
bloquean la terminal. Espera a que `/health` devuelva `database: true` antes de seguir.

## 2 · Ejecutar

```bash
pnpm verify:flow                # 28 comprobaciones
pnpm verify:flow -- --verbose   # muestra cada peticion y respuesta
pnpm verify:flow -- --keep      # conserva los datos de prueba para inspeccionarlos
```

El script (`apps/api/scripts/verify_purchase_flow.py`) crea sus propios datos, los limpia
al terminar y sale con codigo 1 en el primer fallo. Es idempotente: puedes ejecutarlo
tantas veces como quieras.

## 3 · Qué comprueba

| Paso | Invariante |
|---|---|
| 1 | El cliente publica sin cuenta; sin consentimiento se rechaza (`CONSENT_REQUIRED`) |
| 2 | `lead_consents` guarda politica, IP y user-agent **tomados del servidor** |
| 3 | El backend verifica un ID token real de Firebase |
| 4 | El explorador **no** expone nombre, telefono ni email; el detalle sigue bloqueado |
| 5 | Si la pasarela falla: 503 y la plaza se libera al instante |
| 6 | Firma forjada → 401. Solo el webhook firmado desbloquea |
| 7 | Reenviar el mismo evento no incrementa el contador dos veces |
| 8 | Quien pago ve el contacto completo y consume una plaza |
| 9 | La compra de un profesional **no** desbloquea para otro |
| 10 | A las 3 ventas el lead se agota: el cuarto recibe `409 LEAD_CAP_REACHED` |
| 11 | Solo el admin fija precios; el override manda sobre el sugerido y se puede borrar |

## 4 · Interpretar el resultado

**Todo OK con 1 `SKIP`** — es lo normal sin clave de Stripe. El skip es la creacion de la
sesion de Checkout; el resto del camino de pago sí se verifica firmando el webhook con
HMAC. **Reporta el skip explicitamente al usuario**, no lo presentes como cobertura total.

Para cubrirlo tambien: pon una clave de test (`sk_test_...`) en `STRIPE_SECRET_KEY` de
`apps/api/.env` y vuelve a ejecutar. El script la detecta y pasa por Stripe de verdad.

**Un `FALLO`** — el mensaje dice qué invariante se rompio y con qué cuerpo de respuesta.
Antes de tocar el script, descarta estas causas por orden:

1. **Proceso caducado.** Python cachea modulos: si editaste código con el API arrancado,
   reinicia uvicorn. Un `500` inexplicable casi siempre es esto.
2. **Esquema desincronizado.** Un error `UndefinedColumnError` significa que cambiaste un
   modelo ORM sin migracion → usa la skill `nueva-migracion`.
3. **Semillas ausentes.** "No hay categorias" → `pnpm api:seed`.

Solo cuando ninguna aplica, el fallo es real. **Nunca relajes una assertion para que el
script pase**: cada una corresponde a un invariante documentado en `AGENTS.md`. Si una
sobra, di por qué.

## 5 · Al ampliarlo

Si añades un paso al flujo de negocio, añade su comprobacion aqui. Dos reglas:

- **Registra profesionales con el helper `register_professional`**, que crea cuenta en el
  emulador y perfil, y devuelve token e id. El indice unico parcial
  `uq_lead_purchases_active` impide que un mismo profesional ocupe dos plazas del mismo
  lead, asi que cada plaza necesita un profesional distinto.
- **Verifica contra el API, no contra SQL**, salvo cuando no haya endpoint (el registro de
  consentimiento, por ejemplo). Afirmar sobre la respuesta HTTP prueba el contrato publico;
  afirmar sobre la tabla prueba tu propio `INSERT`.
