"""Categoria de oficio, sus servicios y su precio sugerido por lead.

El catalogo tiene dos niveles (Etapa 1): categoria (Reformas, Instaladores...) y
servicio (Reformas de banos, Aerotermia...). El cliente elige una categoria y, de
forma opcional, los servicios que necesita de ella.

El admin lo gestiona desde el panel. El slug sale del nombre al crear y no cambia al
renombrar: lo usan las URL (la landing enlaza oficios por slug) y el SEO por oficio.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from uuid import UUID

from app.domain.exceptions import (
    CatalogNameInvalidError,
    CatalogSlugTakenError,
    InvalidServiceError,
    ServiceNotFoundError,
    ValidationError,
)
from app.domain.models.pricing import assert_sellable_price
from app.domain.value_objects import Money

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SERVICES_PER_LEAD = 10

# Limites de las columnas: un nombre mas largo no cabe en la BD.
CATEGORY_NAME_MAX_LENGTH = 120
SERVICE_NAME_MAX_LENGTH = 160
CATEGORY_SLUG_MAX_LENGTH = 60
SERVICE_SLUG_MAX_LENGTH = 80


def slugify(name: str, *, max_length: int) -> str:
    """Slug de un nombre: ASCII, minusculas y guiones ("Banos y Cocinas" -> "banos-y-cocinas")."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:max_length].rstrip("-")


def clean_name(name: str, *, max_length: int) -> str:
    """Nombre de categoria o servicio sin espacios sobrantes; con letras o numeros."""
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > max_length or not slugify(cleaned, max_length=max_length):
        raise CatalogNameInvalidError(min=1, max=max_length)
    return cleaned


@dataclass(frozen=True, slots=True)
class Service:
    """Servicio concreto dentro de una categoria."""

    id: UUID
    slug: str
    name_es: str
    name_en: str
    sort_order: int = 0
    active: bool = True

    def __post_init__(self) -> None:
        if not _SLUG_RE.match(self.slug):
            raise ValidationError(f"Slug de servicio invalido: {self.slug!r}")

    def name(self, locale: str) -> str:
        return self.name_en if locale.lower().startswith("en") else self.name_es

    @classmethod
    def create(cls, *, id: UUID, name_es: str, name_en: str, sort_order: int) -> Service:
        name_es = clean_name(name_es, max_length=SERVICE_NAME_MAX_LENGTH)
        return cls(
            id=id,
            slug=slugify(name_es, max_length=SERVICE_SLUG_MAX_LENGTH),
            name_es=name_es,
            name_en=clean_name(name_en, max_length=SERVICE_NAME_MAX_LENGTH),
            sort_order=sort_order,
        )


@dataclass(slots=True)
class Category:
    """Oficio (carpinteria, fontaneria...) con el precio de referencia de sus leads.

    `suggested_lead_price` NO es el precio de venta: es el que se aplica cuando el
    admin no ha fijado uno propio para un contacto concreto. El precio real de una
    venta lo resuelve `Lead.sale_price()`.
    """

    id: UUID
    slug: str
    name_es: str
    name_en: str
    suggested_lead_price: Money
    active: bool = True
    sort_order: int = 0
    services: list[Service] = field(default_factory=list)
    """Todos, tambien los retirados: un lead antiguo sigue nombrando el suyo."""

    def __post_init__(self) -> None:
        self.slug = self.slug.strip().lower()
        if not _SLUG_RE.match(self.slug):
            raise ValidationError(f"Slug de categoria invalido: {self.slug!r}")
        assert_sellable_price(self.suggested_lead_price)

    def name(self, locale: str) -> str:
        return self.name_en if locale.lower().startswith("en") else self.name_es

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        name_es: str,
        name_en: str,
        suggested_lead_price: Money,
        sort_order: int,
    ) -> Category:
        name_es = clean_name(name_es, max_length=CATEGORY_NAME_MAX_LENGTH)
        return cls(
            id=id,
            slug=slugify(name_es, max_length=CATEGORY_SLUG_MAX_LENGTH),
            name_es=name_es,
            name_en=clean_name(name_en, max_length=CATEGORY_NAME_MAX_LENGTH),
            suggested_lead_price=suggested_lead_price,
            sort_order=sort_order,
        )

    def edit(self, *, name_es: str, name_en: str, sort_order: int, active: bool) -> None:
        """Renombra, reordena o (des)activa. El slug no cambia: lo usan las URL.

        Desactivar la retira del formulario de publicar y del perfil; los leads y los
        profesionales que ya la tienen la siguen mostrando.
        """
        self.name_es = clean_name(name_es, max_length=CATEGORY_NAME_MAX_LENGTH)
        self.name_en = clean_name(name_en, max_length=CATEGORY_NAME_MAX_LENGTH)
        self.sort_order = sort_order
        self.active = active

    def service(self, service_id: UUID) -> Service:
        found = next((s for s in self.services if s.id == service_id), None)
        if found is None:
            raise ServiceNotFoundError()
        return found

    def add_service(self, *, id: UUID, name_es: str, name_en: str) -> Service:
        """Anade un servicio al final de la categoria.

        El slug es unico dentro de la categoria, contando los retirados: un lead
        antiguo puede seguir nombrando el retirado, y dos con el mismo slug se
        confundirian en la URL.
        """
        sort_order = max((s.sort_order for s in self.services), default=0) + 1
        service = Service.create(id=id, name_es=name_es, name_en=name_en, sort_order=sort_order)
        if any(s.slug == service.slug for s in self.services):
            raise CatalogSlugTakenError()
        self.services.append(service)
        return service

    def edit_service(
        self, service_id: UUID, *, name_es: str, name_en: str, sort_order: int, active: bool
    ) -> Service:
        """Renombra, reordena o (des)activa un servicio. Su slug no cambia."""
        current = self.service(service_id)
        updated = replace(
            current,
            name_es=clean_name(name_es, max_length=SERVICE_NAME_MAX_LENGTH),
            name_en=clean_name(name_en, max_length=SERVICE_NAME_MAX_LENGTH),
            sort_order=sort_order,
            active=active,
        )
        self.services = [updated if s.id == service_id else s for s in self.services]
        return updated

    def remove_service(self, service_id: UUID) -> Service:
        """Lo quita de la categoria. Solo para un servicio que nada usa (lo decide el caso
        de uso): lo que ya se uso se desactiva."""
        removed = self.service(service_id)
        self.services = [s for s in self.services if s.id != service_id]
        return removed

    @property
    def active_services(self) -> list[Service]:
        """Los que se ofrecen hoy en el formulario, en el orden del catalogo."""
        return sorted((s for s in self.services if s.active), key=lambda s: s.sort_order)

    def resolve_services(self, service_ids: Sequence[UUID]) -> list[Service]:
        """Valida los servicios que el cliente eligio para esta categoria.

        Quita duplicados conservando el orden. Rechaza servicios de otra categoria o
        retirados del catalogo: el profesional filtra por ellos y un servicio ajeno
        haria aparecer la solicitud donde no toca.
        """
        unique = list(dict.fromkeys(service_ids))
        if len(unique) > MAX_SERVICES_PER_LEAD:
            raise ValidationError(f"Maximo {MAX_SERVICES_PER_LEAD} servicios por solicitud")
        offered = {s.id: s for s in self.active_services}
        missing = [sid for sid in unique if sid not in offered]
        if missing:
            raise InvalidServiceError(
                f"Servicios que no pertenecen a la categoria {self.slug}: {missing}"
            )
        return [offered[sid] for sid in unique]

    def services_named(self, service_ids: Sequence[UUID]) -> list[Service]:
        """Los servicios de un lead, en su orden, aunque hoy esten retirados."""
        by_id = {s.id: s for s in self.services}
        return [by_id[sid] for sid in service_ids if sid in by_id]

    def change_suggested_lead_price(self, price: Money) -> None:
        """Actualiza el precio de referencia del oficio.

        Solo afecta a las ventas futuras sin precio propio: las compras ya creadas
        guardan su importe y los leads con precio fijado por el admin lo conservan.
        """
        assert_sellable_price(price)
        self.suggested_lead_price = price
