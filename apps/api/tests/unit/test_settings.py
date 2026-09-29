"""Validaciones de `Settings` que protegen reglas de negocio al arrancar."""

import pytest

from app.config import Settings


def test_current_privacy_policy_covers_public_preview() -> None:
    assert Settings().privacy_policy_version == "2026-09-v2"


def test_undeclared_privacy_policy_version_is_refused() -> None:
    # Subir la version sin declararla en el dominio apagaria en silencio la vista
    # previa de todos los leads nuevos.
    with pytest.raises(ValueError, match="PUBLIC_PREVIEW_POLICY_VERSIONS"):
        Settings(privacy_policy_version="2027-01-v3")
