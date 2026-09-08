---
name: nuevo-caso-de-uso
description: Añade una interaccion de negocio nueva al backend hexagonal de Reforma Hub recorriendo las siete capas en el orden correcto (puerto, caso de uso, fake, test, adaptador, composition root, endpoint) sin dejarse ninguna. Usar al implementar cualquier funcionalidad nueva del backend, un endpoint nuevo, una regla de negocio nueva, o al integrar un servicio externo; tambien cuando falle un test con "Can't instantiate abstract class" o cuando un endpoint nuevo de 500 por falta de cableado.
---

# Añadir un caso de uso

Siete archivos en orden. Saltarse uno produce fallos concretos y conocidos:

| Si te olvidas de… | Sintoma |
|---|---|
| el fake del puerto | `TypeError: Can't instantiate abstract class InMemory…` en **toda** la suite |
| el composition root | el endpoint da 500 con `AttributeError` en `RequestContainer` |
| el `_round_trip()` del fake | los tests de concurrencia pasan sin probar nada |
| registrar el router | el endpoint devuelve 404 |

Las plantillas de cada archivo estan en
[`references/plantillas.md`](references/plantillas.md) — cargalas cuando vayas a escribir
código, no antes.

## Antes de escribir: dos preguntas

**¿Es de verdad un caso de uso?** Si solo transforma datos sin decidir nada, es un helper.
Si expresa una regla del negocio ("un lead se vende como maximo a 3 profesionales"), va al
**dominio**, no al caso de uso. El caso de uso *orquesta*: carga, delega la decision a la
entidad, persiste.

**¿Necesita un servicio externo nuevo?** Entonces el puerto va primero, con el vocabulario
del negocio y no el de la libreria: `create_checkout_session`, no `stripe_create_session`.
Un puerto que menciona la tecnologia ya ha filtrado la dependencia.

## Los siete pasos

### 1 · El puerto (solo si hace falta uno nuevo)

`app/application/ports/` — clase abstracta con `@abstractmethod`. Exportala en
`ports/__init__.py` y en su `__all__`.

> Añadir un metodo a un puerto existente **rompe todos los fakes** que lo implementan.
> Actualizalos en el mismo cambio (paso 3), no despues.

### 2 · El caso de uso

`app/application/use_cases/` — un archivo por interaccion, `@dataclass(slots=True)` con los
puertos como campos y un solo metodo `execute()`. Sin estado entre llamadas.

Reglas que mypy strict vigila en esta capa:

- Cero imports de `sqlalchemy`, `fastapi`, `stripe`, `firebase_admin`, `boto3`, `pydantic`.
- Cero `datetime.now()`: la hora viene de `ClockPort`. Los UUID, de `IdGeneratorPort`.
- Las entradas y salidas complejas son dataclasses en `application/dto/`, no dicts.
- Si escribe, envuelve las escrituras en `async with self.uow:`.

Exportalo en `use_cases/__init__.py` y su `__all__`.

### 3 · Los fakes

`tests/fakes/` — implementa el puerto nuevo (o el metodo nuevo en el fake existente).
**Empieza cada metodo async con `await _round_trip()`**: sin ese punto de cesion al event
loop las corrutinas corren de forma efectivamente atomica y cualquier test de concurrencia
pasa sin probar nada.

Añade el caso de uso a la clase `World` de `tests/conftest.py` (campo + construccion en
`__post_init__`) para que los tests lo tengan cableado.

### 4 · Los tests con fakes

`tests/unit/use_cases/` — cubre el camino feliz, cada error de negocio que puede lanzar, y
la concurrencia si toca plazas o dinero.

**Si el caso de uso no se puede probar aqui sin base de datos, las dependencias estan mal
puestas.** Vuelve al paso 2 antes de seguir.

Para un test de concurrencia: escribelo, desactiva temporalmente el mecanismo que protege
(el `FOR UPDATE`, por ejemplo) y **comprueba que el test falla**. Un test de carrera que
nunca se ha visto fallar no vale nada.

### 5 · El adaptador

`app/infrastructure/adapters/` — la implementacion real. Si es un SDK externo:

- Envuelve las llamadas sincronas en `asyncio.to_thread(...)`.
- Traduce **toda** excepcion de la libreria a un error de dominio. Dejar escapar una se
  convierte en un 500 sin contexto para el usuario.
- Busca cómo probarlo de verdad sin credenciales (ver `tests/unit/test_stripe_adapter.py`,
  que firma eventos con HMAC). Los fakes no detectan desajustes con los SDK.

Si es un repositorio, lee la seccion "Repositorios" de `apps/api/AGENTS.md`: hay tres
trampas de SQLAlchemy async que muerden siempre.

### 6 · El composition root

`app/infrastructure/api/dependencies.py` — una `@property` en `RequestContainer` que
construye el caso de uso con sus adaptadores. **Es el unico sitio del backend donde se
elige implementacion concreta.** Si instancias un adaptador en otro lado, el cambio esta mal.

Si el adaptador es de proceso (una conexion, un cliente HTTP), va en `Infrastructure` y se
crea en `build_infrastructure()` de `main.py`, no por peticion.

### 7 · El endpoint y su test

`app/infrastructure/api/v1/` + schemas Pydantic en `api/schemas/` + serializador en
`api/serializers.py`.

- El endpoint **no lleva logica**: valida, llama al caso de uso, serializa.
- Elige la dependencia de auth correcta: `CurrentProfessionalDep`, `AdminDep` o nada.
- Los errores nuevos necesitan su `code` en las traducciones (`es.json` **y** `en.json`).
- Si devuelve datos de un lead, el schema de salida **no puede tener campos de contacto**.

Test en `tests/api/`, con Firebase y Stripe falsos. Si el endpoint toca leads, incluye una
assertion de que la respuesta no contiene la PII del cliente.

## Cerrar el cambio

```bash
cd apps/api && uv run ruff check . && uv run mypy app
cd ../.. && pnpm lint && pnpm test
```

Y si tocaste leads, compras o pagos, ejecuta la skill `verificar-flujo-compra`.

## Checklist

- [ ] Puerto exportado en `ports/__init__.py` y su `__all__`
- [ ] Caso de uso sin imports de infraestructura, sin `datetime.now()`, exportado
- [ ] Fakes actualizados, con `await _round_trip()` en cada metodo async
- [ ] `World` de `conftest.py` cableado
- [ ] Tests de camino feliz + cada error de negocio (+ concurrencia si aplica)
- [ ] Adaptador traduce las excepciones de la libreria a errores de dominio
- [ ] `@property` en `RequestContainer`
- [ ] Router registrado en `v1/__init__.py`
- [ ] Codigos de error nuevos traducidos en `es.json` y `en.json`
- [ ] Migracion si cambio el esquema (skill `nueva-migracion`)
- [ ] `pnpm lint && pnpm test` en verde
