# Voy a Reformar — Paquete de handoff para desarrollo

Marketplace español donde profesionales de la reforma compran contactos de clientes ya validados por teléfono.

Este paquete contiene el diseño de referencia, los tokens y la especificación de comportamiento necesarios para implementarlo en un codebase real.

---

## 1. Cómo usar este paquete con Claude Code

1. Copia la carpeta `design_handoff_voyareformar/` a la raíz de tu repositorio.
2. Abre Claude Code en el repositorio.
3. Prompt sugerido:

```
Lee design_handoff_voyareformar/README.md y design_handoff_voyareformar/tokens.css.
Implementa la pantalla del formulario de solicitud (sección 5 del README) en nuestro stack,
siguiendo los patrones de componentes y el sistema de estilos que ya usamos en este repo.
No copies los estilos inline de los HTML de referencia: son solo referencia visual.
```

4. Para ver el diseño: abre `pantallas/Voy a Reformar - Opciones web.dc.html` en un navegador.

**Importante.** Los HTML de `pantallas/` usan estilos inline porque están hechos para verse, no para mantenerse. Son la fuente de verdad del **aspecto** y del **comportamiento**, no del código.

---

## 2. Contenido

```
design_handoff_voyareformar/
├── README.md                              este archivo
├── tokens.css                             variables CSS listas para usar
├── assets/logo-voyareformar.png           logo principal
└── pantallas/
    ├── Voy a Reformar - Design System.dc.html   catálogo de componentes y estados
    ├── Voy a Reformar - Opciones web.dc.html    formulario + 2 direcciones de home
    ├── support.js                               runtime de los HTML de referencia
    └── assets/
```

En `Opciones web` hay tres bloques: **2a** el formulario del cliente (interactivo), **1a** y **1b** dos direcciones de home aún sin decidir.

---

## 3. Fundamentos

### Color

| Token | Hex | Uso |
|---|---|---|
| Azul marca | `#034AAC` | Botón primario, enlaces, precios, iconografía activa |
| Amarillo acento | `#F5C336` | CTA de compra, sellos, subrayados. **Texto siempre `#1F2937` encima** |
| Gris tinta | `#1F2937` | Titulares, texto principal, cabecera oscura, pie |
| Blanco | `#FFFFFF` | Superficies de tarjeta y formulario |
| Azul oscuro | `#023576` | Hover del primario |
| Amarillo oscuro | `#E0AE1F` | Hover del acento |
| Fondo página | `#F4F6FA` | |
| Azul suave | `#E8EEFA` | Fondo de estado seleccionado |
| Borde | `#E6E9EE` | Bordes y separadores |
| Borde fuerte | `#D1D5DB` | Borde de botón secundario |
| Texto ayuda | `#6B7280` | |
| Texto secundario | `#4B5563` | |
| Error | `#C0392B` sobre `#FDF3F2` | |
| Desactivado | texto `#9CA3AF` / `#C4C9D2`, fondo `#E6E9EE` | |

Nunca texto blanco sobre amarillo: no cumple contraste AA.

### Tipografía

Poppins, pesos 300–800. `https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800`

| Rol | Tamaño / peso / tracking |
|---|---|
| Display (hero) | 58 / 700 / −1.4px / lh 1.05 |
| H1 de página | 36 / 700 / −1px |
| H2 de sección | 30 / 700 / −0.6px |
| Título de tarjeta | 17 / 600 / lh 1.4 |
| Cuerpo | 15–16 / 400 / lh 1.6 |
| Ayuda | 13 / 400 |
| Etiqueta | 12.5 / 600 / 1.2px / mayúsculas |

Tracking negativo solo en titulares. El cuerpo nunca lleva tracking.

### Espaciado

Escala base 4 px: `4 · 8 · 12 · 14 · 24 · 40 · 64`.
8 gap entre chips · 12 gap en rejillas de opciones · 14 entre bloques de formulario · 24 padding de tarjeta · 40 margen lateral de página · 64 entre secciones.

### Radios

`6` etiqueta · `10` control y botón · `12` tarjeta de opción · `14` tarjeta · `18` panel · `999` chip.

### Elevación

Por defecto plana: solo `1px solid #E6E9EE`. Sombra `0 6px 20px rgba(31,41,55,.10)` únicamente en menús y modales. Las tarjetas de listado nunca llevan sombra.

---

## 4. Componentes

### Botón

Radio 10, peso 600, `white-space: nowrap`. Un solo primario por vista.

| Variante | Normal | Hover | Desactivado |
|---|---|---|---|
| Primario | bg `#034AAC`, texto `#fff` | bg `#023576` | bg `#E6E9EE`, texto `#9CA3AF` |
| Acento | bg `#F5C336`, texto `#1F2937` | bg `#E0AE1F` | bg `#F6EBC6`, texto `#A99A6B` |
| Secundario | bg `#fff`, borde 1.5px `#D1D5DB`, texto `#1F2937` | borde y texto `#034AAC` | borde `#E6E9EE`, texto `#C4C9D2` |
| Texto | `#034AAC` subrayado, sin fondo | `#023576` | `#C4C9D2` |

Tamaños: compacto 40 px (`9px 18px`, 14/22, radio 8) · normal 48 px (`12px 26px`, 16/24) · grande 56 px (`15px 32px`, 17/26). El secundario descuenta el borde: `10.5px` vertical. En móvil ningún botón baja de 48 px.

### Campo de texto

Padding `13px 14px`, borde 1.5px `#E6E9EE`, radio 10, texto 15.
Foco: borde `#034AAC` + `box-shadow: 0 0 0 3px rgba(3,74,172,.14)`.
Error: borde `#C0392B`, fondo `#FDF3F2`, mensaje 13/500 en `#C0392B` debajo.
Etiqueta 15/600 encima. Ayuda 13 en `#6B7280` debajo del campo, nunca dentro del placeholder.

### Chip de selección

Padding `10px 16px`, radio 999, borde 1.5px, texto 14.5.
Sin seleccionar: borde `#E6E9EE`, fondo `#fff`, peso 400.
Seleccionado: borde y fondo `#034AAC`, texto `#fff`, peso 500.
No disponible: borde `#E6E9EE`, fondo `#F4F6FA`, texto `#C4C9D2`.

Se usa para presupuesto, plazo, tipo de inmueble, estado, relación con el inmueble, franja horaria y subservicios.

### Tarjeta de opción

Padding `14px 16px`, radio 12, borde 1.5px, columna con gap 4.
Título 15/600 `#1F2937`, subtítulo 12.5/lh 1.45 `#6B7280`.
Seleccionada: borde `#034AAC`, fondo `#E8EEFA`.

### Etiquetas y sellos

Gremio sobre fondo claro: 12/600, tracking .7px, mayúsculas, `#034AAC` sobre `#E8EEFA`, padding `6px 11px`, radio 6.
Gremio sobre fondo oscuro: 11.5/700, `#1F2937` sobre `#F5C336`, padding `5px 10px`, radio 5.
Verificado: icono de sello amarillo 15px + texto 12.5/600 `#1F2937`.
Precio de contacto: 19/700 `#034AAC`.
En directo: punto de 7px `#034AAC` + texto 13 `#6B7280`.

### Tarjeta de contacto

El componente central. Orden fijo:

1. Fila superior: etiqueta de gremio (izquierda) + sello de verificación (derecha)
2. Titular 17/600 — qué trabajo y en qué barrio y ciudad
3. Descripción 14.5/lh 1.6 `#4B5563`
4. Separador `1px #EEF1F5` y fila de precios: presupuesto estimado (izq.) y precio del contacto (der.), ambos 17/700
5. Botón acento a ancho completo: "Comprar contacto"

Tres estados:
- **Disponible** — como arriba.
- **Comprado** — etiqueta "Ya comprado", fecha de compra en lugar del sello; el bloque de precios se sustituye por los datos del cliente (nombre, teléfono, dirección completa); botón primario "Llamar ahora".
- **Cerrado** — `opacity: .55`, etiqueta gris, sin descripción larga ni botón.

El precio del contacto debe ser visible **siempre** antes de pagar.

### Barra de progreso

Pista 6px `#E6E9EE` radio 999, relleno `#F5C336`.

---

## 5. Pantalla: formulario de solicitud del cliente

Referencia: bloque **2a** de `pantallas/Voy a Reformar - Opciones web.dc.html` (interactivo).

Tres pasos, **sin crear cuenta**. Ancho de contenido 980 px, fondo `#F4F6FA`, superficies blancas.

Cabecera fija en las tres vistas: logo + aviso con icono de candado — «Sin crear cuenta. Tu teléfono solo lo ve el profesional que compra el contacto.»
Encima de cada paso: etiqueta "Paso N de 3" en azul + barra de progreso al 33 / 66 / 100 %.

### Paso 1 — Qué trabajo necesitas

Rejilla de 3 columnas con las 18 categorías como tarjetas de opción (título + lista de subservicios como subtítulo):

Reformas · Pintura y decoración · Albañilería · Electricidad · Fontanería · Carpintería · Cocinas · Baños · Climatización y calefacción · Ventanas y cerramientos · Suelos y revestimientos · Pladur y aislamiento · Humedades e impermeabilización · Cerrajería · Manitas y reparaciones · Jardines, terrazas y piscinas · Eficiencia energética · Interiorismo, arquitectura y proyectos

Los subservicios exactos de cada categoría están en el array `CATS` dentro del HTML de referencia.

Al seleccionar una categoría aparece debajo un panel «¿Qué incluye el trabajo?» con los subservicios de esa categoría como chips de selección múltiple (opcional). Cambiar de categoría limpia los subservicios marcados.

**Validación:** categoría obligatoria. Sin ella, "Continuar" desactivado.

### Paso 2 — Cuéntanos el proyecto

| Campo | Tipo | Obligatorio |
|---|---|---|
| Descripción del trabajo | textarea 4 filas | sí, mín. 10 caracteres |
| Tipo de inmueble | chip único: Piso · Casa o chalet · Local comercial · Oficina · Comunidad de vecinos · Nave o industrial · Terreno o exterior | sí |
| Estado actual | chip único: A estrenar / obra nueva · En buen estado · Necesita actualización · Muy deteriorado · Vivienda vacía · Habitada durante la obra | sí |
| Relación con el inmueble | chip único: Soy el propietario · Soy inquilino · Administro el inmueble | no |
| Código postal | texto | sí, 5 dígitos |
| Superficie aproximada | texto (`78 m²`) | no |
| Presupuesto | chip único: Menos de 1.000 € · 1.000–5.000 € · 5.000–15.000 € · 15.000–40.000 € · Más de 40.000 € · No lo sé todavía | no |
| Plazo | chip único: Lo antes posible · En 2-4 semanas · En 1-3 meses · Solo estoy pidiendo precios | no |

Pie: "Atrás" secundario a la izquierda, "Continuar" primario a la derecha.

### Paso 3 — Tus datos de contacto

| Campo | Tipo | Obligatorio | Nota bajo el campo |
|---|---|---|---|
| Nombre completo | texto, ancho completo | sí | |
| Teléfono | tel | sí, mín. 9 dígitos | «Es el dato principal. Llamamos desde un número español.» |
| Email | email | no | «Te enviamos una copia de tu solicitud.» |
| Ubicación | texto, ancho completo | sí | «La dirección exacta solo se muestra al profesional que compra tu contacto. En el listado público únicamente aparece el barrio.» |
| Franja horaria | chip único: Mañanas · Tardes · Cualquier hora | no | |
| Consentimiento RGPD | checkbox, `accent-color: #034AAC`, 20×20 | sí | ver abajo |

La cabecera del paso muestra un resumen: `categoría · tipo de inmueble · m² · CP`.

**Consentimiento.** Texto: «He leído y acepto la política de tratamiento de datos. Autorizo a Voy a Reformar a tratar mis datos para validar la solicitud y a cederlos al profesional que compre el contacto, conforme al RGPD (UE) 2016/679 y la LOPDGDD 3/2018.» El enlace abre la página completa; debajo, un botón de texto despliega en la misma vista un panel con el resumen de la política (responsable, finalidad, legitimación, destinatarios, conservación, derechos), con `max-height: 190px` y scroll.

**Pendiente de producto:** los datos reales del responsable (razón social, domicilio, email de privacidad) son ficticios en el diseño.

### Confirmación

Panel blanco centrado, radio 18: círculo amarillo de 62 px con check, «Solicitud recibida» en 30/700, y el texto de qué pasa después. Botón secundario «Enviar otra solicitud» que reinicia el formulario.

---

## 6. Pantallas de home (sin decidir)

`1a` **Oficio** — hero azul con la promesa primero y dos tarjetas de entrada (profesional / cliente). Más institucional.
`1b` **Tablero** — el producto visible desde el primer scroll: contactos reales en directo junto al titular. Más comercial.

Ambas incluyen: validación en 3 pasos, listado de contactos, testimonios de profesionales y bloque de precio transparente. Elegid una antes de implementar.

---

## 7. Reglas del sistema

**Sí**
- Un solo botón primario por pantalla.
- El precio del contacto siempre visible antes de pagar.
- Amarillo sobre azul o sobre blanco, con texto gris tinta encima.
- Texto de ayuda bajo el campo, no dentro del placeholder.
- Superficies blancas sobre fondo `#F4F6FA`.

**No**
- Texto blanco sobre amarillo.
- Degradados en fondos o botones.
- Sombras en tarjetas de listado.
- Más de dos pesos tipográficos en un mismo bloque.
- Iconos decorativos que no aporten información.

---

## 8. Decisiones abiertas

- Colores de estado más allá del error (éxito, aviso, informativo).
- Set de iconos. Los del diseño son SVG sueltos inline.
- Comportamiento responsive: el diseño está hecho a 980–1280 px. Los puntos de ruptura móviles no están definidos.
- Listado completo de contactos, ficha de detalle, registro del profesional y panel de saldo: aún sin diseñar.
- Datos legales reales de la empresa para la política de privacidad.
