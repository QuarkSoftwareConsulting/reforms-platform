# Plan de la Etapa 1 — estado y decisiones

Documento vivo. Recoge qué se acordó con el cliente, qué está hecho y qué falta, para que
cualquier persona o sesión de agente retome el trabajo sin reconstruir la conversación.
**Actualízalo al cerrar cada fase o al cambiar una decisión.**

- Fuente original: documento del cliente "Etapa 1" (flujos F01–F03 con sus respuestas),
  transcrito en [`etapa-1-cliente.md`](./etapa-1-cliente.md).
- Última actualización: 2026-09-28.
- Ramas, todas sin push: Fase 1 `suscriptions` (commit `8d534f5`), Fase 2
  `feat/reglas-lead` (commit `239e975`), Fase 3 `feat/formulario-cliente` (con commit). Cada una sale de la anterior.

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

### Fase 1 — Recarga mensual y saldo · ✅ implementada y con commit, pendiente de push y PR

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
- [ ] Push y PR (esperar a que el usuario lo pida).
- [ ] Configurar en Stripe: el portal de cliente (cancelación **al final del periodo**) y
      los eventos del webhook listados en el README.
- [ ] Devolución de adeudos SEPA por el banco (`charge.dispute.created`): restar el saldo
      y bloquear compras hasta regularizar. **No implementado.**
- [ ] Formulario de ajuste manual de saldo en el panel de admin (hoy solo por API).

### Fase 2 — Reglas del lead · ✅ implementada y con commit, pendiente de push y PR

Hecho:
- **5 plazas por lead** (`DEFAULT_MAX_PURCHASES`, `LEAD_MAX_PURCHASES=5`). Los leads
  existentes conservan sus 3: el consentimiento de su cliente (`max_recipients`) se dio
  para un máximo de 3 destinatarios.
- **Precio sugerido de 5 €** en todos los oficios (`categories.csv`). Ojo: `pnpm api:seed`
  sobrescribe el sugerido de los oficios existentes con el del CSV.
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
- [ ] Push y PR (esperar a que el usuario lo pida).
- [ ] Subir `LEAD_MAX_PURCHASES=5` y `PRIVACY_POLICY_VERSION=2026-09-v2` en el entorno de
      Cloud Run (el `.env` local ya está actualizado).
- [x] Servicio, plazo y tipo de inmueble: llegaron con la Fase 3 y ya se ven antes de pagar.
- [ ] "Profesionales que ya compraron": hoy se muestra el **número**. Confirmar con el
      cliente si quiere también los **nombres** comerciales (es dato de otros
      profesionales).
- [ ] Texto legal completo de la política (hoy solo existe el resumen del formulario).

### Fase 3 — Catálogo, cobertura y formulario del cliente (F01) · ✅ implementada y con commit, pendiente de push y PR

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
- [ ] Push y PR (esperar a que el usuario lo pida).
- [ ] **Proveedor de SMS** (§3): adaptador real del puerto y `PHONE_VERIFICATION_BACKEND`.
      Con un proveedor real hará falta también un **límite por IP** en
      `/leads/phone-verification`, contra el abuso de envíos pagados ("SMS pumping").
- [ ] **Atribución de GeoNames** (CC BY 4.0) en la página legal o el pie de la web.
- [ ] Los profesionales siguen eligiendo **categorías**, no servicios, y el explorador
      filtra por categoría. Con categorías amplias ("Obras menores" junta pintores y
      fontaneros), el filtro por servicio llega con el registro de la Fase 4 ("servicios
      ofrecidos").
- [ ] Revisión visual del formulario en el navegador (no se pudo hacer en esta sesión).

### Fase 4 — Registro y validación del profesional (F02) · ⏳ pendiente

- Tipo (autónomo / empresa / trabajador independiente), dirección, móvil, foto, logo,
  fotos de trabajos y documentos (modelos de la AEAT o DNI/TIE/pasaporte) en un bucket
  privado.
- `verification_status` (pendiente / aprobado / rechazado), cola de validación del admin
  con auditoría.
- Reglas del §1: ve en revisión, compra solo aprobado. Al rechazar: reembolso y cancelación
  (puerto: `refund_invoice`, `cancel_subscription`; movimiento de saldo propio e
  idempotente).
- Datos fiscales (NIF, razón social, dirección) para poder facturar.

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
6. **Confirmar las interpretaciones de la Fase 3** (anidación de servicios, opciones de
   programación y de tipo de inmueble).

## 4. Decisiones descartadas (no reabrir sin hablarlo)

- **Quitar la recarga obligatoria (solo pago por lead):** se descartó; el cliente mantiene
  la recarga.
- **Planes Free/Pro con acceso anticipado:** se exploraron y se descartaron.
- **Bloquear también la vista de solicitudes sin recarga:** se implementó un momento y se
  revirtió, porque el cliente confirmó que la cuenta inactiva **sí** ve los leads.
