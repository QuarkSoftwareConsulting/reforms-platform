"""A que flags atiende cada despliegue."""

import pytest

from app.domain.models import FlagEnvironment


@pytest.mark.parametrize(
    ("deployment", "flags"),
    [
        ("production", FlagEnvironment.PROD),
        ("development", FlagEnvironment.DEV),
        ("staging", FlagEnvironment.DEV),
        ("test", FlagEnvironment.DEV),
        # Un entorno que no reconocemos nunca lee las de produccion.
        ("prod", FlagEnvironment.DEV),
    ],
)
def test_only_production_reads_the_prod_flags(deployment: str, flags: FlagEnvironment) -> None:
    assert FlagEnvironment.for_deployment(deployment) is flags
