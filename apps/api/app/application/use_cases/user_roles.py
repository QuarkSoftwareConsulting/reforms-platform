"""Gestion de roles y directorio de usuarios del admin.

El rol vive en `users.role`: el claim de Firebase solo crea el primer admin
(`SyncUserFromIdentity`). Asi un cambio de rol surte efecto en la siguiente
peticion, sin esperar a que caduque el token del usuario.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto import AdminUserItem, AdminUserListResult, RoleChangeResult
from app.application.ports import (
    AdminUserFilters,
    ClockPort,
    IdGeneratorPort,
    ProfessionalAccountRepositoryPort,
    ProfessionalRepositoryPort,
    UnitOfWork,
    UserRepositoryPort,
)
from app.application.use_cases.admin_operations import MAX_PAGE_SIZE
from app.domain.exceptions import LastAdminError, UserNotFoundError
from app.domain.models import User, UserRole, UserRoleEvent


@dataclass(slots=True)
class ChangeUserRole:
    """Da o quita el rol de admin, dejando constancia de quien lo hizo."""

    users: UserRepositoryPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork

    async def execute(
        self,
        *,
        user_id: UUID,
        role: UserRole,
        actor_user_id: UUID | None,
        note: str | None = None,
    ) -> RoleChangeResult:
        """`actor_user_id=None` lo hace el sistema (la CLI de bootstrap)."""
        async with self.uow:
            current = await self.users.get(user_id)
            if current is None:
                raise UserNotFoundError()
            # Degradar a un admin bloquea a TODOS los admins antes que la fila objetivo:
            # con solo la objetivo, dos admins degradandose a la vez dejarian cero.
            other_admins: list[UUID] | None = None
            if current.is_admin and role is not UserRole.ADMIN:
                other_admins = await self.users.lock_admins()
            user = await self.users.get_for_update(user_id)
            if user is None:
                raise UserNotFoundError()
            event = user.change_role(
                role,
                actor_user_id=actor_user_id,
                event_id=self.ids.new_id(),
                at=self.clock.now(),
                note=note,
            )
            if event is None:
                return RoleChangeResult(user=user, event=None)
            if event.from_role is UserRole.ADMIN:
                if other_admins is None:
                    # Lo promovieron entre la lectura y el bloqueo: se bloquea ahora.
                    other_admins = await self.users.lock_admins()
                if not [admin_id for admin_id in other_admins if admin_id != user.id]:
                    raise LastAdminError()
            await self.users.add_role_event(event)
            return RoleChangeResult(user=await self.users.update(user), event=event)


@dataclass(slots=True)
class ListUserRoleEvents:
    """Historial de roles de un usuario, del mas reciente al mas antiguo."""

    users: UserRepositoryPort

    async def execute(self, user_id: UUID) -> list[UserRoleEvent]:
        if await self.users.get(user_id) is None:
            raise UserNotFoundError()
        return await self.users.list_role_events(user_id)


@dataclass(slots=True)
class ListAdminUsers:
    """Directorio de usuarios con el resumen de su perfil profesional, si lo tienen."""

    users: UserRepositoryPort
    professionals: ProfessionalRepositoryPort
    accounts: ProfessionalAccountRepositoryPort
    clock: ClockPort

    async def execute(self, filters: AdminUserFilters) -> AdminUserListResult:
        normalized = AdminUserFilters(
            query=filters.query.strip() if filters.query and filters.query.strip() else None,
            role=filters.role,
            verification_status=filters.verification_status,
            limit=min(max(filters.limit, 1), MAX_PAGE_SIZE),
            offset=max(filters.offset, 0),
        )
        items = await self.describe(await self.users.list_admin(normalized))
        return AdminUserListResult(
            items=items,
            total=await self.users.count_admin(normalized),
            limit=normalized.limit,
            offset=normalized.offset,
        )

    async def describe(self, users: list[User]) -> list[AdminUserItem]:
        """Une cada usuario con su perfil y su cuenta, en el mismo orden."""
        profiles = await self.professionals.get_many_by_user_ids({user.id for user in users})
        accounts = await self.accounts.get_many({profile.id for profile in profiles.values()})
        now = self.clock.now()
        items: list[AdminUserItem] = []
        for user in users:
            profile = profiles.get(user.id)
            account = accounts.get(profile.id) if profile is not None else None
            items.append(
                AdminUserItem(
                    user=user,
                    professional=profile,
                    account=account,
                    account_active=account is not None and account.is_active(now),
                )
            )
        return items
