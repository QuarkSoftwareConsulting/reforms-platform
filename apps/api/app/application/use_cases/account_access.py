"""Compra de solicitudes: solo con la recarga mensual al dia.

Una cuenta inactiva puede ver solicitudes, pero no comprarlas (documento del
cliente, F02). La regla vive en el dominio (`ProfessionalAccount.assert_can_purchase`);
aqui solo se resuelve la cuenta.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.application.ports import ProfessionalAccountRepositoryPort
from app.domain.exceptions import SubscriptionRequiredError
from app.domain.models import ProfessionalAccount


def require_active(account: ProfessionalAccount | None, now: datetime) -> ProfessionalAccount:
    if account is None:
        raise SubscriptionRequiredError()
    account.assert_can_purchase(now)
    return account


async def require_active_account(
    accounts: ProfessionalAccountRepositoryPort, professional_id: UUID, now: datetime
) -> ProfessionalAccount:
    """Lectura sin bloqueo: descarta pronto a quien no puede comprar."""
    return require_active(await accounts.get(professional_id), now)
