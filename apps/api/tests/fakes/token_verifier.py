from __future__ import annotations

from app.application.ports import AuthenticatedIdentity, TokenVerifierPort
from app.domain.exceptions import AuthenticationError


class FakeTokenVerifier(TokenVerifierPort):
    """Mapa token -> identidad. Cualquier token desconocido falla la verificacion."""

    def __init__(self, identities: dict[str, AuthenticatedIdentity] | None = None) -> None:
        self.identities = identities or {}

    def register(self, token: str, identity: AuthenticatedIdentity) -> None:
        self.identities[token] = identity

    async def verify(self, id_token: str) -> AuthenticatedIdentity:
        identity = self.identities.get(id_token)
        if identity is None:
            raise AuthenticationError("Token invalido")
        return identity
