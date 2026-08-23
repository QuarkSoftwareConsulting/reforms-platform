"""Puerto de verificacion de identidad.

Lo implementa Firebase Auth, pero el nucleo solo ve un `AuthenticatedIdentity`.
Cambiar de proveedor no toca ni el dominio ni los casos de uso.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    """Identidad extraida de un ID token valido."""

    provider_uid: str
    email: str | None
    email_verified: bool = False
    display_name: str | None = None
    is_admin_claim: bool = False


class TokenVerifierPort(ABC):
    @abstractmethod
    async def verify(self, id_token: str) -> AuthenticatedIdentity:
        """Devuelve la identidad del token o lanza `AuthenticationError`."""
