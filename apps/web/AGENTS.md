# AGENTS.md — Frontend (`apps/web`)

Reglas específicas del frontend. Complementan (y en caso de conflicto, tienen prioridad
sobre) el [`AGENTS.md` raíz](../../AGENTS.md), que contiene los invariantes de negocio.
Léelo antes.

Next.js 15 (App Router) + React 19 + TypeScript strict, gestionado con **pnpm**.

---

## Mapa de capas

```
src/
├── app/[locale]/       Rutas. Server Components por defecto.
├── components/
│   ├── ui/             Presentación pura: Button, Field, Alert, Card. Sin dominio.
│   └── features/       Componentes de dominio: LeadCard, LeadWizard, PurchaseButton…
├── hooks/              Estado, efectos y llamadas al API. Aquí va la lógica de interfaz.
├── helpers/            Funciones puras: currency, date, distance, validators, cn.
├── services/           Clientes HTTP. El único sitio que conoce las rutas del API.
├── types/api.ts        DTOs espejo de los schemas Pydantic del backend.
├── lib/firebase.ts     El único módulo que importa `firebase/*`.
└── i18n/               Locales, rutas por idioma y config de next-intl.
```

**Dónde va cada cosa:**

| Si es… | va en… | y no debe… |
|---|---|---|
| Una URL del API | `services/` | aparecer en un componente o hook |
| Estado, efecto o llamada | `hooks/` | vivir dentro del JSX de un componente |
| Cálculo o formateo sin React | `helpers/` | importar nada de `react` |
| Presentación sin dominio | `components/ui/` | conocer `Lead`, `Purchase`… |
| Presentación con dominio | `components/features/` | hacer `fetch` directamente |

Un componente que hace `fetch`, o un helper que importa React, están en la capa
equivocada. Los componentes de `ui/` deben poder copiarse a otro proyecto sin arrastrar
nada del negocio.

---

## Server vs Client Components

Por defecto, **Server Component**. `"use client"` solo si el componente necesita estado,
efectos, eventos del navegador o contexto.

- Lo que debe indexar Google (landing, catálogo de oficios) se renderiza en servidor con
  datos reales del API. No lo conviertas en carga desde cliente: es el SEO local el que
  justifica Next.js en este proyecto.
- Las zonas privadas (`proyectos`, `mis-contactos`, `perfil`) llevan
  `robots: { index: false }` en su `generateMetadata`.
- **`useSearchParams()` en un componente cliente exige un `<Suspense>` alrededor**, o
  `next build` falla al prerenderizar. Ejemplo en `app/[locale]/publicar/page.tsx`.
- En páginas de `[locale]`, llama a `setRequestLocale(locale)` antes de usar traducciones,
  o pierdes el renderizado estático.

---

## Autenticación

`AuthProvider` (`hooks/useAuth.tsx`) envuelve Firebase y es la **única** puerta de entrada:
ningún otro módulo importa `firebase/auth`. Cambiar de proveedor de identidad debería tocar
solo `lib/firebase.ts` y ese hook.

- El token no se copia a ningún sitio: `services/api.ts` lo pide justo antes de cada
  petición mediante `setTokenProvider`, y así nunca envía uno caducado. Ante un 401
  reintenta **una vez** forzando renovación.
- Se usa `onIdTokenChanged`, no `onAuthStateChanged`, para enterarse también de las
  renovaciones de token.
- `<AuthGate>` es **comodidad de UX, no seguridad**. La autorización real la aplica el
  backend en cada petición. No muevas ninguna comprobación de permisos al cliente.

---

## i18n: no negociable

**Cero cadenas de UI incrustadas en componentes.** Todo texto visible sale de
`messages/es.json` / `messages/en.json`.

- Los dos archivos deben tener **exactamente las mismas claves** (hoy: 284 cada uno).
  Comprobación rápida:

  ```bash
  node -e "
  const fs=require('fs'), keys=(o,p='')=>Object.entries(o).flatMap(([k,v])=>
    typeof v==='object'&&v!==null?keys(v,p+k+'.'):[p+k]);
  const es=new Set(keys(JSON.parse(fs.readFileSync('messages/es.json'))));
  const en=new Set(keys(JSON.parse(fs.readFileSync('messages/en.json'))));
  const falta=[...es].filter(k=>!en.has(k)), sobra=[...en].filter(k=>!es.has(k));
  console.log({es:es.size, en:en.size, falta, sobra});"
  ```

- Los errores del API se traducen **por `code`**, con `useApiError()`. El `message` que
  manda el backend es para desarrolladores: no lo muestres al usuario. Un código
  desconocido cae en `errors.generic` — nunca se filtra texto crudo del backend.
- Los mensajes de validación son **claves**, no frases: los esquemas Zod de
  `helpers/validators.ts` devuelven `"consentRequired"` y el componente hace
  `tValidation(key)`.
- Añadir un idioma: `i18n/routing.ts` (`locales`), un `messages/<lang>.json` completo y los
  tags de `Intl` en `helpers/currency.ts` y `helpers/date.ts`.

> Las cadenas de `es.json` llevan acentos correctos desde la implantación del sistema de
> diseño. El ASCII solo aplica al código fuente; el texto de cara al usuario, no. Si añades
> una clave, acentúala.

---

## Validación

Los esquemas de `helpers/validators.ts` **duplican a propósito** las reglas del backend:
dan respuesta inmediata al usuario, pero el backend nunca confía en ellos y revalida. Si
cambias una regla de negocio, cámbiala en los dos lados o el formulario aceptará algo que
el API rechazará.

`validatePhotos()` filtra en cliente lo que el backend rechazaría, para no gastar una
subida al bucket en un archivo inválido.

---

## Tests

```bash
pnpm test              # vitest, 61 tests
pnpm test:watch
pnpm lint              # eslint + tsc --noEmit
```

- `tests/render.tsx` envuelve el árbol con `NextIntlClientProvider` y los mensajes reales.
  **Afirma contra `messages.*` importado, no contra literales**: así un cambio de copy no
  rompe el test, pero borrar una clave sí.
- Mockea en la frontera de `services/`, no `fetch`. El test comprueba el comportamiento del
  hook o del componente, no el transporte.
- Consulta por rol y etiqueta accesible (`getByRole`, `getByLabelText`), no por clase CSS.
- Si un texto está partido entre nodos (p. ej. "Paso 1 de 3 · Qué trabajo necesitas"), usa
  un matcher de regex; no reestructures el JSX para acomodar el test.
- Las etiquetas de campo llevan el asterisco de obligatorio pegado detrás, así que
  `getByLabelText` necesita un regex. `tests/LeadWizard.test.tsx` lo construye con el helper
  `label(messages.publish.<clave>)`: afirma contra el mensaje, no contra el literal.
- Prioridad en lo que hay que probar: que **no se pueda enviar el formulario sin
  consentimiento**, que la tarjeta del explorador **no renderice PII**, y que un doble click
  en "desbloquear" **no cree dos reservas** (`useLeadPurchase` mantiene `pending` tras una
  redirección correcta, a propósito).

---

## Estilos

Tailwind con el sistema de diseño **«Voy a Reformar»**
(`design_handoff_voyareformar/README.md` es la especificación).

- Los hex viven **solo** en el bloque `:root` de `src/app/globals.css`, copia de
  `design_handoff_voyareformar/tokens.css`. `tailwind.config.ts` les pone nombre semántico:
  `brand{,-hover,-soft}`, `accent{,-hover,-disabled}`, `ink`, `page`, `surface`, `line`,
  `line-strong`, `divider`, `secondary`, `muted`, `disabled{,-soft}`, `danger{,-bg}`.
  **No hay escala numérica** (`brand-600` ya no existe) y no se escriben hex en componentes.
- Escalas propias: tamaños `display · h1 · h2 · card-title · body · help · label`, radios
  `tag 6 · control 10 · option 12 · card 14 · panel 18`, anchos `max-w-shell` (1280) y
  `max-w-form` (980) vía `<Container>`.
- Reglas del sistema que no son gusto personal: **un solo botón primario por vista**, el
  precio del contacto siempre visible antes de pagar, texto gris tinta sobre el amarillo
  (nunca blanco: no cumple AA), sin degradados y **sin sombra en tarjetas de listado** — la
  elevación se reserva a menús y modales.
- Primitivos en `components/ui/`: `Button`, `Field`, `Card`/`Panel`/`Tag`/`Seal`/`LiveDot`,
  `OptionCard`, `ProgressBar`, `Alert`, `Container`. `OptionCard` envuelve un `input` nativo
  en `sr-only` para conservar rol y etiqueta accesible: no lo sustituyas por un `div` con
  `onClick`. El *chip de selección* del handoff (§4) todavía no existe como componente
  porque ningún campo actual lo necesita; su especificación está en el README del handoff
  para cuando lleguen presupuesto, plazo y tipo de inmueble.
- Clases condicionales con `cn()` (`helpers/cn.ts`), que resuelve conflictos de Tailwind.
- La tipografía es Poppins autohospedada con `next/font/google` en el layout de idioma. No
  la sirvas desde `fonts.googleapis.com`: bloquearía el primer render.

Accesibilidad como requisito, no como extra: `aria-invalid` + `aria-describedby` en campos
con error (ya lo hace `components/ui/Field.tsx`, úsalo en vez de montar `<input>` a mano),
`role="alert"` solo para lo que interrumpe, y foco visible.

---

## Dependencias

pnpm 11: los paquetes que necesitan scripts de instalación (`sharp`, `esbuild`,
`unrs-resolver`, `@firebase/util`, `protobufjs`) se declaran en `allowBuilds` dentro de
`pnpm-workspace.yaml` en la raíz. `onlyBuiltDependencies` y el campo `pnpm` de
`package.json` **ya no se leen** en esta versión.

Instala siempre desde la raíz: `pnpm --filter web add <paquete>`.
