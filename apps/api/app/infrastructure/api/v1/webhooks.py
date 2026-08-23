"""Webhook de la pasarela de pago.

Es el unico camino por el que una compra pasa a `paid`: la confirmacion debe venir
firmada por Stripe, nunca del navegador del profesional.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Header, Request

from app.infrastructure.api.dependencies import ContainerDep
from app.infrastructure.api.schemas.purchases import WebhookAckOut

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe", response_model=WebhookAckOut, summary="Eventos de Stripe")
async def stripe_webhook(
    request: Request,
    container: ContainerDep,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> WebhookAckOut:
    payload = await request.body()
    outcome = await container.handle_payment_event.execute(
        payload=payload, signature=stripe_signature or ""
    )
    logger.info(
        "stripe_webhook",
        event_id=outcome.event_id,
        event_type=outcome.event_type,
        handled=outcome.handled,
        duplicate=outcome.duplicate,
    )
    return WebhookAckOut(received=True, handled=outcome.handled, duplicate=outcome.duplicate)
