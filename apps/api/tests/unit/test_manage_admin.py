"""Tests de la CLI de claims administrativos, sin credenciales ni red."""

from __future__ import annotations

import json
import sys
from unittest.mock import Mock

import pytest
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import PermissionDeniedError, UnavailableError
from google.auth.exceptions import DefaultCredentialsError, RefreshError

from scripts import manage_admin


@pytest.fixture
def firebase(monkeypatch: pytest.MonkeyPatch) -> Mock:
    sdk = Mock()
    sdk.app.project_id = "reforma-hub-test"
    sdk.initialize.return_value = sdk.app
    monkeypatch.setattr(manage_admin, "get_settings", sdk.settings)
    monkeypatch.setattr(manage_admin, "init_firebase_app", sdk.initialize)
    monkeypatch.setattr(firebase_auth, "get_user", sdk.get_user)
    monkeypatch.setattr(firebase_auth, "get_user_by_email", sdk.get_user_by_email)
    monkeypatch.setattr(firebase_auth, "set_custom_user_claims", sdk.set_claims)
    return sdk


def run_cli(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["manage_admin", *args])
    return manage_admin.main()


@pytest.mark.parametrize("identifier", ["--uid", "--email"])
def test_grant_preserves_existing_claims(
    monkeypatch: pytest.MonkeyPatch,
    firebase: Mock,
    capsys: pytest.CaptureFixture[str],
    identifier: str,
) -> None:
    claims = {"plan": "pro", "permissions": {"reports": True}, "reforma_admin": False}
    user = firebase_auth.UserRecord({"localId": "fb-admin", "customAttributes": json.dumps(claims)})
    firebase.get_user.return_value = user
    firebase.get_user_by_email.return_value = user
    value = "fb-admin" if identifier == "--uid" else "admin@example.com"

    assert run_cli(monkeypatch, "grant", identifier, value) == 0

    firebase.initialize.assert_called_once_with(firebase.settings.return_value)
    if identifier == "--uid":
        firebase.get_user.assert_called_once_with(value, app=firebase.app)
        firebase.get_user_by_email.assert_not_called()
    else:
        firebase.get_user_by_email.assert_called_once_with(value, app=firebase.app)
        firebase.get_user.assert_not_called()
    firebase.set_claims.assert_called_once_with(
        "fb-admin", {**claims, "admin": True}, app=firebase.app
    )
    assert user.custom_claims == claims
    output = capsys.readouterr()
    assert "ADMIN concedido" in output.out
    assert "fb-admin" in output.out
    assert "permissions" not in output.out
    assert not output.err


@pytest.mark.parametrize(
    "admin_claims",
    [{"admin": True}, {"reforma_admin": True}, {"admin": True, "reforma_admin": True}, {}],
)
def test_revoke_removes_only_administrative_claims(
    monkeypatch: pytest.MonkeyPatch,
    firebase: Mock,
    capsys: pytest.CaptureFixture[str],
    admin_claims: dict[str, bool],
) -> None:
    other_claims = {"plan": "pro", "permissions": {"reports": True}}
    claims = {**other_claims, **admin_claims}
    firebase.get_user.return_value = firebase_auth.UserRecord(
        {"localId": "fb-admin", "customAttributes": json.dumps(claims)}
    )

    assert run_cli(monkeypatch, "revoke", "--uid", "fb-admin") == 0

    firebase.set_claims.assert_called_once_with("fb-admin", other_claims, app=firebase.app)
    assert firebase.get_user.return_value.custom_claims == claims
    output = capsys.readouterr()
    assert "ADMIN revocado" in output.out
    assert "fb-admin" in output.out
    assert not output.err


@pytest.mark.parametrize("action", ["grant", "revoke"])
def test_user_without_custom_claims(
    monkeypatch: pytest.MonkeyPatch, firebase: Mock, action: str
) -> None:
    firebase.get_user.return_value = firebase_auth.UserRecord({"localId": "fb-admin"})

    assert run_cli(monkeypatch, action, "--uid", "fb-admin") == 0

    expected = {"admin": True} if action == "grant" else {}
    firebase.set_claims.assert_called_once_with("fb-admin", expected, app=firebase.app)


@pytest.mark.parametrize(
    "error",
    [DefaultCredentialsError("secret"), ValueError("secret"), OSError("secret")],
)
def test_configuration_errors_are_safe(
    monkeypatch: pytest.MonkeyPatch,
    firebase: Mock,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
) -> None:
    firebase.initialize.side_effect = error

    assert run_cli(monkeypatch, "grant", "--uid", "fb-admin") == 1

    firebase.get_user.assert_not_called()
    firebase.set_claims.assert_not_called()
    output = capsys.readouterr()
    assert "configurar Firebase Admin" in output.err
    assert "secret" not in output.err
    assert not output.out


def test_missing_project_fails_before_lookup(
    monkeypatch: pytest.MonkeyPatch, firebase: Mock, capsys: pytest.CaptureFixture[str]
) -> None:
    firebase.app.project_id = None

    assert run_cli(monkeypatch, "grant", "--uid", "fb-admin") == 1

    firebase.get_user.assert_not_called()
    firebase.set_claims.assert_not_called()
    assert "configurar Firebase Admin" in capsys.readouterr().err


def test_missing_user_fails_without_writing(
    monkeypatch: pytest.MonkeyPatch, firebase: Mock, capsys: pytest.CaptureFixture[str]
) -> None:
    firebase.get_user_by_email.side_effect = firebase_auth.UserNotFoundError("secret")

    assert run_cli(monkeypatch, "revoke", "--email", "missing@example.com") == 1

    firebase.set_claims.assert_not_called()
    output = capsys.readouterr()
    assert "no existe un usuario Firebase" in output.err
    assert "secret" not in output.err
    assert not output.out


@pytest.mark.parametrize("operation", ["get_user", "set_claims"])
@pytest.mark.parametrize(
    "error",
    [
        PermissionDeniedError("secret"),
        UnavailableError("secret"),
        RefreshError("secret"),
        ValueError("secret"),
    ],
)
def test_operation_errors_return_failure_without_exposing_details(
    monkeypatch: pytest.MonkeyPatch,
    firebase: Mock,
    capsys: pytest.CaptureFixture[str],
    operation: str,
    error: Exception,
) -> None:
    firebase.get_user.return_value = firebase_auth.UserRecord({"localId": "fb-admin"})
    getattr(firebase, operation).side_effect = error

    assert run_cli(monkeypatch, "grant", "--uid", "fb-admin") == 1

    if operation == "get_user":
        firebase.set_claims.assert_not_called()
    output = capsys.readouterr()
    assert "no se pudieron actualizar los claims" in output.err
    assert "secret" not in output.err
    assert not output.out


@pytest.mark.parametrize(
    "args",
    [
        ("grant",),
        ("grant", "--uid", "fb-admin", "--email", "admin@example.com"),
        ("invalid", "--uid", "fb-admin"),
    ],
)
def test_invalid_arguments_do_not_initialize_firebase(
    monkeypatch: pytest.MonkeyPatch, firebase: Mock, args: tuple[str, ...]
) -> None:
    with pytest.raises(SystemExit) as error:
        run_cli(monkeypatch, *args)

    assert error.value.code == 2
    firebase.initialize.assert_not_called()
