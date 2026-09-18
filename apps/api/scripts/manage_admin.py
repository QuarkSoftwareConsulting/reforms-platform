"""Concede o revoca privilegios administrativos mediante Firebase custom claims.

Uso desde apps/api:
    uv run python -m scripts.manage_admin grant --email admin@example.com
    uv run python -m scripts.manage_admin revoke --uid firebase-uid
"""

from __future__ import annotations

import argparse
import sys

from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError
from google.auth.exceptions import GoogleAuthError

from app.config import get_settings
from app.infrastructure.adapters.auth.firebase_token_verifier import (
    ADMIN_CLAIMS,
    init_firebase_app,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("grant", "revoke"))
    identifier = parser.add_mutually_exclusive_group(required=True)
    identifier.add_argument("--uid", help="UID del usuario Firebase")
    identifier.add_argument("--email", help="email del usuario Firebase")
    args = parser.parse_args()

    try:
        app = init_firebase_app(get_settings())
        if not app.project_id:
            raise ValueError("Falta el proyecto Firebase")
    except (ValueError, OSError, GoogleAuthError, FirebaseError):
        print(
            "Error: no se pudo configurar Firebase Admin. Revisa el proyecto y las "
            "credenciales (FIREBASE_CREDENTIALS_JSON, GOOGLE_APPLICATION_CREDENTIALS "
            "o credenciales predeterminadas del entorno).",
            file=sys.stderr,
        )
        return 1

    try:
        user = (
            firebase_auth.get_user(args.uid, app=app)
            if args.uid is not None
            else firebase_auth.get_user_by_email(args.email, app=app)
        )
        # El SDK reemplaza todos los claims; copiarlos evita perder los ajenos al rol.
        claims = dict(user.custom_claims or {})
        if args.action == "grant":
            claims[ADMIN_CLAIMS[0]] = True
        else:
            # Cualquiera de los alias reconocidos mantiene el privilegio administrativo.
            for claim in ADMIN_CLAIMS:
                claims.pop(claim, None)
        firebase_auth.set_custom_user_claims(user.uid, claims, app=app)
    except firebase_auth.UserNotFoundError:
        print("Error: no existe un usuario Firebase con ese identificador.", file=sys.stderr)
        return 1
    except (ValueError, OSError, GoogleAuthError, FirebaseError):
        # Las excepciones del proveedor pueden incluir datos sensibles de la peticion.
        print(
            "Error: no se pudieron actualizar los claims. Revisa el identificador, "
            "los claims existentes, las credenciales, los permisos y la conexion a Firebase.",
            file=sys.stderr,
        )
        return 1

    result = "concedido" if args.action == "grant" else "revocado"
    print(f"ADMIN {result} para el usuario Firebase UID={user.uid!r}.")
    print("El cambio se reflejara al renovar el ID token y sincronizar de nuevo la identidad.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
