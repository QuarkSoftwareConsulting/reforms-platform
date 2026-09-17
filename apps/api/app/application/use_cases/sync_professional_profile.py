"""Casos de uso de identidad y perfil profesional.

Firebase es la fuente de verdad de la autenticacion; nosotros mantenemos un
espejo local (`users`) para poder relacionar compras, leads y roles sin depender
de llamadas al proveedor en cada peticion.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto import ProfessionalProfile, UpsertProfessionalInput
from app.application.ports import (
    AuthenticatedIdentity,
    CategoryRepositoryPort,
    ClockPort,
    IdGeneratorPort,
    PostalCodeRepositoryPort,
    ProfessionalRepositoryPort,
    UnitOfWork,
    UserRepositoryPort,
)
from app.domain.exceptions import (
    CategoryNotFoundError,
    ProfessionalNotFoundError,
    UnknownPostalCodeError,
    ValidationError,
)
from app.domain.models import Professional, User, UserRole
from app.domain.value_objects import Email, PhoneNumber, PostalCode


@dataclass(slots=True)
class SyncUserFromIdentity:
    """Crea o actualiza el usuario local a partir de la identidad de Firebase."""

    users: UserRepositoryPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork

    async def execute(self, identity: AuthenticatedIdentity) -> User:
        existing = await self.users.get_by_firebase_uid(identity.provider_uid)
        email = Email(identity.email) if identity.email else None

        if existing is not None:
            changed = False
            if email is not None and existing.email != email:
                existing.email = email
                changed = True
            if identity.display_name and existing.display_name != identity.display_name:
                existing.display_name = identity.display_name
                changed = True
            # El claim de admin manda: se gestiona desde la consola de Firebase.
            desired_role = UserRole.ADMIN if identity.is_admin_claim else UserRole.PROFESSIONAL
            if desired_role is not existing.role:
                existing.role = desired_role
                changed = True
            if changed:
                async with self.uow:
                    return await self.users.update(existing)
            return existing

        if email is None:
            raise ValidationError("La cuenta de Firebase no tiene email asociado")

        user = User(
            id=self.ids.new_id(),
            firebase_uid=identity.provider_uid,
            email=email,
            role=UserRole.ADMIN if identity.is_admin_claim else UserRole.PROFESSIONAL,
            created_at=self.clock.now(),
            display_name=identity.display_name,
        )
        async with self.uow:
            return await self.users.add(user)


@dataclass(slots=True)
class UpsertProfessionalProfile:
    """Crea o actualiza el perfil profesional (zona base, radio y oficios)."""

    professionals: ProfessionalRepositoryPort
    categories: CategoryRepositoryPort
    postal_codes: PostalCodeRepositoryPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork

    async def execute(self, *, user_id: UUID, data: UpsertProfessionalInput) -> Professional:
        postal_code = PostalCode(data.postal_code)
        info = await self.postal_codes.get(postal_code)
        if info is None:
            raise UnknownPostalCodeError(f"Codigo postal no reconocido: {postal_code}")

        if data.category_ids:
            found = {c.id for c in await self.categories.get_many(data.category_ids) if c.active}
            missing = data.category_ids - found
            if missing:
                raise CategoryNotFoundError(
                    f"Categorias inexistentes o inactivas: {sorted(str(m) for m in missing)}"
                )

        existing = await self.professionals.get_by_user_id(user_id)
        if existing is None:
            professional = Professional(
                id=self.ids.new_id(),
                user_id=user_id,
                business_name=data.business_name,
                phone=PhoneNumber(data.phone),
                base_postal_code=info.code,
                base_coordinates=info.coordinates,
                service_radius_km=data.service_radius_km,
                created_at=self.clock.now(),
                city=info.city,
                province=info.province,
                category_ids=set(data.category_ids),
            )
            async with self.uow:
                return await self.professionals.add(professional)

        existing.business_name = data.business_name
        existing.phone = PhoneNumber(data.phone)
        existing.base_postal_code = info.code
        existing.base_coordinates = info.coordinates
        existing.service_radius_km = data.service_radius_km
        existing.city = info.city
        existing.province = info.province
        existing.category_ids = set(data.category_ids)
        # Revalida los invariantes tras la mutacion (radio, nombre no vacio).
        existing.__post_init__()

        async with self.uow:
            return await self.professionals.update(existing)


@dataclass(slots=True)
class GetProfessionalProfile:
    professionals: ProfessionalRepositoryPort
    categories: CategoryRepositoryPort

    async def execute(self, *, user_id: UUID) -> ProfessionalProfile:
        professional = await self.professionals.get_by_user_id(user_id)
        if professional is None:
            raise ProfessionalNotFoundError("Todavia no has creado tu perfil profesional")
        categories = await self.categories.get_many(professional.category_ids)
        return ProfessionalProfile(professional=professional, categories=categories)
