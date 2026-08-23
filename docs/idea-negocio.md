<requerimientos>## Idea de negocio

Reforma hub resuelve un problema, cuando una persona requiere un tecnico o un profesional en algun are como son: Carpitenria, pintura, promeria (entre otras) pero nconoce a nadie asi que quiere buscarlos, pero no sabe donde, por otro lado existen personas con esas capacidades que saben de un oficio pero no concoern personas que los requieran m es ahi donde **Reforma hub** aparece donde las personas que requieren alguien para un oficio sube loq ue necesita agrega fotos y descripciones ademas de ussus datos de contacto a la plataforma, y los profesionales en el oficio se registran puede ver los diferentes oficios etiquetados por tipo, como lo son carpinteria, promeria y otros comunes y asi ellos pueden decidir COMPRAR EL CONTACTO, lo que significa que deben pagar un dinero por ese contacto (5 euros) la plataforma rcibe el dinero y desbloquea el contacto mostandole los datos de contcto de cliente.

Tambien los clientes y sus requerimientos pueden llegar desde el administrador de la plataforma que puede ingresalos ya que los ha traido de campañas de maketing

## Alcance

### Plataforma Web – Cliente

Los usuarios podrán:

- Acceder a la plataforma y conocer el servicio.

- Publicar una solicitud de trabajo o reforma.

- Seleccionar la categoría del servicio requerido.

- Describir el proyecto o trabajo a realizar.

- Ingresar datos de contacto.

- Aceptar políticas de tratamiento de datos.

- Publicar la solicitud para que sea visible a profesionales.

### Pataforma Web - Profesional

Los profesionales podrán:

- Registrarse en la plataforma.

- Definir sus servicios y zona geográfica.

- Visualizar solicitudes disponibles.

- Revisar información básica del trabajo solicitado.

- Comprar el contacto del cliente mediante pago en la plataforma.

- Acceder a los datos completos del cliente una vez realizado el pago.

- Consultar el historial de contactos adquiridos.

### Panel de Administración

El sistema contará con un panel administrativo que permitirá:

Visualizar solicitudes registradas.

Gestionar usuarios registrados.

Configurar precios por categoría de servicio.

Visualizar compras realizadas por profesionales.

Consultar métricas básicas del sistema.

</requerimientos> Tu tarea es suguerir viavilidad tecnica, esto esta inicial mente en españa pero aberto a extpanciones, el equipo conoce de typescript y pyhton (asi que debe suguerir el stack tecnologico)

El proyecto Reforma Hub es altamente viable técnicamente al seguir un modelo probado de pay-per-lead (similar a Habitissimo o Cronoshare), requiriendo un enfoque prioritario en cumplimiento normativo europeo y geolocalización.

Análisis de Viabilidad y Puntos Críticos

Cumplimiento RGPD (España/UE): Es obligatorio solicitar el consentimiento explícito del cliente para ceder sus datos a profesionales. Se debe guardar registro auditable de la aceptación previa al desbloqueo.

Límite de Compra por Lead (Lead Capping): Cada solicitud debe restringirse a un máximo de 3 a 5 compras para evitar la saturación del cliente y proteger la tasa de conversión del profesional.

Optimización de Micro-pagos: Cobrar 5 € por transacción individual reduce el margen por comisiones fijas de pasarela. La mejor práctica es implementar un sistema de saldo prepagado (wallet) para los profesionales.

Stack Tecnológico Propuesto

Capa Tecnología Justificación Técnica
Frontend Next.js (TypeScript) Híbrido SSR/SSG indispensable para el SEO local en España (ej. "carpintero en Madrid").
Backend FastAPI (Python) Rendimiento elevado, validación estricta de datos con Pydantic y facilidad para analítica posterior.
Base de Datos PostgreSQL + PostGIS Motor relacional con extensión geoespacial para consultas rápidas por código postal o radio en km.
Pagos Stripe API Cumplimiento nativo de la normativa europea SCA/3D Secure y gestión de cobros en múltiples divisas.
Almacenamiento Cloudflare R2 / AWS S3 Guardado optimizado de fotografías de proyectos con CDN y bajos costes de transferencia.
Componentes Clave de Arquitectura

Ingesta Administrativa y Marketing: API REST protegida para conectar formularios de campañas (Meta Lead Ads, Google Ads) vía webhooks o herramientas de automatización (Zapier/Make).

Alertas Geo-localizadas: Módulo de notificaciones en tiempo real vía Email/SMS/WhatsApp (Brevo o Twilio) segmentado por la ubicación geográfica del profesional.

¿Te gustaría profundizar en la arquitectura del sistema de créditos/wallet para optimizar las comisiones o en el modelo de datos para las búsquedas geoespaciales?

bueno dame un PRD

Documento de Requisitos de Producto (PRD): Reforma Hub

1. Visión del Producto y Objetivos
   Reforma Hub es una plataforma marketplace pay-per-lead que conecta a propietarios/inquilinos en España con profesionales del sector de reformas y mantenimiento (carpintería, fontanería, pintura, etc.).

Objetivo de Negocio: Monetizar mediante la venta de contactos de clientes verificados a un precio base de 5 € por lead.

Límite de Monetización (Lead Capping): Un mismo lead solo podrá ser adquirido por un máximo de 3 profesionales para garantizar la conversión y evitar la saturación del cliente.

Alcance Geográfico: Fase 1 en España (soporte para Código Postal y provincias), diseñado con arquitectura multi-idioma/multi-moneda para expansión internacional.

2. Tipos de Usuario
   Cliente (Demandante): Publica requerimientos de reforma sin costo.

Profesional (Oferente): Busca proyectos por zona/oficio y paga para obtener los datos directos del cliente.

Administrador del Sistema: Opera el marketplace, gestiona campañas de adquisición de leads e inspecciona transacciones.

3. Requisitos Funcionales
   Módulo Usuario Funcionalidad Criterio de Aceptación
   Publicación de Solicitud Cliente Formulario paso a paso con categoría, descripción, fotos, Código Postal y datos de contacto. Consentimiento explícito de RGPD para cesión de datos. Verificación de teléfono vía SMS (OTP).
   Explorador de Proyectos Profesional Listado de trabajos filtrable por categoría y distancia geográfica (radio en km). Muestra detalles del trabajo (fotos, descripción, ciudad/CP) pero oculta nombre, teléfono y email.
   Compra y Desbloqueo Profesional Adquisición del lead mediante pago con tarjeta o saldo prepagado (Wallet). Tras el pago exitoso, la interfaz muestra de inmediato los datos de contacto y envía copia por email.
   Ingesta Externa de Leads Admin API / Webhook para inyectar solicitudes desde Meta Ads y Google Ads. Transforma formularios externos en solicitudes publicadas automáticamente en el sistema.
   Gestión Administrativa Admin Panel para moderar solicitudes, gestionar usuarios y ajustar precios por categoría. Posibilidad de deshabilitar leads duplicados/fraudulentos y reembolsar saldo al profesional.
4. Requisitos No Funcionales y Legales
   Cumplimiento RGPD (UE): Registro auditable (IP, fecha y hora) del consentimiento del cliente autorizando que hasta 3 profesionales lean sus datos de contacto.

Rendimiento: Tiempos de carga de página < 1.5s (SEO focalizado mediante Next.js SSR) y respuestas de API < 200 ms (FastAPI).

Seguridad y Pagos: Cumplimiento con la normativa europea SCA / 3D Secure 2.0 a través de la integración nativa de Stripe.

Geolocalización: Consultas espaciales optimizadas con PostGIS en la base de datos para filtrado preciso por código postal o radio en kilómetros.

5. Métricas Clave de Éxito (KPIs)
   Tasa de Cobertura de Lead: % de solicitudes publicadas que son compradas por al menos 1 profesional (Meta: > 75%).

Liquidez del Lead: Promedio de profesionales que adquieren cada lead (Meta: 2.2 profesionales/lead).

Frecuencia de Compra: Promedio de leads adquiridos por mes por profesional activo.

¿Quieres que profundicemos en las historias de usuario detalladas (User Stories) para la fase de desarrollo o en la estructura OpenAPI del endpoint de ingesta de leads?

modifica teiendo en cuenta

- la ingesta desde admin no requiere webhook eso lo hara el admin desde un fomrualrio.

- multilenguahe ingles y español

- se va apoder pagar en euro, dolar y otras ¿monedas, (esto lo hace stripe?)

Efectivamente, Stripe maneja el cobro multimoneda de forma nativa y automática. Puedes configurar los precios en la moneda base (ej. Euros) y Stripe se encarga de mostrar la conversión y cobrar en la moneda local del profesional (Dólares, Pesos, etc.), o bien puedes establecer precios fijos por cada moneda.

Aquí tienes el PRD actualizado con tus modificaciones:

Documento de Requisitos de Producto (PRD): Reforma Hub (Actualizado)

1. Visión del Producto y Objetivos
   Reforma Hub es una plataforma marketplace pay-per-lead que conecta a clientes con requerimientos de oficios (carpintería, fontanería, pintura, etc.) con profesionales del sector.

Objetivo de Negocio: Monetizar mediante la venta de contactos de clientes verificados a un precio base (ej. 5 €/$5 USD) por lead.

Internacionalización: La plataforma nace con soporte bilingüe (Español e Inglés) y sistema multimoneda (Euros, Dólares y otras) para facilitar su expansión global.

Límite de Monetización (Lead Capping): Un mismo lead solo podrá ser adquirido por un máximo de 3 profesionales para garantizar la conversión y evitar la saturación del cliente.

2. Tipos de Usuario
   Cliente (Demandante): Publica requerimientos de reforma sin costo.

Profesional (Oferente): Busca proyectos por zona/oficio y paga para obtener los datos directos del cliente.

Administrador del Sistema: Opera el marketplace, gestiona moderación e ingresa manualmente leads captados de otros canales.

3. Requisitos Funcionales
   Módulo Usuario Funcionalidad Criterio de Aceptación
   Publicación de Solicitud Cliente Formulario paso a paso con categoría, descripción, fotos, ubicación y datos de contacto. Consentimiento explícito de políticas de privacidad. Verificación de teléfono (OTP) opcional.
   Explorador de Proyectos Profesional Listado de trabajos filtrable por categoría y ubicación. Muestra detalles del trabajo (fotos, descripción, ciudad) pero oculta nombre, teléfono y email.
   Compra y Desbloqueo Profesional Adquisición del lead mediante pago con tarjeta en su moneda local. Tras el pago exitoso, la interfaz muestra de inmediato los datos de contacto y envía copia por email.
   Ingesta Manual de Leads Admin Formulario interno en el panel administrativo para crear solicitudes. El admin puede ingresar manualmente los datos de leads provenientes de redes sociales o marketing, publicándolos directamente.
   Gestión Administrativa Admin Panel para moderar solicitudes, gestionar usuarios, configurar monedas/precios y ver métricas. Posibilidad de deshabilitar leads, ver el historial de compras y realizar reembolsos si es necesario.
4. Requisitos No Funcionales y Legales
   Internacionalización (i18n): Todo el frontend (Next.js), correos electrónicos y notificaciones deben soportar Español e Inglés, con capacidad de detectar el idioma del navegador del usuario.

Pagos Multimoneda: Integración con Stripe Billing/Checkout. El sistema debe ser capaz de procesar pagos en EUR, USD y otras monedas, aplicando las normativas de seguridad SCA / 3D Secure.

Cumplimiento de Privacidad: Registro auditable del consentimiento del cliente autorizando la cesión de sus datos. Adaptabilidad a RGPD (Europa) y otras normativas según la región.

Rendimiento y SEO: Tiempos de carga < 1.5s. Renderizado del lado del servidor (SSR) para indexar páginas por oficio y ciudad (ej. "Plumbers in Miami" / "Carpinteros en Madrid").

5. Métricas Clave de Éxito (KPIs)
   Tasa de Cobertura de Lead: % de solicitudes publicadas (tanto orgánicas como ingresadas por el admin) que son compradas por al menos 1 profesional.

Ingresos por Moneda: Volumen de facturación segmentado por divisa (EUR vs USD).

Costo de Adquisición vs Valor de Venta: Comparación entre lo que gasta el admin en marketing para traer un lead manualmente, frente a las veces que se vende ese lead en la plataforma.

¿Consideras que con estos ajustes el alcance refleja mejor tu idea? Si estás de acuerdo, el siguiente paso ideal sería definir las Historias de Usuario o el Diagrama de Entidad-Relación (Base de Datos) para que el equipo de Python y TypeScript empiece a trabajar.

antes de eso dame el documeto en markdopwn para poderlo copiar

Tu archivo Markdown (MD) está listo.

MD icon
PRD_Reforma_Hub
MD
Open
Puedes descargar el archivo y copiar el texto directamente a tus notas, Jira, Notion o la herramienta que utilices para gestionar el proyecto.

¿Te gustaría que ahora trabajemos en las Historias de Usuario o en el Modelo de Base de Datos?

Your Lean Solutions Group - GTS chats aren’t used to improve our models. Gemini is AI and can make mistakes. Your privacy & GeminiOpens in a new window

Analyzing

# Documento de Requisitos de Producto (PRD): Reforma Hub

## 1. Visión del Producto y Objetivos

Reforma Hub es una plataforma marketplace _pay-per-lead_ que conecta a clientes con requerimientos de oficios (carpintería, fontanería, pintura, etc.) con profesionales del sector.

- **Objetivo de Negocio:** Monetizar mediante la venta de contactos de clientes verificados a un precio base (ej. 5 €/$5 USD) por lead.
- **Internacionalización:** La plataforma nace con soporte bilingüe (**Español e Inglés**) y sistema **multimoneda** (Euros, Dólares y otras) para facilitar su expansión global.
- **Límite de Monetización (_Lead Capping_):** Un mismo lead solo podrá ser adquirido por un máximo de **3 profesionales** para garantizar la conversión y evitar la saturación del cliente.

---

## 2. Tipos de Usuario

- **Cliente (Demandante):** Publica requerimientos de reforma sin costo.
- **Profesional (Oferente):** Busca proyectos por zona/oficio y paga para obtener los datos directos del cliente.
- **Administrador del Sistema:** Opera el marketplace, gestiona moderación e ingresa manualmente leads captados de otros canales.

---

## 3. Requisitos Funcionales

| Módulo                       | Usuario     | Funcionalidad                                                                                  | Criterio de Aceptación                                                                                                         |
| :--------------------------- | :---------- | :--------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------- |
| **Publicación de Solicitud** | Cliente     | Formulario paso a paso con categoría, descripción, fotos, ubicación y datos de contacto.       | Consentimiento explícito de políticas de privacidad. Verificación de teléfono (OTP) opcional.                                  |
| **Explorador de Proyectos**  | Profesional | Listado de trabajos filtrable por categoría y ubicación.                                       | Muestra detalles del trabajo (fotos, descripción, ciudad) pero **oculta** nombre, teléfono y email.                            |
| **Compra y Desbloqueo**      | Profesional | Adquisición del lead mediante pago con tarjeta en su moneda local.                             | Tras el pago exitoso, la interfaz muestra de inmediato los datos de contacto y envía copia por email.                          |
| **Ingesta Manual de Leads**  | Admin       | Formulario interno en el panel administrativo para crear solicitudes.                          | El admin puede ingresar manualmente los datos de leads provenientes de redes sociales o marketing, publicándolos directamente. |
| **Gestión Administrativa**   | Admin       | Panel para moderar solicitudes, gestionar usuarios, configurar monedas/precios y ver métricas. | Posibilidad de deshabilitar leads, ver el historial de compras y realizar reembolsos si es necesario.                          |

---

## 4. Requisitos No Funcionales y Legales

- **Internacionalización (i18n):** Todo el frontend (Next.js), correos electrónicos y notificaciones deben soportar Español e Inglés, con capacidad de detectar el idioma del navegador del usuario.
- **Pagos Multimoneda:** Integración con Stripe Billing/Checkout. El sistema debe ser capaz de procesar pagos en EUR, USD y otras monedas, aplicando las normativas de seguridad SCA / 3D Secure.
- **Cumplimiento de Privacidad:** Registro auditable del consentimiento del cliente autorizando la cesión de sus datos. Adaptabilidad a RGPD (Europa) y otras normativas según la región.
- **Rendimiento y SEO:** Tiempos de carga < 1.5s. Renderizado del lado del servidor (SSR) para indexar páginas por oficio y ciudad (ej. "Plumbers in Miami" / "Carpinteros en Madrid").

---

## 5. Métricas Clave de Éxito (KPIs)

- **Tasa de Cobertura de Lead:** % de solicitudes publicadas (tanto orgánicas como ingresadas por el admin) que son compradas por al menos 1 profesional.
- **Ingresos por Moneda:** Volumen de facturación segmentado por divisa (EUR vs USD).
- **Costo de Adquisición vs Valor de Venta:** Comparación entre lo que gasta el admin en marketing para traer un lead manualmente, frente a las veces que se vende ese lead en la plataforma.
  PRD_Reforma_Hub.md
  PRD_Reforma_Hub.md
  Loading PRD_Reforma_Hub.md.Displaying PRD_Reforma_Hub.md.
