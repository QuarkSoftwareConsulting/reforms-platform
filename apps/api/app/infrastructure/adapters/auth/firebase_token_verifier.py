"""Adaptador de Firebase Authentication.

Verifica ID tokens emitidos por el SDK del navegador. En desarrollo respeta
FIREBASE_AUTH_EMULATOR_HOST, con lo que no hace falta service account.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import firebase_admin
import google.auth.credentials
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from app.application.ports import AuthenticatedIdentity, TokenVerifierPort
from app.config import Settings
from app.domain.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

ADMIN_CLAIMS = ("admin", "reforma_admin")
APP_NAME = "reforma-hub"


class EmulatorCredentials(credentials.Base):  # type: ignore[misc]
    """Credencial vacia para el emulador de Auth.

    Con el emulador los ID tokens vienen sin firmar y firebase-admin no consulta
    las claves publicas de Google, asi que no hace falta service account. Pero
    `initialize_app` exige un objeto credencial, y esta es la envoltura minima.
    """

    def get_credential(self) -> google.auth.credentials.Credentials:
        return google.auth.credentials.AnonymousCredentials()  # type: ignore[no-untyped-call]


def init_firebase_app(settings: Settings) -> firebase_admin.App:
    """Inicializa (una sola vez) la app de firebase-admin.

    Orden de resolucion de credenciales:
      1. Emulador: cualquier credencial sirve, no se valida firma contra Google.
      2. `FIREBASE_CREDENTIALS_JSON` con el service account en linea (CI, Docker).
      3. `GOOGLE_APPLICATION_CREDENTIALS` con la ruta al fichero.
      4. Credenciales por defecto del entorno (GCP, Cloud Run).
    """
    try:
        return firebase_admin.get_app(APP_NAME)
    except ValueError:
        pass

    options = {"projectId": settings.firebase_project_id} if settings.firebase_project_id else {}

    if settings.uses_auth_emulator:
        os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = settings.firebase_auth_emulator_host
        logger.warning(
            "Firebase Auth apuntando al emulador en %s", settings.firebase_auth_emulator_host
        )
        credential: credentials.Base = EmulatorCredentials()
    elif settings.firebase_credentials_json:
        credential = credentials.Certificate(json.loads(settings.firebase_credentials_json))
    elif settings.google_application_credentials:
        credential = credentials.Certificate(settings.google_application_credentials)
    else:
        credential = credentials.ApplicationDefault()

    return firebase_admin.initialize_app(credential, options, name=APP_NAME)


class FirebaseTokenVerifier(TokenVerifierPort):
    def __init__(self, app: firebase_admin.App) -> None:
        self._app = app

    async def verify(self, id_token: str) -> AuthenticatedIdentity:
        try:
            # `verify_id_token` hace red (descarga de claves publicas) y es
            # sincrono: va a un hilo para no bloquear el event loop.
            claims: dict[str, Any] = await asyncio.to_thread(
                firebase_auth.verify_id_token, id_token, app=self._app, check_revoked=False
            )
        except firebase_auth.ExpiredIdTokenError as exc:
            raise AuthenticationError("El token ha expirado, vuelve a iniciar sesion") from exc
        except firebase_auth.RevokedIdTokenError as exc:
            raise AuthenticationError("El token ha sido revocado") from exc
        except (firebase_auth.InvalidIdTokenError, ValueError) as exc:
            raise AuthenticationError("Token de autenticacion invalido") from exc

        uid = claims.get("uid") or claims.get("sub")
        if not uid:
            raise AuthenticationError("El token no contiene identificador de usuario")

        return AuthenticatedIdentity(
            provider_uid=str(uid),
            email=claims.get("email"),
            email_verified=bool(claims.get("email_verified", False)),
            display_name=claims.get("name"),
            is_admin_claim=any(bool(claims.get(claim)) for claim in ADMIN_CLAIMS),
        )
