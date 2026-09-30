<!-- Transcripcion del documento del cliente "Etapa 1" (flujos F01-F03 con sus respuestas).
     Es la fuente de docs/plan-etapa-1.md. No editar: si el cliente cambia algo, anotarlo en el plan. -->

# F01 Cliente publica solicitud de reforma

En el flujograma, antes de la publicación validar teléfono por medio de mensaje de texto, después de la confirmación de publicación al cliente enviar mensaje de texto a profesionales, correo electrónico o WhatsApp.

Una vez se completen 5 profesionales enviar automáticamente información por correo electrónico al Cliente con el nombre, teléfono móvil y tipo de profesional (autónomo, Empresa o trabajador independiente) que atendería la solicitud de presupuesto, si a las 24 horas no se completan 5 profesionales, enviar información de los que hayan, si ningún profesional se apunta, no enviar correo electrónico.

## Preguntas y respuestas

* **¿El cliente publica como invitado o tendrá cuenta?**  
  El cliente publica como invitado.

* **¿Secciones "Categoría, Descripción y Datos" son correctas en orden y contenido?**  
  Son correctas en orden y contenido.

* **¿Qué datos quedan visibles para el profesional antes de pagar y cuáles después del pago?**  
  * **Datos visibles antes de pagar:** Nombre, Código Postal.  
  * **Datos visibles después de pagar:** Todos.

* **Categorías / Servicios**  
  Listado completo en pagina 3 de este documento.

* **Vistas / mockups - Categoría/Servicio**  
  La opción 1, adicionando que, al dar clic en la categoría, la observación de los servicios se visualice justo al lado del botón continuar.

---

# F01 Cliente publica solicitud de reforma

## 2. Detalles del Proyecto
Cambiar la pregunta: *"¿Cuál es el estado actual de la reforma?"*, por la pregunta, *"¿Cuál es la programación actual de tu proyecto?"*

## 3. Datos de contacto
Reemplazar la ubicación por el código postal.

* **Vistas / mockups - Datos de contacto**  
  Elegimos política de datos colapsada.

* **Vistas / mockups - Solicitud publicada**  
  Cambiar la palabra *"llamarán"* por la palabra *"contactarán"*.

---

# F02 Profesional: registro e inicio de sesión

Flujograma, después de la aceptación de términos del profesional se configura el perfil, servicios ofrecidos y zona geográfica, luego se requiere la verificación y aprobación.

Se debe debitar mensualmente de la cuenta bancaria del profesional la recarga mínima, el precio es el valor de un contact, de esa manera se mantiene la cuenta activa. Este valor se podrá utilizar para la compra de contactos. En el formulario solicitudes en tu zona, debe mostrarse el estado actual del profesional. La cuenta inactiva permite visualizar Leads, más no comprarlos hasta no estar al día con la recarga mínima mensual.

## Preguntas:

* **¿El profesional puede entrar inmediatamente o necesita verificación/aprobación?**  
  El profesional necesitará verificación y aprobación para registrarse en la plataforma, se debe identificar como Autónomo, Empresa o Trabajador independiente, para cualquiera de los dos primeros se solicitará adjunto de algunos modelos de la agencia tributaria, para el trabajador independiente se solicitará identificación (DNI, TIE, Pasaporte), los documentos se verifican y si es el caso se aprueba el registro en la plataforma. De esta manera habrá un campo que identificará a cada profesional, el cual utilizaremos más adelante.

---

## Describir lista completa de servicios y zonas geográficas disponibles

En la primera etapa, la zona de cobertura del servicio es la **Comunidad de Madrid**.

### Las categorías y servicios:

#### Reformas
* Reformas de baños
* Reformas de cocinas
* Reformas de viviendas
* Reforma integral (baño, cocina, casa, piso, vivienda)
* Reformas de locales comerciales
* Rehabilitación de fachadas
* Cambiar plato de ducha
  * Cambiar bañera por plato de ducha
  * Cambiar encimera de cocina
* Cerramiento de terrazas
  * Alicatador
* Quitar gotelé
  * Reparación de paredes

#### Seguridad Electrónica
* Circuito Cerrado de televisión (CCTV)
* Alarma
* Control de acceso
* Sistemas de detección de incendio
* Automatización
* Domótica

#### Construcción
* Construcción de casas
* Construcción de piscinas
* Construcción de muros
* Derribos y demoliciones
* Excavaciones
  * Nivelación de terreno
  * Alquiler de andamios

#### Instaladores
* Electricistas
  * Instalación eléctrica
* Aire acondicionado (instalación y reparación)
* Instalación de ventilador de techo
* Aerotermia
* Calefacción
  * Cambiar caldera
  * Instalar radiadores
* Placas solares
* Ascensores
* Antenas
* Toldos
* Domótica
* Alarmas
* Porteros automáticos
* Puertas de garaje
* Reparación de persianas

#### Obras Menores
* Pintores
  * Pintar casa
  * Pintar paredes
* Albañiles
* Fontaneros
* Cerrajeros
* Carpinteros
* Pladur (paredes y techos)
* Microcemento
* Parquetistas
* Cristaleros
* Yeseros
* Poner suelo laminado
* Poner suelo porcelánico
* Humedades
* Impermeabilizaciones
* Aislamiento térmico
* Tejados y reparación de tejados

#### Mantenimiento
* Limpieza
* Jardineros
* Control de plagas
* Pulir suelos
* Montaje de muebles (incl. IKEA)
* Manitas
* Mantenimiento de ascensores
* Mantenimiento de comunidades
* Mantenimiento de piscinas

#### Técnicos
* Arquitectos
* Ingenieros
* Peritos
* Interiorismo
* Certificaciones energéticas
* Cédulas de habitabilidad

#### Mudanzas
* Mudanzas de viviendas
* Mudanzas de oficinas
* Portes
* Guardamuebles
* Trasteros
* Transporte de muebles
* Retirada de muebles

#### Bienestar y Salud
* Entrenador personal

#### Servicios Profesionales
* Diseño web y creación de páginas web
* Marketing y publicidad

---

* **Servicios y zona se configuran durante el registro o inmediatamente después. No se debería obligar al profesional a introducirlos dos veces.**  
  Servicios y zona se configuran en el registro.

## F02 Profesional: registro e inicio de sesión

* **Datos requeridos:**  
  * El teléfono fijo no es necesario.  
  * Cambiar la palabra celular por *"Móvil"*.  
  * Cobertura geográfica en la primera etapa será la Comunidad de Madrid.  
  * Adicionar un espacio para permitir subir una foto del rostro de la persona, un logo y algunas fotos de trabajos realizados.  
  * Adicionar un espacio para permitir subir los documentos de alta de autónomo o empresa, TIE o Pasaporte.

* **Vistas / mockups - Completa tu perfil:**  
  Adicionar campo de dirección de la empresa o domicilio.

* **Vistas / mockups - Solicitudes en tu zona:**  
  * La cantidad máxima de plaza por contacto será de 5 profesionales.  
  * El precio por cada contacto inicialmente será de 18 euros, impuestos incluidos. El IVA es del 21%.

---

# F03 Profesional consulta y compra un lead

* **¿Qué ve el profesional antes de pagar y qué se desbloquea después?**  
  * **Antes de pagar:** Puede ver Nombre, categoría, servicio, descripción, plazo, tipo de inmueble, código postal, cantidad de profesionales que ya compraron el contacto.  
  * **Después de comprar:** Puede ver los datos de contacto, correo electrónico, móvil, nombre completo.

* **¿Cuántos profesionales pueden comprar cada lead?**  
  5

* **¿El lead cuesta siempre lo mismo o su precio cambia?**  
  Cuesta lo mismo siempre.

* **¿Qué ocurre cuando alcanza el máximo de compras?**  
  Sí, se muestra como Cerrado.

* **¿Qué ocurre después del pago?**  
  Mostrar la información de contacto con la opción para contactar inmediatamente por WhatsApp y generar factura.

---

> **Nota visual sobre el encabezado:**  
> Del siguiente encabezado, me gustaría visualizar el fondo blanco con el nombre de la plataforma en los colores azul y amarillo, como se encuentra en la identidad de marca.

## 08-NAVEGACIÓN

### Header público y cabecera profesional
Se respetan las dos variantes principales del header actual: la vista pública con acceso y CTA para profesionales, y la vista autenticada del profesional con enlaces operativos y salida.

* **Vista Pública:**  
  `Voy a Reformar` | `Soy profesional` | `Acceder` | `Publicar solicitud`

* **Vista Autenticada (Profesional):**  
  `Voy a Reformar` | `Contactos` | `Mis contactos` | `Mi perfil` | `Salir`
