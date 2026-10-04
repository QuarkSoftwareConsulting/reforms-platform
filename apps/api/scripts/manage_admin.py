"""Concede o revoca el rol de admin directamente en la base de datos.

El rol vive en `users.role` y lo gestiona un admin desde el panel. Esta CLI queda
para dar de alta al primer admin y para recuperar el acceso si no queda ninguno.
El usuario tiene que haber iniciado sesion al menos una vez (asi existe su fila).

Uso desde apps/api:
    uv run python -m scripts.manage_admin grant --email admin@example.com
    uv run python -m scripts.manage_admin revoke --uid firebase-uid
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.application.ports import UserRepositoryPort
from app.application.use_cases import ChangeUserRole
from app.config import get_settings
from app.domain.exceptions import DomainError
from app.domain.models import UserRole
from app.infrastructure.api.dependencies import RequestContainer
from app.main import build_infrastructure

CLI_NOTE = "CLI manage_admin"


async def apply(
    *,
    users: UserRepositoryPort,
    change_user_role: ChangeUserRole,
    action: str,
    uid: str | None,
    email: str | None,
) -> int:
    """La CLI sin infraestructura: busca al usuario y le cambia el rol."""
    user = (
        await users.get_by_firebase_uid(uid)
        if uid is not None
        else await users.get_by_email(email or "")
    )
    if user is None:
        print(
            "Error: no hay ningun usuario con ese identificador. Tiene que haber "
            "iniciado sesion al menos una vez.",
            file=sys.stderr,
        )
        return 1
    try:
        result = await change_user_role.execute(
            user_id=user.id,
            role=UserRole.ADMIN if action == "grant" else UserRole.PROFESSIONAL,
            actor_user_id=None,
            note=CLI_NOTE,
        )
    except DomainError as exc:
        # p. ej. LAST_ADMIN: la CLI respeta las mismas reglas que el panel.
        print(f"Error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 1

    if result.event is None:
        print(f"Sin cambios: el usuario {user.firebase_uid!r} ya tenia ese rol.")
    else:
        verb = "concedido" if action == "grant" else "revocado"
        print(f"ADMIN {verb} para el usuario Firebase UID={user.firebase_uid!r}.")
        print("Surte efecto en su siguiente peticion: no hace falta volver a iniciar sesion.")
    return 0


async def run(*, action: str, uid: str | None, email: str | None) -> int:
    infra = build_infrastructure(get_settings())
    try:
        async with infra.session_factory() as session:
            container = RequestContainer.build(infra, session)
            return await apply(
                users=container.users,
                change_user_role=container.change_user_role,
                action=action,
                uid=uid,
                email=email,
            )
    except (SQLAlchemyError, OSError):
        print(
            "Error: no se pudo conectar con la base de datos. Revisa DATABASE_URL.",
            file=sys.stderr,
        )
        return 1
    finally:
        await infra.engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("grant", "revoke"))
    identifier = parser.add_mutually_exclusive_group(required=True)
    identifier.add_argument("--uid", help="UID del usuario Firebase")
    identifier.add_argument("--email", help="email del usuario")
    args = parser.parse_args()
    return asyncio.run(run(action=args.action, uid=args.uid, email=args.email))


if __name__ == "__main__":
    sys.exit(main())
