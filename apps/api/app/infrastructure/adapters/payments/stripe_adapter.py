"""Adaptador de Stripe.

Traduce entre el lenguaje del dominio y la API de Stripe. Es el unico modulo que
importa `stripe`; el resto del sistema solo conoce `PaymentPort`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, cast
from uuid import UUID

import stripe

from app.application.ports import (
    CheckoutRequest,
    CheckoutSession,
    PaymentEvent,
    PaymentEventType,
    PaymentPort,
)
from app.domain.exceptions import AuthenticationError, DomainError, PaymentGatewayError

logger = logging.getLogger(__name__)

# Mapa de eventos de Stripe a los pocos que el negocio necesita entender.
EVENT_TYPE_MAP = {
    "checkout.session.completed": PaymentEventType.CHECKOUT_COMPLETED,
    "checkout.session.async_payment_succeeded": PaymentEventType.CHECKOUT_COMPLETED,
    "checkout.session.expired": PaymentEventType.CHECKOUT_EXPIRED,
    "checkout.session.async_payment_failed": PaymentEventType.PAYMENT_FAILED,
    "payment_intent.payment_failed": PaymentEventType.PAYMENT_FAILED,
    "charge.refunded": PaymentEventType.REFUNDED,
}

# Stripe solo acepta estos codigos de idioma en el checkout.
SUPPORTED_LOCALES = {"es", "en"}

# Limites que Stripe impone a `expires_at`.
MIN_EXPIRY_MINUTES = 30
MAX_EXPIRY_MINUTES = 24 * 60


class StripePaymentGateway(PaymentPort):
    def __init__(self, *, secret_key: str, webhook_secret: str) -> None:
        self._client = stripe.StripeClient(secret_key) if secret_key else None
        self._webhook_secret = webhook_secret

    def _require_client(self) -> stripe.StripeClient:
        if self._client is None:
            logger.error("stripe_sin_configurar: falta STRIPE_SECRET_KEY")
            raise PaymentGatewayError()
        return self._client

    async def create_checkout_session(self, request: CheckoutRequest) -> CheckoutSession:
        client = self._require_client()
        locale = request.locale if request.locale in SUPPORTED_LOCALES else "auto"

        params: dict[str, Any] = {
            "mode": "payment",
            "line_items": [
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": request.amount.currency.lower(),
                        "unit_amount": request.amount.amount_cents,
                        "product_data": {
                            "name": request.product_name,
                            "description": request.product_description[:500],
                        },
                    },
                }
            ],
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
            "locale": locale,
            # Los metadatos son como el webhook reencuentra la compra reservada.
            "metadata": {
                "purchase_id": str(request.purchase_id),
                "lead_id": str(request.lead_id),
                "professional_id": str(request.professional_id),
            },
            "payment_intent_data": {
                "metadata": {"purchase_id": str(request.purchase_id)},
            },
        }
        if request.customer_email:
            params["customer_email"] = request.customer_email
        # Stripe exige que la sesion caduque entre 30 min y 24 h desde ahora. La
        # alineamos con nuestro TTL de reserva para que el hueco no quede bloqueado
        # en la pasarela despues de que lo hayamos liberado.
        if MIN_EXPIRY_MINUTES <= request.expires_in_minutes <= MAX_EXPIRY_MINUTES:
            params["expires_at"] = int(time.time()) + request.expires_in_minutes * 60

        # El SDK de Stripe es sincrono: se ejecuta en un hilo para no bloquear el
        # event loop de FastAPI.
        try:
            session = await asyncio.to_thread(
                client.checkout.sessions.create, params=cast(Any, params)
            )
        except stripe.StripeError as exc:
            # Clave invalida, red caida, cuenta suspendida... Para el profesional es
            # todo lo mismo: no se ha podido iniciar el pago. El detalle va al log.
            logger.error("stripe_checkout_fallido: %s", exc, exc_info=True)
            raise PaymentGatewayError() from exc

        if not session.url:
            logger.error("stripe_checkout_sin_url: session=%s", session.id)
            raise PaymentGatewayError()
        return CheckoutSession(id=session.id, url=session.url, expires_at_epoch=session.expires_at)

    def parse_webhook_event(self, payload: bytes, signature: str) -> PaymentEvent:
        if not self._webhook_secret:
            raise DomainError("Falta STRIPE_WEBHOOK_SECRET: no se puede verificar el webhook")
        try:
            event = stripe.Webhook.construct_event(
                payload=payload, sig_header=signature, secret=self._webhook_secret
            )
        except stripe.SignatureVerificationError as exc:
            raise AuthenticationError("Firma de webhook de Stripe invalida") from exc
        except ValueError as exc:
            raise AuthenticationError("Payload de webhook malformado") from exc

        event_type = EVENT_TYPE_MAP.get(event.type, PaymentEventType.IGNORED)
        # `event.data.object` es un StripeObject, no un dict: sin convertirlo,
        # llamar a `.get()` lanza AttributeError. `to_dict()` es superficial (deja
        # `metadata` como StripeObject) y `_to_dict_recursive` es privado, asi que
        # se usa la serializacion JSON publica del SDK.
        obj: dict[str, Any] = json.loads(str(event.data.object)) if event.data is not None else {}
        metadata = obj.get("metadata") or {}

        purchase_id: UUID | None = None
        raw_purchase_id = metadata.get("purchase_id")
        if raw_purchase_id:
            try:
                purchase_id = UUID(raw_purchase_id)
            except ValueError:
                logger.warning("purchase_id no es un UUID valido: %r", raw_purchase_id)

        return PaymentEvent(
            id=event.id,
            type=event_type,
            raw_type=event.type,
            purchase_id=purchase_id,
            checkout_session_id=obj.get("id") if obj.get("object") == "checkout.session" else None,
            payment_intent_id=_as_id(obj.get("payment_intent")),
            amount_cents=obj.get("amount_total") or obj.get("amount"),
            currency=(obj.get("currency") or "").upper() or None,
            # Solo se guarda lo minimo para auditar: el payload completo de Stripe
            # puede contener datos del pagador que no necesitamos conservar.
            payload={"id": event.id, "type": event.type},
        )

    async def expire_checkout_session(self, session_id: str) -> None:
        client = self._require_client()
        try:
            await asyncio.to_thread(client.checkout.sessions.expire, session_id)
        except stripe.StripeError as exc:
            # Ya estaba pagada, expirada o la pasarela no responde. La plaza ya se
            # libero en nuestra BD, asi que esto es best-effort.
            logger.info("No se pudo expirar la sesion %s: %s", session_id, exc)


def _as_id(value: object) -> str | None:
    """Stripe devuelve unas veces el id y otras el objeto expandido."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        found = value.get("id")
        return found if isinstance(found, str) else None
    return getattr(value, "id", None)
