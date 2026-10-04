"""Casos de uso de identidad y perfil profesional.

Firebase es la fuente de verdad de la autenticacion; nosotros mantenemos un
espejo local (`users`) para poder relacionar compras, leads y roles sin depender
de llamadas al proveedor en cada peticion. El rol, en cambio, es nuestro: Firebase
solo lo propone al crear la cuenta.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto import ProfessionalProfile, UpsertProfessionalInput
from app.application.parsing import parse_postal_code
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
from app.application.use_cases.phone_verification import parse_mobile
from app.application.use_cases.professional_files import assert_own_key, media_prefix
from app.domain.exceptions import (
    CategoryNotFoundError,
    InvalidServiceError,
    InvalidTaxIdError,
    ProfessionalNotFoundError,
    UnknownPostalCodeError,
    ValidationError,
)
from app.domain.models import MADRID, Professional, ServiceArea, User, UserRole
from app.domain.value_objects import Email, TaxId


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
            # El rol NO se sincroniza: vive en nuestra BD y lo cambia un admin desde el
            # panel (`ChangeUserRole`). Si el claim mandara, un admin degradado
            # recuperaria el acceso en su siguiente peticion.
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
            # El claim solo cuenta al crear la cuenta: es como se da de alta el primer admin.
            role=UserRole.ADMIN if identity.is_admin_claim else UserRole.PROFESSIONAL,
            created_at=self.clock.now(),
            display_name=identity.display_name,
        )
        async with self.uow:
            return await self.users.add(user)


@dataclass(slots=True)
class UpsertProfessionalProfile:
    """Crea o actualiza el perfil profesional: zona, oficios, servicios y datos de alta.

    El formulario envia el perfil completo en cada guardado. Tipo, razon social y NIF
    se pueden cambiar solo hasta enviar el alta a revision (`set_identity`).
    """

    professionals: ProfessionalRepositoryPort
    categories: CategoryRepositoryPort
    postal_codes: PostalCodeRepositoryPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork
    service_area: ServiceArea = MADRID

    async def execute(self, *, user_id: UUID, data: UpsertProfessionalInput) -> Professional:
        postal_code = parse_postal_code(data.postal_code)
        # Cobertura de la Etapa 1 tambien para la base del profesional (F02).
        self.service_area.assert_covers(postal_code)
        info = await self.postal_codes.get(postal_code)
        if info is None:
            raise UnknownPostalCodeError(f"Codigo postal no reconocido: {postal_code}")

        phone = parse_mobile(data.phone)
        tax_id = self._parse_tax_id(data.tax_id)
        await self._assert_services(data.category_ids, data.service_ids)

        async with self.uow:
            existing = await self.professionals.get_by_user_id(user_id)
            if existing is not None:
                # Bloqueado: `update` reescribe el perfil entero, estado del alta
                # incluido. Sin el bloqueo, guardar el perfil mientras el admin aprueba
                # o rechaza devolveria el alta al estado leido.
                existing = await self.professionals.get_for_update(existing.id)
            professional = existing or Professional(
                id=self.ids.new_id(),
                user_id=user_id,
                business_name=data.business_name,
                phone=phone,
                base_postal_code=info.code,
                base_coordinates=info.coordinates,
                service_radius_km=data.service_radius_km,
                created_at=self.clock.now(),
            )
            self._assert_own_media(professional.id, data)

            professional.business_name = data.business_name
            professional.phone = phone
            professional.base_postal_code = info.code
            professional.base_coordinates = info.coordinates
            professional.service_radius_km = data.service_radius_km
            professional.city = info.city
            professional.province = info.province
            professional.category_ids = set(data.category_ids)
            professional.service_ids = set(data.service_ids)
            professional.address = data.address
            professional.profile_photo_key = data.profile_photo_key
            professional.logo_key = data.logo_key
            professional.work_photo_keys = list(data.work_photo_keys)
            professional.set_identity(
                professional_type=data.professional_type,
                legal_name=data.legal_name,
                tax_id=tax_id,
            )
            # Revalida los invariantes tras la mutacion (radio, nombre, fotos, CIF).
            professional.__post_init__()

            if existing is None:
                return await self.professionals.add(professional)
            return await self.professionals.update(professional)

    @staticmethod
    def _parse_tax_id(raw: str | None) -> TaxId | None:
        if raw is None or not raw.strip():
            return None
        try:
            return TaxId(raw)
        except ValueError as exc:
            raise InvalidTaxIdError() from exc

    async def _assert_services(self, category_ids: set[UUID], service_ids: set[UUID]) -> None:
        categories = await self.categories.get_many(category_ids) if category_ids else []
        active = [c for c in categories if c.active]
        missing = category_ids - {c.id for c in active}
        if missing:
            raise CategoryNotFoundError(
                f"Categorias inexistentes o inactivas: {sorted(str(m) for m in missing)}"
            )
        # Cada servicio tiene que ser de uno de los oficios elegidos.
        offered = {s.id for c in active for s in c.active_services}
        if not service_ids <= offered:
            raise InvalidServiceError("Hay servicios que no pertenecen a los oficios elegidos")

    @staticmethod
    def _assert_own_media(professional_id: UUID, data: UpsertProfessionalInput) -> None:
        prefix = media_prefix(professional_id)
        keys = [data.profile_photo_key, data.logo_key, *data.work_photo_keys]
        for key in keys:
            if key is not None:
                assert_own_key(key, prefix)


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
