# Plantillas de los siete archivos

Ejemplo hilado: **archivar un lead que el cliente pide retirar**. Sustituye los nombres,
pero conserva la forma — es la que tiene el resto del backend.

Cada bloque indica su archivo. Comentarios y docstrings en español, sin acentos
(convencion del proyecto: el codigo fuente es ASCII puro).

---

## 1 · Puerto — `app/application/ports/notifications_port.py`

Solo si la interaccion necesita un servicio externo que aun no tiene puerto.

```python
"""Puerto de notificaciones al cliente."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Notification:
    """Aviso ya traducido y listo para enviar."""

    recipient: str
    subject: str
    body: str


class NotificationPort(ABC):
    @abstractmethod
    async def send(self, notification: Notification) -> None:
        """Envia el aviso. Lanza `NotificationError` si no se pudo entregar."""
```

Exportar en `ports/__init__.py`:

```python
from app.application.ports.notifications_port import Notification, NotificationPort

__all__ = [
    # ...
    "Notification",
    "NotificationPort",
]
```

---

## 2 · Caso de uso — `app/application/use_cases/archive_lead.py`

```python
"""Caso de uso: archivar un lead a peticion del cliente."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.ports import ClockPort, LeadRepositoryPort, UnitOfWork
from app.domain.exceptions import LeadNotFoundError
from app.domain.models import Lead


@dataclass(slots=True)
class ArchiveLead:
    """Retira un lead del explorador conservando las compras ya realizadas.

    No libera las plazas vendidas: los datos del cliente ya se cedieron a esos
    profesionales y su compra sigue siendo valida.
    """

    leads: LeadRepositoryPort
    clock: ClockPort
    uow: UnitOfWork

    async def execute(self, *, lead_id: UUID, reason: str) -> Lead:
        async with self.uow:
            lead = await self.leads.get_for_update(lead_id)
            if lead is None:
                raise LeadNotFoundError()

            # La decision es del dominio; el caso de uso solo orquesta.
            lead.archive(reason=reason, at=self.clock.now())
            return await self.leads.update(lead)
```

Exportar en `use_cases/__init__.py` y su `__all__`.

> Si la regla ("un lead pagado no se puede archivar sin motivo") es de negocio, vive en
> `Lead.archive()`, no aqui. El caso de uso no decide: delega.

---

## 3 · Fake — `tests/fakes/notifications.py`

```python
from __future__ import annotations

from app.application.ports import Notification, NotificationPort
from tests.fakes.repositories import _round_trip


class FakeNotifier(NotificationPort):
    """Guarda los avisos enviados para poder afirmar sobre ellos."""

    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[Notification] = []
        self.fail = fail

    async def send(self, notification: Notification) -> None:
        # Modela el viaje de red: sin este punto de cesion al event loop los tests
        # de concurrencia pasarian sin probar nada.
        await _round_trip()
        if self.fail:
            raise RuntimeError("El proveedor de avisos no responde")
        self.sent.append(notification)
```

Exportar en `tests/fakes/__init__.py`.

Cablear en `tests/conftest.py`:

```python
@dataclass
class World:
    # ...campos existentes...
    notifier: FakeNotifier

    archive_lead: ArchiveLead = field(init=False)

    def __post_init__(self) -> None:
        # ...cableado existente...
        self.archive_lead = ArchiveLead(
            leads=self.leads, clock=self.clock, uow=self.uow
        )
```

Y en la fixture `world`, pasar `notifier=FakeNotifier()`.

---

## 4 · Tests — `tests/unit/use_cases/test_archive_lead.py`

```python
"""Tests del archivado de leads."""

from uuid import uuid4

import pytest

from app.domain.exceptions import LeadNotFoundError
from app.domain.models import Category, LeadStatus
from tests.conftest import World
from tests.factories import make_lead


class TestArchiveLead:
    async def test_archived_lead_disappears_from_the_explorer(
        self, world: World, carpentry: Category
    ) -> None:
        lead = make_lead(category_id=carpentry.id)
        world.leads.items[lead.id] = lead
        professional = world.add_professional(category_ids={carpentry.id})

        await world.archive_lead.execute(lead_id=lead.id, reason="peticion del cliente")

        result = await world.list_leads.execute(professional_id=professional.id)
        assert [i.lead.id for i in result.items] == []
        assert lead.status is LeadStatus.DISABLED

    async def test_keeps_slots_of_professionals_who_already_paid(
        self, world: World, carpentry: Category
    ) -> None:
        """El dato personal ya se cedio: la plaza no se reutiliza."""
        lead = make_lead(category_id=carpentry.id, purchases_count=1)
        world.leads.items[lead.id] = lead

        await world.archive_lead.execute(lead_id=lead.id, reason="duplicado")

        assert lead.purchases_count == 1

    async def test_unknown_lead_raises(self, world: World) -> None:
        with pytest.raises(LeadNotFoundError):
            await world.archive_lead.execute(lead_id=uuid4(), reason="x")
```

Si el caso de uso toca plazas o dinero, añade el test de concurrencia:

```python
    async def test_two_simultaneous_calls_are_serialized(
        self, world: World, carpentry: Category
    ) -> None:
        import asyncio

        lead = make_lead(category_id=carpentry.id, max_purchases=1)
        world.leads.items[lead.id] = lead
        a = world.add_professional(category_ids={carpentry.id})
        b = world.add_professional(category_ids={carpentry.id})

        results = await asyncio.gather(
            world.start_purchase.execute(lead_id=lead.id, professional_id=a.id),
            world.start_purchase.execute(lead_id=lead.id, professional_id=b.id),
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, BaseException)]
        assert len(successes) == 1
        # Prueba de que el bloqueo se ejercito de verdad, no que hubo suerte.
        assert world.leads.lock_waits == 1
```

Y **comprueba que falla** desactivando el `await lock.acquire()` del fake antes de darlo
por bueno.

---

## 5 · Adaptador — `app/infrastructure/adapters/notifications/brevo_adapter.py`

```python
"""Adaptador de Brevo para avisos por email."""

from __future__ import annotations

import asyncio
import logging

import some_sdk

from app.application.ports import Notification, NotificationPort
from app.domain.exceptions import NotificationError

logger = logging.getLogger(__name__)


class BrevoNotifier(NotificationPort):
    def __init__(self, *, api_key: str, sender: str) -> None:
        self._client = some_sdk.Client(api_key) if api_key else None
        self._sender = sender

    async def send(self, notification: Notification) -> None:
        if self._client is None:
            logger.error("brevo_sin_configurar: falta BREVO_API_KEY")
            raise NotificationError()
        try:
            # El SDK es sincrono: a un hilo para no bloquear el event loop.
            await asyncio.to_thread(
                self._client.send,
                to=notification.recipient,
                subject=notification.subject,
                body=notification.body,
            )
        except some_sdk.SdkError as exc:
            # Nunca dejar escapar una excepcion de libreria: se convertiria en un
            # 500 sin contexto. Y nunca registrar la PII del destinatario.
            logger.error("brevo_envio_fallido: %s", exc, exc_info=True)
            raise NotificationError() from exc
```

---

## 6 · Composition root — `app/infrastructure/api/dependencies.py`

Por peticion, en `RequestContainer`:

```python
    @property
    def archive_lead(self) -> ArchiveLead:
        return ArchiveLead(
            leads=self.leads, clock=self.infra.clock, uow=self.uow
        )
```

Si el adaptador es de proceso (cliente HTTP, pool de conexiones), va en `Infrastructure` y
se construye una sola vez en `build_infrastructure()` de `main.py`:

```python
@dataclass(slots=True)
class Infrastructure:
    # ...
    notifier: NotificationPort
```

```python
def build_infrastructure(settings: Settings) -> Infrastructure:
    return Infrastructure(
        # ...
        notifier=BrevoNotifier(
            api_key=settings.brevo_api_key, sender=settings.brevo_sender
        ),
    )
```

Y en los tests de API (`tests/api/conftest.py`), sustituyelo por el fake.

---

## 7 · Endpoint — `app/infrastructure/api/v1/leads.py`

Schema en `api/schemas/leads.py`:

```python
class ArchiveLeadIn(ApiModel):
    reason: str = Field(min_length=3, max_length=500)


class ArchivedLeadOut(ApiModel):
    id: UUID
    status: str
```

Endpoint:

```python
@router.post(
    "/leads/{lead_id}/archive",
    response_model=ArchivedLeadOut,
    summary="Archivar una solicitud",
)
async def archive_lead(
    lead_id: UUID,
    payload: ArchiveLeadIn,
    container: ContainerDep,
    _admin: AdminDep,
) -> ArchivedLeadOut:
    """Sin logica: valida, delega y serializa."""
    lead = await container.archive_lead.execute(
        lead_id=lead_id, reason=payload.reason
    )
    return ArchivedLeadOut(id=lead.id, status=lead.status.value)
```

Si el router es nuevo, registralo en `v1/__init__.py`:

```python
api_router.include_router(admin.router)
```

Test en `tests/api/test_lead_lifecycle.py`:

```python
    async def test_archiving_requires_admin(
        self, api: AsyncClient, carpentry_category: Category, pro_auth: dict[str, str]
    ) -> None:
        created = await publish_lead(api, carpentry_category)
        response = await api.post(
            f"/leads/{created['id']}/archive",
            json={"reason": "duplicado"},
            headers=pro_auth,
        )
        assert response.status_code == 403
        assert response.json()["code"] == "PERMISSION_DENIED"

    async def test_archived_lead_is_not_listed(
        self,
        api: AsyncClient,
        carpentry_category: Category,
        admin_auth: dict[str, str],
        pro_auth: dict[str, str],
    ) -> None:
        created = await publish_lead(api, carpentry_category)
        await create_profile(api, carpentry_category, pro_auth)
        await api.post(
            f"/leads/{created['id']}/archive",
            json={"reason": "duplicado"},
            headers=admin_auth,
        )

        listing = await api.get("/leads", headers=pro_auth)
        assert listing.json()["total"] == 0
        # El endpoint no puede filtrar datos del cliente en ningun caso.
        assert CLIENT_PHONE not in listing.text
```

---

## Codigos de error nuevos

Tres archivos, siempre los tres:

```python
# app/domain/exceptions/__init__.py
class NotificationError(DomainError):
    """No hemos podido enviar el aviso."""

    code = "NOTIFICATION_FAILED"
    status = 503
```

```jsonc
// apps/web/messages/es.json → "errors": { "NOTIFICATION_FAILED": "..." }
// apps/web/messages/en.json → la misma clave, traducida
```

Comprobar la paridad de claves:

```bash
cd apps/web && node -e "
const fs=require('fs'), keys=(o,p='')=>Object.entries(o).flatMap(([k,v])=>
  typeof v==='object'&&v!==null?keys(v,p+k+'.'):[p+k]);
const es=new Set(keys(JSON.parse(fs.readFileSync('messages/es.json'))));
const en=new Set(keys(JSON.parse(fs.readFileSync('messages/en.json'))));
console.log({es:es.size, en:en.size, falta:[...es].filter(k=>!en.has(k))});"
```
