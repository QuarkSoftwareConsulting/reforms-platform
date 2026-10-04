# Plan de la Etapa 1 — estado y decisiones

Documento vivo. Recoge qué se acordó con el cliente, qué está hecho y qué falta, para que
cualquier persona o sesión de agente retome el trabajo sin reconstruir la conversación.
**Actualízalo al cerrar cada fase o al cambiar una decisión.**

- Fuente original: documento del cliente "Etapa 1" (flujos F01–F03 con sus respuestas),
  transcrito en [`etapa-1-cliente.md`](./etapa-1-cliente.md).
- Última actualización: 2026-10-03.
- **Las cuatro fases están integradas en `develop`** (PR #20 las trajo apiladas; el #21
  añadió la revisión posterior, ver "Revisión de la Etapa 1" más abajo). Se desarrollaron
  como una rama y un PR por fase, **apilados**; la tabla se conserva como historial.

  | Fase | Rama | PR | Base del PR |
  |---|---|---|---|
  | 1 · Recarga mensual y saldo | `suscriptions` | #16 | `develop` |
  | 2 · Reglas del lead | `feat/reglas-lead` | #17 | `suscriptions` |
  | 3 · Formulario del cliente | `feat/formulario-cliente` | #18 | `feat/reglas-lead` |
  | 4 · Alta y validación del profesional | `feat/validacion-profesional` | #19 | `feat/formulario-cliente` |

  La CI (`.github/workflows/ci.yml`) solo corre en PR contra `develop` o `main`. En local,
  las cuatro fases pasan `pnpm lint`, `pnpm test` y `pnpm verify:flow`.

---

## 1. Reglas de negocio vigentes

Si algo de este apartado contradice el código, gana este apartado y hay que corregir el
código (o volver a hablarlo con el cliente).

### Recarga mensual y acceso

| Estado del profesional | ¿Ve solicitudes? | ¿Compra? |
|---|---|---|
| Registrado, sin recarga o con la recarga vencida (inactivo) | **Sí**, sin datos de contacto | **No** |
| Recarga al día pero "En revisión" (no aprobado) | **Sí**, sin datos de contacto | **No** |
| Recarga al día **y** aprobado | Sí | **Sí** |

- Confirmado por el cliente: "La cuenta inactiva permite visualizar Leads, más no
  comprarlos hasta no estar al día con la recarga mínima mensual."
- **La recarga se abona como saldo** para comprar contactos. El saldo se acumula y no
  caduca. Si no alcanza para un contacto, se aplica el saldo disponible y el resto se cobra
  con Checkout.
- Medios de pago: tarjeta y domiciliación SEPA. Con SEPA, la cuenta queda "pendiente"
  hasta que Stripe confirma el cobro (`invoice.paid`), que puede tardar días.
- **El admin fija el importe de la recarga.** El cliente la define como el valor de un
  contacto, 18 € IVA incluido; es el valor inicial de configuración. Un cambio solo afecta
  a las suscripciones nuevas.
- Si el pago falla (`past_due`) o se cancela, la cuenta queda inactiva: ve solicitudes y
  conserva el saldo, pero no compra.

### Validación del profesional (Fase 4)

- Tras registrarse, el profesional configura perfil, servicios y zona. Después requiere
  verificación y aprobación del admin con documentos.
- Mientras está "En revisión" puede ver solicitudes, pero no comprar.
- **Rechazado en la validación ⇒ reembolso del primer cobro y cancelación automática** de
  la suscripción.

### Precio de los contactos

- El precio de cada lead lo decide el admin cuando llega el proyecto (`Lead.price_override`,
  ya implementado) y puede cambiar el sugerido de cada oficio.
- **Decidido (2026-09-28): 5 € por defecto**, en lugar de los 18 € por contacto del
  documento del cliente. Los 18 € siguen siendo el importe inicial de la recarga.
- Los datos iniciales (`apps/api/data/categories.csv`) sugieren 5 € en todos los oficios.
- Los precios se publican con el IVA incluido (21 %) y se muestra el desglose.

### Plazas por lead

- **5 profesionales por lead** como máximo. Los leads creados antes conservan 3, porque su
  cliente consintió ceder los datos a un máximo de 3.
- Un lead agotado sigue visible como "Cerrado", sin botón de compra.

---

## 2. Fases

Una rama y un PR por fase. Ninguna fase se da por cerrada sin `pnpm lint && pnpm test` en
verde y, si toca leads, pagos o auth, `pnpm verify:flow`.

### Fase 1 — Recarga mensual y saldo · ✅ integrada en `develop`

Hecho:
- Dominio: `ProfessionalAccount` (estado de la suscripción + saldo), libro append-only
  `credit_entries`, `SubscriptionPrice` (historial de importes de la recarga).
- `StartLeadPurchase` exige la recarga al día (`402 SUBSCRIPTION_REQUIRED`). El saldo se
  gasta con la cuenta en `FOR UPDATE`, **después** del lead. Si el saldo cubre el precio,
  la compra queda pagada sin Checkout.
- Webhook: `invoice.paid` activa la cuenta y abona el saldo; `invoice.payment_failed` y
  `customer.subscription.*` sincronizan el estado. Todo pasa por `processed_payment_events`.
- Si una reserva con saldo caduca o falla, el saldo se devuelve (`SPEND_REVERSAL`).
- Admin: cambiar el importe de la recarga (crea un precio nuevo en Stripe), ajustar el
  saldo a mano, ver el estado y el saldo de cada profesional, y la métrica de cuentas
  activas.
- Web: página `/suscripcion`, aviso de estado en "Solicitudes", botón de compra que
  anuncia el saldo, aviso de pago cancelado, tarjeta de recarga en el panel de admin.
- Migraciones: `f74c49826ab1` (cuentas y saldo) y `34c4e1084577` (importe configurable).
- Tests de concurrencia vistos fallar sin el bloqueo, en memoria y contra Postgres.

Sin verificar contra Stripe real (falta una clave de test en `apps/api/.env`):
- Checkout de la recarga.
- Creación de precios desde el admin.
- Checkout de la compra.
- Portal de cliente.

Pendiente dentro de la Fase 1:
- [x] Commit en `suscriptions`.
- [x] Push y PR abierto (ver la tabla del principio).
- [ ] Configurar en Stripe: el portal de cliente (cancelación **al final del periodo**) y
      los eventos del webhook listados en el README.
- [ ] Devolución de adeudos SEPA por el banco o disputa (`charge.dispute.created`).
      **No implementado.** Decisión (2026-09-29): se retira la recarga **entera** aunque ya
      se gastara; lo que falte queda como **deuda** (no saldo negativo). Con deuda no se
      compra y cualquier abono la salda primero; una disputa ganada devuelve el saldo. El
      banco retira el dinero sin permiso nuestro: no es una devolución que decidamos.
- [ ] Disputa de una **compra de contacto** (no de la recarga): hoy no toca el saldo.
      Pendiente de decidir con el cliente (ver §3).
- [ ] Formulario de ajuste manual de saldo en el panel de admin (hoy solo por API).

### Fase 2 — Reglas del lead · ✅ integrada en `develop`

Hecho:
- **5 plazas por lead** (`DEFAULT_MAX_PURCHASES`, `LEAD_MAX_PURCHASES=5`). Los leads
  existentes conservan sus 3: el consentimiento de su cliente (`max_recipients`) se dio
  para un máximo de 3 destinatarios.
- **Precio sugerido de 5 €** en todos los oficios (`categories.csv`). (Al principio
  `pnpm api:seed` sobrescribía el sugerido de los oficios existentes; desde la Fase 3 ya no
  pisa el que haya cambiado el admin.)
- **IVA incluido** con desglose al 21 % (`vat_breakdown` en el dominio; `price_breakdown`
  en el API). La base se redondea al céntimo y la cuota es la diferencia.
- **Leads agotados visibles como "Cerrado"**, después de los abiertos y sin compra. Quien
  ya lo compró conserva el acceso a su contacto.
- **Antes de pagar se ven** el nombre de pila, el CP completo y cuántos profesionales ya
  compraron ("2 de 5"). Nombre y CP solo si el consentimiento lo cubre
  (`lead_consents.allows_public_preview`, migración `b21c3dcaecb5`); los leads anteriores
  siguen sin nombre y con el prefijo del CP.
- Política de privacidad y casilla del formulario actualizadas; versión `2026-09-v2`.
  Invariante §4.4 de `AGENTS.md` reescrito.

Pendiente o fuera de esta fase:
- [x] Commit en `feat/reglas-lead`.
- [x] Push y PR abierto (ver la tabla del principio).
- [ ] Subir `LEAD_MAX_PURCHASES=5` y `PRIVACY_POLICY_VERSION=2026-09-v2` en el entorno de
      Cloud Run (el `.env` local ya está actualizado).
- [x] Servicio, plazo y tipo de inmueble: llegaron con la Fase 3 y ya se ven antes de pagar.
- [ ] "Profesionales que ya compraron": hoy se muestra el **número**. Confirmar con el
      cliente si quiere también los **nombres** comerciales (es dato de otros
      profesionales).
- [ ] Texto legal completo de la política (hoy solo existe el resumen del formulario).

### Fase 3 — Catálogo, cobertura y formulario del cliente (F01) · ✅ integrada en `develop`

Hecho:
- **Catálogo de dos niveles**, categoría → servicio, con las 10 categorías y 86 servicios
  del documento (`categories.csv`, `services.csv`). El cliente elige una categoría y, de
  forma opcional, varios servicios suyos. Los servicios se ven **junto al botón
  "Continuar"** (opción 1 del mockup con el cambio pedido). Los 12 oficios antiguos quedan
  inactivos, no se borran.
- **Cobertura: solo la Comunidad de Madrid** (`ServiceArea`, `POSTAL_CODE_NOT_COVERED`). El
  catálogo de CP de Madrid pasa de 20 a 323 códigos, generados desde GeoNames con
  `scripts/import_postal_codes.py`.
- **Formulario:** tipo de inmueble y "¿Cuál es la programación actual de tu proyecto?", los
  dos obligatorios. Se ven antes de pagar junto con los servicios. "Llamarán" pasa a
  "contactarán". La política ya iba plegada y el formulario ya pedía el CP y no la
  dirección.
- **SMS de verificación del móvil** antes de publicar: puerto `PhoneVerificationPort`,
  endpoint `POST /leads/phone-verification`, fake para tests y adaptador `console` para
  desarrollo. Desactivado por defecto hasta tener proveedor.
- `pnpm api:seed` ya no pisa el precio sugerido que haya cambiado el admin.
- Migración `3a35d15d30d7`.

Interpretaciones que conviene confirmar con el cliente:
- [ ] **Anidación de servicios:** en la transcripción algunos servicios cuelgan de otros
      ("Alicatador" bajo "Cerramiento de terrazas", "Cambiar encimera de cocina" bajo
      "Cambiar plato de ducha"), lo que parece un error de la transcripción. Se han dejado
      todos como servicios de su categoría, sin un tercer nivel.
- [ ] **"Programación actual":** el documento cambia la pregunta, pero no da opciones. Se
      usan las del plazo del mockup (lo antes posible, 2–4 semanas, 1–3 meses, solo
      pidiendo precios), que es lo que F03 llama "plazo". La pregunta "estado actual" del
      mockup desaparece.
- [ ] **Tipo de inmueble:** opciones del mockup (piso, casa o chalet, local, oficina,
      comunidad, nave, terreno).

Pendiente:
- [x] Commit en `feat/formulario-cliente`.
- [x] Push y PR abierto (ver la tabla del principio).
- [ ] **Proveedor de SMS** (§3): adaptador real del puerto y `PHONE_VERIFICATION_BACKEND`.
      Con un proveedor real hará falta también un **límite por IP** en
      `/leads/phone-verification`, contra el abuso de envíos pagados ("SMS pumping").
- [ ] **Atribución de GeoNames** (CC BY 4.0) en la página legal o el pie de la web.
- [x] Filtro por servicio en el explorador: llegó con la Fase 4.
- [ ] Revisión visual del formulario en el navegador (no se pudo hacer en esta sesión).

### Fase 4 — Registro y validación del profesional (F02) · ✅ integrada en `develop`

Hecho:
- **Alta del profesional:**
  - tipo (autónomo, empresa o trabajador independiente);
  - razón social y NIF/NIE/CIF, validado con su letra o dígito de control;
  - dirección y móvil (solo móvil español, sin fijo);
  - base obligatoria en la Comunidad de Madrid;
  - foto de la cara, logo y hasta 8 fotos de trabajos (bucket público).
- **Documentos** en un **bucket privado** aparte:
  - modelos de la AEAT para autónomos y empresas; DNI, TIE o pasaporte para el independiente;
  - el admin los descarga con URLs firmadas de corta duración;
  - `verify:flow` comprueba contra MinIO que sin firma responde 403.
- **Validación:**
  - estados `incomplete` → `pending` (el profesional envía) → `approved` / `rejected` (el admin);
  - cada paso queda auditado en `professional_verification_events`;
  - cola en el panel del admin (lo más antiguo primero) con el expediente.
- **Envío del alta:** no hay botón de envío aparte. El profesional pulsa "Guardar" y, si
  el alta queda completa, un diálogo pide confirmar el envío a revisión (avisa de que tipo,
  razón social, NIF y documentos quedarán fijos). Cancelar deja el alta sin enviar.
- **Acceso:**
  - incompleto o en revisión ve solicitudes, pero no compra (`403 PROFESSIONAL_NOT_APPROVED`);
  - el estado se muestra en "Solicitudes en tu zona" y en el botón de compra.
- **Rechazo:**
  - reembolsa el primer cobro de la recarga y cancela la suscripción, llamando a la pasarela antes de guardar;
  - retira ese saldo con `VERIFICATION_REFUND`;
  - el rechazado deja de ver solicitudes.
- **Servicios ofrecidos:**
  - el profesional elige servicios dentro de sus oficios;
  - en un oficio con servicios elegidos, el explorador solo le muestra los suyos y las solicitudes sin servicio;
  - en un oficio sin servicios elegidos, lo ve todo.
- Migración `c7d7d55fbb83`.

Decisiones tomadas en la implementación (confirmar si no encajan):
- [ ] **Perfiles existentes:** quedan "incompletos" y tienen que aportar datos y documentos
      como un alta nueva antes de poder comprar.
- [ ] **Bloqueo al enviar:** una vez enviada el alta, tipo, razón social, NIF y documentos
      no se pueden cambiar. Si el cliente quiere permitir correcciones, hará falta un
      estado "devuelta para corregir".
- [ ] **Rechazo definitivo:** no hay reapertura. Solo se reembolsa el **primer** cobro,
      como dice el documento; si la revisión tarda más de un mes y hay un segundo cobro,
      ese no se reembolsa solo.
- [ ] **Fotos opcionales**, documentos obligatorios.
- [x] **El NIF/NIE/CIF es obligatorio para los tres tipos** (2026-10-03, decidido por el
      equipo al probar el alta; el documento del cliente no exime a nadie y el pasaporte es
      un documento que se adjunta, no un identificador fiscal). Antes se dejaba en blanco
      al independiente con pasaporte: era una interpretación nuestra, no una regla del
      cliente (pregunta 1 de [`preguntas-cliente.md`](./preguntas-cliente.md)).
      **Consecuencia a confirmar:** un independiente que solo tenga pasaporte y no
      NIE no puede completar el alta. Si el cliente quiere admitirlo, hará falta un campo o
      un tipo de identificador propio, no dejarlo vacío.

Sin verificar contra Stripe real (falta una clave de test):
- El reembolso de la factura (`invoice.payments` → PaymentIntent) y la cancelación de la
  suscripción. Probado con el objeto real del SDK, pero sin llamar a Stripe.

Pendiente:
- [x] Commit en `feat/validacion-profesional`.
- [x] Push y PR abierto (ver la tabla del principio).
- [ ] Crear el bucket privado en GCS (`GCS_PRIVATE_BUCKET`) para Cloud Run: sin él el API
      no arranca con `STORAGE_BACKEND=gcs`.
- [ ] Revisión visual del perfil y de la cola del admin en el navegador.

### Revisión de la Etapa 1 (PR #21) · ✅ integrada

Correcciones tras revisar las fases 1–4; ya están en los invariantes de `AGENTS.md`:
- **Rechazo del alta con el primer cobro SEPA en curso:** se prohíbe hasta que se confirme
  o falle (`409 REJECTION_AWAITING_PAYMENT`), porque ese adeudo no se puede anular y
  abonaría saldo a un rechazado sin reembolso.
- **Rechazo sin reembolsos a medias:** `assert_can_reject` comprueba estado y motivo antes
  de llamar a la pasarela, y el reembolso y la cancelación son idempotentes.
- **Concurrencia en el alta:** quien escribe el perfil lo carga con `get_for_update`
  (orden de bloqueo: profesional antes que cuenta); el rechazo mantiene el bloqueo durante
  las llamadas a Stripe.
- **Vista previa según la política aceptada:** `allows_public_preview` sale de la versión de
  política aceptada (`PUBLIC_PREVIEW_POLICY_VERSIONS`), no de que el lead sea nuevo.
- **Notas de revisión de compras** (`PurchaseReview`, append-only): el admin marca una
  compra para revisión manual (`POST /admin/purchases/{id}/reviews`).

### Roles y panel de admin · ✅ hecho en `improvements-1` (sin integrar)

Pedido interno: asignar admins desde la consola no es viable para el cliente.
- **Roles:** `professional` y `admin`, guardados en `users.role`. El cliente sigue sin
  cuenta (publica como invitado, como se acordó). El admin cambia roles desde el panel;
  surte efecto en la siguiente petición. El claim de Firebase solo crea el primer admin y
  la CLI `manage_admin` escribe en la BD. Invariante §4.14 de `AGENTS.md`.
- **Auditoría:** `user_role_events` (append-only, con el admin que hizo el cambio).
- **Panel:** dashboard con métricas y gráficas diarias (7/30/90 días, hora de Madrid),
  directorio de usuarios con filtros y expediente de alta, y listado global de compras
  (sin PII del cliente), todo paginado.
- `pnpm verify:flow` incluye el paso 13 (roles con token real de Firebase).

Pendiente:
- [ ] Revisión visual del panel en el navegador.
- [ ] Dividir el panel en secciones o pestañas si la página única se hace larga.

### Fase 5 — Notificaciones, WhatsApp, factura y navegación · ⏳ pendiente

- Aviso a los profesionales de la zona al publicarse un lead (SMS, email o WhatsApp; el
  proveedor está sin decidir).
- Correo al cliente con los profesionales que compraron: al llegar a 5 compras o a las
  24 h con los que haya.
- Botón de WhatsApp tras la compra y "generar factura".
- Header: fondo blanco con logotipo azul y amarillo. Navegación pública: Soy profesional |
  Acceder | Publicar solicitud. Privada: Contactos | Mis contactos | Mi perfil | Salir.

---

## 3. Pendientes con el cliente

1. **"Profesionales que ya compraron"**: ¿el número (implementado) o también sus nombres?
2. **Fiscalidad del saldo prepagado**, con su asesor: IVA al cobrar la recarga (anticipo o
   bono univalente), sin factura nueva al gastar saldo. Facturación compatible con
   Verifactu (aplazado a 2027 según la última información; confirmar la fecha).
   Condiciones: saldo no reembolsable en efectivo e intransferible.
3. **Qué pasa con el saldo si cancela la recarga:** hoy se conserva, pero no se puede
   gastar hasta reactivarla. La propuesta es dejarlo usar hasta el final del periodo
   pagado.
4. **Texto de la landing** que sustituye "Sin cuota mensual ni permanencia" (ya retirado;
   el texto nuevo es una propuesta).
5. **Proveedores** de SMS (ya hay puerto y adaptador de desarrollo), WhatsApp y email.
6. **Disputa de una compra de contacto:** ¿devuelve saldo, queda como deuda o la resuelve
   el admin a mano? (La de la recarga ya está decidida, ver Fase 1.)
7. **Confirmar las interpretaciones de la Fase 3** (anidación de servicios, opciones de
   programación y de tipo de inmueble).
8. **Confirmar las decisiones de la Fase 4**: perfiles existentes pasan a "incompletos",
   bloqueo de los datos al enviar el alta (sin estado "devuelta para corregir"), rechazo
   definitivo que solo reembolsa el primer cobro, y fotos opcionales.

## 4. Decisiones descartadas (no reabrir sin hablarlo)

- **Quitar la recarga obligatoria (solo pago por lead):** se descartó; el cliente mantiene
  la recarga.
- **Planes Free/Pro con acceso anticipado:** se exploraron y se descartaron.
- **Bloquear también la vista de solicitudes sin recarga:** se implementó un momento y se
  revirtió, porque el cliente confirmó que la cuenta inactiva **sí** ve los leads.
