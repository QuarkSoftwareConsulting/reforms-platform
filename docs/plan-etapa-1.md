# Plan de la Etapa 1 — estado y decisiones

Documento vivo. Recoge qué se acordó con el cliente, qué está hecho y qué falta, para que
cualquier persona o sesión de agente retome el trabajo sin reconstruir la conversación.
**Actualízalo al cerrar cada fase o al cambiar una decisión.**

- Fuente original: documento del cliente "Etapa 1" (flujos F01–F03 con sus respuestas).
- Última actualización: 2026-09-28.
- Fase 1: rama `suscriptions`, con commit y sin push. Fase 2: rama `feat/reglas-lead`.

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
- Hoy los datos iniciales (`apps/api/data/categories.csv`) sugieren de 3 € a 12 € según el
  oficio; hay que llevarlos a 5 € (Fase 2).

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

### Fase 2 — Reglas del lead · ⏳ pendiente

- 5 plazas por lead en lugar de 3 (`Lead.max_purchases`, settings, textos, `verify:flow`).
- Precio por defecto de 5 € (ver §1): poner a 500 céntimos el sugerido de todos los oficios
  en `categories.csv`. Mostrar "IVA incluido" y el desglose al 21 %.
- Leads agotados visibles como "Cerrado", sin botón de compra.
- Datos visibles antes de pagar: **nombre de pila** del cliente, categoría, servicio,
  descripción, plazo, tipo de inmueble, código postal y profesionales que ya compraron.
  Cambia el invariante §4.4 de `AGENTS.md` y la política de privacidad.

### Fase 3 — Catálogo, cobertura y formulario del cliente (F01) · ⏳ pendiente

- Catálogo de dos niveles (categoría → servicio → sub-servicio) con el listado del documento.
- Cobertura: solo la Comunidad de Madrid (CP 28xxx).
- Formulario: "¿Cuál es la programación actual de tu proyecto?", tipo de inmueble, código
  postal en vez de ubicación, política colapsada, "contactarán" en vez de "llamarán" y los
  servicios junto al botón continuar.
- Verificación del móvil del cliente por SMS (puerto + fake; el proveedor está sin decidir).

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

1. **Fiscalidad del saldo prepagado**, con su asesor: IVA al cobrar la recarga (anticipo o
   bono univalente), sin factura nueva al gastar saldo. Facturación compatible con
   Verifactu (aplazado a 2027 según la última información; confirmar la fecha).
   Condiciones: saldo no reembolsable en efectivo e intransferible.
2. **Qué pasa con el saldo si cancela la recarga:** hoy se conserva, pero no se puede
   gastar hasta reactivarla. La propuesta es dejarlo usar hasta el final del periodo
   pagado.
3. **Texto de la landing** que sustituye "Sin cuota mensual ni permanencia" (ya retirado;
   el texto nuevo es una propuesta).
4. **Proveedores** de SMS, WhatsApp y email.

## 4. Decisiones descartadas (no reabrir sin hablarlo)

- **Quitar la recarga obligatoria (solo pago por lead):** se descartó; el cliente mantiene
  la recarga.
- **Planes Free/Pro con acceso anticipado:** se exploraron y se descartaron.
- **Bloquear también la vista de solicitudes sin recarga:** se implementó un momento y se
  revirtió, porque el cliente confirmó que la cuenta inactiva **sí** ve los leads.
