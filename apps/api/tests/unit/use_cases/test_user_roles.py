"""Roles gestionados desde el panel: la BD manda y nunca se queda sin admin."""

from __future__ import annotations

import asyncio
import dataclasses

import pytest

from app.application.ports import AdminUserFilters, AuthenticatedIdentity
from app.domain.exceptions import CannotChangeOwnRoleError, LastAdminError, UserNotFoundError
from app.domain.models import User, UserRole, VerificationStatus
from app.domain.value_objects import Email
from tests.conftest import World
from tests.factories import NOW, make_professional


def _admin(world: World, email: str) -> User:
    return world.add_user(firebase_uid=f"fb-{email}", email=Email(email), role=UserRole.ADMIN)


def _pro(world: World, email: str) -> User:
    return world.add_user(firebase_uid=f"fb-{email}", email=Email(email))


class TestChangeUserRole:
    async def test_admin_promotes_a_professional_and_leaves_an_event(self, world: World) -> None:
        admin = _admin(world, "admin@example.com")
        pro = _pro(world, "pro@example.com")

        result = await world.change_user_role.execute(
            user_id=pro.id, role=UserRole.ADMIN, actor_user_id=admin.id, note="  soporte  "
        )

        assert result.user.role is UserRole.ADMIN
        assert world.users.items[pro.id].role is UserRole.ADMIN
        assert result.event is not None
        assert result.event.from_role is UserRole.PROFESSIONAL
        assert result.event.to_role is UserRole.ADMIN
        assert result.event.actor_user_id == admin.id
        assert result.event.note == "soporte"
        assert result.event.created_at == NOW
        assert await world.list_role_events.execute(pro.id) == [result.event]

    async def test_promotion_survives_the_next_login_without_claim(self, world: World) -> None:
        admin = _admin(world, "admin@example.com")
        pro = _pro(world, "pro@example.com")
        await world.change_user_role.execute(
            user_id=pro.id, role=UserRole.ADMIN, actor_user_id=admin.id
        )

        synced = await world.sync_user.execute(
            AuthenticatedIdentity(provider_uid=pro.firebase_uid, email="pro@example.com")
        )

        assert synced.role is UserRole.ADMIN

    async def test_admin_demotes_another_admin(self, world: World) -> None:
        admin = _admin(world, "admin@example.com")
        other = _admin(world, "other@example.com")

        result = await world.change_user_role.execute(
            user_id=other.id, role=UserRole.PROFESSIONAL, actor_user_id=admin.id
        )

        assert result.user.role is UserRole.PROFESSIONAL
        assert world.users.items[other.id].role is UserRole.PROFESSIONAL

    async def test_same_role_is_a_noop_without_event(self, world: World) -> None:
        admin = _admin(world, "admin@example.com")
        pro = _pro(world, "pro@example.com")

        result = await world.change_user_role.execute(
            user_id=pro.id, role=UserRole.PROFESSIONAL, actor_user_id=admin.id
        )

        assert result.event is None
        assert world.users.role_events == []

    async def test_nobody_changes_their_own_role(self, world: World) -> None:
        admin = _admin(world, "admin@example.com")
        _admin(world, "other@example.com")

        with pytest.raises(CannotChangeOwnRoleError):
            await world.change_user_role.execute(
                user_id=admin.id, role=UserRole.PROFESSIONAL, actor_user_id=admin.id
            )
        assert world.users.items[admin.id].role is UserRole.ADMIN

    async def test_the_last_admin_cannot_be_demoted(self, world: World) -> None:
        admin = _admin(world, "admin@example.com")

        # Solo la CLI (actor `None`) podria intentarlo: el admin no puede degradarse.
        with pytest.raises(LastAdminError):
            await world.change_user_role.execute(
                user_id=admin.id, role=UserRole.PROFESSIONAL, actor_user_id=None
            )
        assert world.users.items[admin.id].role is UserRole.ADMIN
        assert world.users.role_events == []

    async def test_unknown_user(self, world: World) -> None:
        admin = _admin(world, "admin@example.com")
        with pytest.raises(UserNotFoundError):
            await world.change_user_role.execute(
                user_id=world.ids.new_id(), role=UserRole.ADMIN, actor_user_id=admin.id
            )

    async def test_two_admins_demoting_each_other_leave_one_admin(self, world: World) -> None:
        """La carrera: sin bloquear a todos los admins, cada uno ve "queda el otro"."""
        first = _admin(world, "first@example.com")
        second = _admin(world, "second@example.com")

        results = await asyncio.gather(
            world.change_user_role.execute(
                user_id=second.id, role=UserRole.PROFESSIONAL, actor_user_id=first.id
            ),
            world.change_user_role.execute(
                user_id=first.id, role=UserRole.PROFESSIONAL, actor_user_id=second.id
            ),
            return_exceptions=True,
        )

        admins = [user for user in world.users.items.values() if user.is_admin]
        assert len(admins) == 1
        assert sum(isinstance(result, LastAdminError) for result in results) == 1

    async def test_race_is_lost_without_the_lock(self, world: World) -> None:
        """Comprueba que el test anterior prueba algo: sin bloqueo quedan cero admins."""
        world.users.locking_enabled = False
        first = _admin(world, "first@example.com")
        second = _admin(world, "second@example.com")

        await asyncio.gather(
            world.change_user_role.execute(
                user_id=second.id, role=UserRole.PROFESSIONAL, actor_user_id=first.id
            ),
            world.change_user_role.execute(
                user_id=first.id, role=UserRole.PROFESSIONAL, actor_user_id=second.id
            ),
            return_exceptions=True,
        )

        assert not [user for user in world.users.items.values() if user.is_admin]

    async def test_every_demotion_locks_the_admins_before_the_target_row(
        self, world: World, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Revision de la PR 27: un orden de bloqueo distinto puede interbloquear.

        El objetivo se lee como profesional y lo promueven antes del bloqueo. El camino
        de respaldo bloqueaba su fila y LUEGO a los admins, al reves que una degradacion
        normal: dos transacciones asi se esperan la una a la otra en Postgres.
        """
        actor = _admin(world, "actor@example.com")
        target = _admin(world, "target@example.com")
        stale = dataclasses.replace(target, role=UserRole.PROFESSIONAL)
        order: list[str] = []
        original_get = world.users.get
        original_lock_admins = world.users.lock_admins
        original_get_for_update = world.users.get_for_update

        async def stale_get(user_id):  # type: ignore[no-untyped-def]
            user = await original_get(user_id)
            # Lectura previa al bloqueo: aun no le habian dado el rol de admin.
            return stale if user_id == target.id else user

        async def lock_admins():  # type: ignore[no-untyped-def]
            order.append("admins")
            return await original_lock_admins()

        async def get_for_update(user_id):  # type: ignore[no-untyped-def]
            order.append("target")
            return await original_get_for_update(user_id)

        monkeypatch.setattr(world.users, "get", stale_get)
        monkeypatch.setattr(world.users, "lock_admins", lock_admins)
        monkeypatch.setattr(world.users, "get_for_update", get_for_update)

        await world.change_user_role.execute(
            user_id=target.id, role=UserRole.PROFESSIONAL, actor_user_id=actor.id
        )

        assert order == ["admins", "target"]
        assert world.users.items[target.id].role is UserRole.PROFESSIONAL


class TestListAdminUsers:
    async def test_lists_users_with_their_professional_summary(self, world: World) -> None:
        admin = _admin(world, "admin@example.com")
        pro = _pro(world, "pro@example.com")
        professional = make_professional(
            user_id=pro.id,
            business_name="Reformas Sol",
            verification_status=VerificationStatus.PENDING,
        )
        world.professionals.items[professional.id] = professional
        world.add_account(professional)

        result = await world.list_admin_users.execute(AdminUserFilters())

        assert result.total == 2
        by_id = {item.user.id: item for item in result.items}
        assert by_id[admin.id].professional is None
        assert by_id[pro.id].professional == professional
        assert by_id[pro.id].account is not None
        assert by_id[pro.id].account_active is True

    async def test_filters_by_role_status_and_query(self, world: World) -> None:
        _admin(world, "admin@example.com")
        pending = _pro(world, "pending@example.com")
        approved = _pro(world, "approved@example.com")
        world.professionals.items[pending.id] = make_professional(
            id=pending.id,
            user_id=pending.id,
            business_name="Fontaneria Rio",
            verification_status=VerificationStatus.PENDING,
        )
        world.professionals.items[approved.id] = make_professional(
            id=approved.id,
            user_id=approved.id,
            business_name="Pinturas Luna",
            verification_status=VerificationStatus.APPROVED,
        )

        admins = await world.list_admin_users.execute(AdminUserFilters(role=UserRole.ADMIN))
        queue = await world.list_admin_users.execute(
            AdminUserFilters(verification_status=VerificationStatus.PENDING)
        )
        by_name = await world.list_admin_users.execute(AdminUserFilters(query="  luna "))

        assert [item.user.email.value for item in admins.items] == ["admin@example.com"]
        assert [item.user.id for item in queue.items] == [pending.id]
        assert [item.user.id for item in by_name.items] == [approved.id]

    async def test_page_size_is_clamped(self, world: World) -> None:
        _pro(world, "pro@example.com")
        result = await world.list_admin_users.execute(AdminUserFilters(limit=10_000, offset=-5))
        assert result.limit == 100
        assert result.offset == 0
