"""El admin gestiona el catalogo: categorias de oficio y sus servicios.

Lo que ya se uso no se borra, se desactiva: un lead antiguo sigue nombrando su
categoria y sus servicios, y un profesional sigue teniendolos en su perfil. Borrar
solo existe para corregir lo que se creo por error y nadie llego a usar.

El catalogo vive en la BD; la semilla (`scripts/seed.py`) solo lo carga en un entorno
vacio y no pisa lo que el admin cambio.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.ports import (
    CategoryRepositoryPort,
    IdGeneratorPort,
    PresignedUpload,
    StoragePort,
    UnitOfWork,
)
from app.domain.exceptions import (
    CatalogItemInUseError,
    CatalogSlugTakenError,
    CategoryNotFoundError,
    ServiceNotFoundError,
    ValidationError,
)
from app.domain.models import Category, Service
from app.domain.value_objects import Money

# Fotos de las tarjetas de la landing. Formatos que cualquier navegador pinta (sin HEIC)
# y un tamano razonable para una tarjeta.
CATALOG_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
CATALOG_IMAGE_MAX_BYTES = 5 * 1024 * 1024


def catalog_image_prefix(service_id: UUID) -> str:
    """Las fotos de un servicio llevan su id en la clave: no se adjunta la de otro."""
    return f"catalog/services/{service_id}"


@dataclass(slots=True)
class ListCatalogForAdmin:
    categories: CategoryRepositoryPort

    async def execute(self) -> list[Category]:
        return await self.categories.list_all()


@dataclass(slots=True)
class CreateCategory:
    categories: CategoryRepositoryPort
    ids: IdGeneratorPort
    uow: UnitOfWork

    async def execute(
        self, *, name_es: str, name_en: str, suggested_lead_price: Money, sort_order: int | None
    ) -> Category:
        async with self.uow:
            existing = await self.categories.list_all()
            category = Category.create(
                id=self.ids.new_id(),
                name_es=name_es,
                name_en=name_en,
                suggested_lead_price=suggested_lead_price,
                # Sin orden, al final: es donde el admin espera ver lo que acaba de crear.
                sort_order=(
                    sort_order
                    if sort_order is not None
                    else max((c.sort_order for c in existing), default=0) + 1
                ),
            )
            # Tambien contra las desactivadas: el slug es unico y una URL antigua no
            # debe pasar a apuntar a otro oficio.
            if any(c.slug == category.slug for c in existing):
                raise CatalogSlugTakenError()
            return await self.categories.add(category)


@dataclass(slots=True)
class UpdateCategory:
    """Renombra, reordena, (des)activa y cambia el precio sugerido de un oficio.

    El precio solo afecta a ventas futuras sin precio propio (AGENTS.md 4.9) y se
    queda en la divisa del oficio.
    """

    categories: CategoryRepositoryPort
    uow: UnitOfWork

    async def execute(
        self,
        *,
        category_id: UUID,
        name_es: str,
        name_en: str,
        suggested_price_cents: int,
        sort_order: int,
        active: bool,
    ) -> Category:
        async with self.uow:
            category = await _load(self.categories, category_id)
            category.edit(name_es=name_es, name_en=name_en, sort_order=sort_order, active=active)
            category.change_suggested_lead_price(
                Money(suggested_price_cents, category.suggested_lead_price.currency)
            )
            return await self.categories.update(category)


@dataclass(slots=True)
class DeleteCategory:
    categories: CategoryRepositoryPort
    uow: UnitOfWork

    async def execute(self, *, category_id: UUID) -> None:
        async with self.uow:
            await _load(self.categories, category_id)
            if await self.categories.is_in_use(category_id):
                raise CatalogItemInUseError()
            await self.categories.delete(category_id)


@dataclass(slots=True)
class CreateService:
    categories: CategoryRepositoryPort
    ids: IdGeneratorPort
    uow: UnitOfWork

    async def execute(self, *, category_id: UUID, name_es: str, name_en: str) -> Category:
        async with self.uow:
            category = await _load(self.categories, category_id)
            category.add_service(id=self.ids.new_id(), name_es=name_es, name_en=name_en)
            return await self.categories.update(category)


@dataclass(slots=True)
class UpdateService:
    categories: CategoryRepositoryPort
    uow: UnitOfWork

    async def execute(
        self,
        *,
        category_id: UUID,
        service_id: UUID,
        name_es: str,
        name_en: str,
        sort_order: int,
        active: bool,
        featured: bool = False,
        image_key: str | None = None,
        landing_name_es: str | None = None,
        landing_name_en: str | None = None,
    ) -> Category:
        if image_key and (
            not image_key.startswith(f"{catalog_image_prefix(service_id)}/") or ".." in image_key
        ):
            raise ValidationError("La foto no pertenece a este servicio")
        async with self.uow:
            category = await _load(self.categories, category_id)
            category.edit_service(
                service_id,
                name_es=name_es,
                name_en=name_en,
                sort_order=sort_order,
                active=active,
                featured=featured,
                image_key=image_key,
                landing_name_es=landing_name_es,
                landing_name_en=landing_name_en,
            )
            return await self.categories.update(category)


@dataclass(slots=True)
class DeleteService:
    categories: CategoryRepositoryPort
    uow: UnitOfWork

    async def execute(self, *, category_id: UUID, service_id: UUID) -> Service:
        async with self.uow:
            category = await _load(self.categories, category_id)
            category.service(service_id)  # que sea de esta categoria
            if await self.categories.is_service_in_use(service_id):
                raise CatalogItemInUseError()
            removed = category.remove_service(service_id)
            await self.categories.delete_service(service_id)
            return removed


@dataclass(slots=True)
class RequestCatalogImageUpload:
    """URL firmada para que el navegador del admin suba la foto de un servicio."""

    categories: CategoryRepositoryPort
    storage: StoragePort

    async def execute(
        self,
        *,
        category_id: UUID,
        service_id: UUID,
        filename: str,
        content_type: str,
        size_bytes: int | None,
    ) -> PresignedUpload:
        normalized = content_type.split(";")[0].strip().lower()
        if normalized not in CATALOG_IMAGE_TYPES:
            raise ValidationError(f"Tipo de imagen no permitido: {content_type}")
        if size_bytes is not None and size_bytes > CATALOG_IMAGE_MAX_BYTES:
            raise ValidationError("La foto supera el maximo de 5 MB")
        category = await _load(self.categories, category_id)
        category.service(service_id)
        return await self.storage.create_presigned_upload(
            key_prefix=catalog_image_prefix(service_id),
            filename=filename,
            content_type=normalized,
        )


@dataclass(slots=True)
class GetLandingServiceImage:
    """URL de la foto de un servicio destacado, resuelta en cada peticion.

    La landing se cachea un dia y el bucket da URLs firmadas que caducan en minutos:
    la pagina enlaza una URL estable del API y esta la traduce a una vigente.
    """

    categories: CategoryRepositoryPort
    storage: StoragePort

    async def execute(self, *, service_id: UUID) -> str:
        for category in await self.categories.list_active():
            for service in category.services:
                if service.id == service_id and service.on_landing and service.image_key:
                    return self.storage.public_url(service.image_key)
        raise ServiceNotFoundError()


async def _load(categories: CategoryRepositoryPort, category_id: UUID) -> Category:
    category = await categories.get(category_id)
    if category is None:
        raise CategoryNotFoundError()
    return category
