"""Tests de la CLI de bootstrap de admins, con los fakes y sin base de datos."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock

import pytest

from app.domain.models import User, UserRole
from app.domain.value_objects import Email
from scripts import manage_admin
from tests.conftest import World


def _user(world: World, email: str, role: UserRole = UserRole.PROFESSIONAL) -> User:
    return world.add_user(firebase_uid=f"fb-{email}", email=Email(email), role=role)


async def _apply(world: World, action: str, *, uid: str | None = None, email: str | None = None):
    return await manage_admin.apply(
        users=world.users,
        change_user_role=world.change_user_role,
        action=action,
        uid=uid,
        email=email,
    )


@pytest.mark.parametrize("identifier", ["uid", "email"])
async def test_grant_writes_the_role_and_an_event_without_actor(
    world: World, capsys: pytest.CaptureFixture[str], identifier: str
) -> None:
    user = _user(world, "boss@example.com")
    kwargs = {"uid": user.firebase_uid} if identifier == "uid" else {"email": " Boss@Example.com "}

    assert await _apply(world, "grant", **kwargs) == 0

    assert world.users.items[user.id].role is UserRole.ADMIN
    [event] = world.users.role_events
    assert event.actor_user_id is None
    assert event.note == manage_admin.CLI_NOTE
    output = capsys.readouterr()
    assert "ADMIN concedido" in output.out
    assert not output.err


async def test_revoke_respects_the_last_admin_rule(
    world: World, capsys: pytest.CaptureFixture[str]
) -> None:
    admin = _user(world, "admin@example.com", UserRole.ADMIN)

    assert await _apply(world, "revoke", uid=admin.firebase_uid) == 1

    assert world.users.items[admin.id].role is UserRole.ADMIN
    assert "LAST_ADMIN" in capsys.readouterr().err


async def test_revoke_with_another_admin_left(world: World) -> None:
    _user(world, "admin@example.com", UserRole.ADMIN)
    other = _user(world, "other@example.com", UserRole.ADMIN)

    assert await _apply(world, "revoke", email="other@example.com") == 0
    assert world.users.items[other.id].role is UserRole.PROFESSIONAL


async def test_same_role_reports_no_change(
    world: World, capsys: pytest.CaptureFixture[str]
) -> None:
    _user(world, "admin@example.com", UserRole.ADMIN)

    assert await _apply(world, "grant", email="admin@example.com") == 0
    assert world.users.role_events == []
    assert "Sin cambios" in capsys.readouterr().out


async def test_unknown_user_fails_without_writing(
    world: World, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await _apply(world, "grant", email="missing@example.com") == 1
    assert world.users.role_events == []
    assert "iniciado sesion" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        ("grant",),
        ("grant", "--uid", "fb-admin", "--email", "admin@example.com"),
        ("invalid", "--uid", "fb-admin"),
    ],
)
def test_invalid_arguments_never_touch_the_database(
    monkeypatch: pytest.MonkeyPatch, args: tuple[str, ...]
) -> None:
    run = AsyncMock()
    monkeypatch.setattr(manage_admin, "run", run)
    monkeypatch.setattr(sys, "argv", ["manage_admin", *args])

    with pytest.raises(SystemExit) as error:
        manage_admin.main()

    assert error.value.code == 2
    run.assert_not_called()
