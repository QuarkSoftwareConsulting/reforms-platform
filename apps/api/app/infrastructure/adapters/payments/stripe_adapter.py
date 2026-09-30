"""Adaptador de Stripe.

Traduce entre el lenguaje del dominio y la API de Stripe. Es el unico modulo que
importa `stripe`; el resto del sistema solo conoce `PaymentPort`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import stripe

from app.application.ports import (
    CheckoutRequest,
    CheckoutSession,
    CustomerRequest,
    PaymentEvent,
    PaymentEventType,
    PaymentPort,
    SubscriptionCheckoutRequest,
)
from app.domain.exceptions import AuthenticationError, DomainError, PaymentGatewayError
from app.domain.models import SubscriptionStatus
from app.domain.value_objects import Money

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

# Eventos de la recarga mensual. `checkout.session.completed` tambien llega para
# las suscripciones: se distingue por `mode` en `_classify`.
SUBSCRIPTION_EVENT_TYPE_MAP = {
    "invoice.paid": PaymentEventType.INVOICE_PAID,
    "invoice.payment_failed": PaymentEventType.INVOICE_PAYMENT_FAILED,
    "customer.subscription.created": PaymentEventType.SUBSCRIPTION_UPDATED,
    "customer.subscription.updated": PaymentEventType.SUBSCRIPTION_UPDATED,
    "customer.subscription.deleted": PaymentEventType.SUBSCRIPTION_UPDATED,
}

# Eventos de compra cuyo objeto no es la sesion de checkout: sin `purchase_id` en
# los metadatos no son de una compra de contacto (p. ej. el cobro de la recarga).
PURCHASE_EVENTS_NEEDING_METADATA = {"payment_intent.payment_failed", "charge.refunded"}

# Estados de suscripcion de Stripe traducidos a los del negocio.
SUBSCRIPTION_STATUS_MAP = {
    "incomplete": SubscriptionStatus.PENDING,
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.ACTIVE,
    "past_due": SubscriptionStatus.PAST_DUE,
    "unpaid": SubscriptionStatus.PAST_DUE,
    "paused": SubscriptionStatus.PAST_DUE,
    "canceled": SubscriptionStatus.CANCELED,
    "incomplete_expired": SubscriptionStatus.CANCELED,
}

# Medios de pago de la recarga: tarjeta (activacion inmediata) y domiciliacion
# SEPA (el primer cobro tarda unos dias en confirmarse).
SUBSCRIPTION_PAYMENT_METHODS = ["card", "sepa_debit"]

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

        event_type = _classify(event.type, obj, purchase_id)
        is_subscription = event_type.concerns_subscription
        subscription_id = _subscription_id(obj) if is_subscription else None
        raw_status = obj.get("status") if obj.get("object") == "subscription" else None
        subscription_status = SUBSCRIPTION_STATUS_MAP.get(str(raw_status)) if raw_status else None
        if event.type == "customer.subscription.deleted":
            subscription_status = SubscriptionStatus.CANCELED

        return PaymentEvent(
            id=event.id,
            type=event_type,
            raw_type=event.type,
            purchase_id=purchase_id,
            checkout_session_id=obj.get("id") if obj.get("object") == "checkout.session" else None,
            payment_intent_id=_as_id(obj.get("payment_intent")),
            amount_cents=(
                obj.get("amount_paid")
                if obj.get("object") == "invoice"
                else obj.get("amount_total") or obj.get("amount")
            ),
            currency=(obj.get("currency") or "").upper() or None,
            # Solo se guarda lo minimo para auditar: el payload completo de Stripe
            # puede contener datos del pagador que no necesitamos conservar.
            payload={"id": event.id, "type": event.type},
            customer_id=_as_id(obj.get("customer")) if is_subscription else None,
            subscription_id=subscription_id,
            invoice_id=obj.get("id") if obj.get("object") == "invoice" else None,
            subscription_status=subscription_status,
            period_end=_period_end(obj) if is_subscription else None,
            occurred_at=_from_epoch(getattr(event, "created", None)),
        )

    async def expire_checkout_session(self, session_id: str) -> None:
        client = self._require_client()
        try:
            await asyncio.to_thread(client.checkout.sessions.expire, session_id)
        except stripe.StripeError as exc:
            # Ya estaba pagada, expirada o la pasarela no responde. La plaza ya se
            # libero en nuestra BD, asi que esto es best-effort.
            logger.info("No se pudo expirar la sesion %s: %s", session_id, exc)

    async def create_customer(self, request: CustomerRequest) -> str:
        client = self._require_client()
        params: dict[str, Any] = {
            "email": request.email,
            "name": request.name,
            "metadata": {"professional_id": str(request.professional_id)},
        }
        try:
            customer = await asyncio.to_thread(client.customers.create, params=cast(Any, params))
        except stripe.StripeError as exc:
            logger.error("stripe_cliente_fallido: %s", exc, exc_info=True)
            raise PaymentGatewayError() from exc
        return str(customer.id)

    async def create_subscription_checkout(
        self, request: SubscriptionCheckoutRequest
    ) -> CheckoutSession:
        client = self._require_client()
        locale = request.locale if request.locale in SUPPORTED_LOCALES else "auto"
        metadata = {"professional_id": str(request.professional_id)}
        params: dict[str, Any] = {
            "mode": "subscription",
            "customer": request.customer_id,
            "line_items": [{"price": request.price_id, "quantity": 1}],
            "payment_method_types": SUBSCRIPTION_PAYMENT_METHODS,
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
            "locale": locale,
            "metadata": metadata,
            # Tambien en la suscripcion, para poder rastrear sus eventos en el panel.
            "subscription_data": {"metadata": metadata},
        }
        try:
            session = await asyncio.to_thread(
                client.checkout.sessions.create, params=cast(Any, params)
            )
        except stripe.StripeError as exc:
            logger.error("stripe_checkout_recarga_fallido: %s", exc, exc_info=True)
            raise PaymentGatewayError() from exc
        if not session.url:
            logger.error("stripe_checkout_sin_url: session=%s", session.id)
            raise PaymentGatewayError()
        return CheckoutSession(id=session.id, url=session.url, expires_at_epoch=session.expires_at)

    async def create_recurring_price(self, *, amount: Money, product_name: str) -> str:
        client = self._require_client()
        params: dict[str, Any] = {
            "currency": amount.currency.lower(),
            "unit_amount": amount.amount_cents,
            "recurring": {"interval": "month"},
            # El importe de la mensualidad ya incluye el IVA.
            "tax_behavior": "inclusive",
            "product_data": {"name": product_name},
        }
        try:
            price = await asyncio.to_thread(client.prices.create, params=cast(Any, params))
        except stripe.StripeError as exc:
            logger.error("stripe_precio_fallido: %s", exc, exc_info=True)
            raise PaymentGatewayError() from exc
        return str(price.id)

    async def create_billing_portal_session(
        self, *, customer_id: str, return_url: str, locale: str = "es"
    ) -> str:
        client = self._require_client()
        params: dict[str, Any] = {
            "customer": customer_id,
            "return_url": return_url,
            "locale": locale if locale in SUPPORTED_LOCALES else "auto",
        }
        try:
            session = await asyncio.to_thread(
                client.billing_portal.sessions.create, params=cast(Any, params)
            )
        except stripe.StripeError as exc:
            logger.error("stripe_portal_fallido: %s", exc, exc_info=True)
            raise PaymentGatewayError() from exc
        return str(session.url)

    async def refund_invoice(self, *, invoice_id: str, idempotency_key: str) -> None:
        client = self._require_client()
        try:
            # Desde la API 2025-03-31 la factura ya no trae `payment_intent`: el cobro
            # cuelga de `invoice.payments`, con su PaymentIntent o su Charge.
            invoice = await asyncio.to_thread(
                client.v1.invoices.retrieve, invoice_id, params={"expand": ["payments"]}
            )
            target = _paid_invoice_payment(invoice)
            if target is None:
                logger.error("stripe_reembolso_sin_cobro: invoice=%s", invoice_id)
                raise PaymentGatewayError("La factura no tiene un cobro que reembolsar")
            await asyncio.to_thread(
                client.v1.refunds.create,
                params=cast(Any, target),
                options={"idempotency_key": idempotency_key},
            )
        except stripe.InvalidRequestError as exc:
            # La clave de idempotencia solo cubre 24 h: un reintento posterior de un
            # reembolso que ya se hizo llega como error. Para nosotros es el mismo
            # reintento seguro que cancelar una suscripcion ya cancelada.
            if exc.code == "charge_already_refunded":
                logger.info("stripe_reembolso_ya_hecho: invoice=%s", invoice_id)
                return
            logger.error("stripe_reembolso_fallido: %s", exc, exc_info=True)
            raise PaymentGatewayError() from exc
        except stripe.StripeError as exc:
            logger.error("stripe_reembolso_fallido: %s", exc, exc_info=True)
            raise PaymentGatewayError() from exc

    async def cancel_subscription(self, subscription_id: str) -> None:
        client = self._require_client()
        try:
            await asyncio.to_thread(client.v1.subscriptions.cancel, subscription_id)
        except stripe.InvalidRequestError as exc:
            # Cancelar una ya cancelada falla en Stripe; para nosotros es un reintento.
            try:
                current = await asyncio.to_thread(client.v1.subscriptions.retrieve, subscription_id)
            except stripe.StripeError:
                current = None
            if current is not None and current.status == "canceled":
                return
            logger.error("stripe_cancelacion_fallida: %s", exc, exc_info=True)
            raise PaymentGatewayError() from exc
        except stripe.StripeError as exc:
            logger.error("stripe_cancelacion_fallida: %s", exc, exc_info=True)
            raise PaymentGatewayError() from exc


def _paid_invoice_payment(invoice: Any) -> dict[str, str] | None:
    """Parametros del reembolso: el PaymentIntent (o el Charge) que pago la factura."""
    payments = getattr(invoice, "payments", None)
    for item in getattr(payments, "data", None) or []:
        if getattr(item, "status", None) != "paid":
            continue
        payment = item.payment
        intent = getattr(payment, "payment_intent", None)
        if intent:
            return {"payment_intent": intent if isinstance(intent, str) else intent.id}
        charge = getattr(payment, "charge", None)
        if charge:
            return {"charge": charge if isinstance(charge, str) else charge.id}
    return None


def _classify(raw_type: str, obj: dict[str, Any], purchase_id: UUID | None) -> PaymentEventType:
    """Decide que significa el evento para el negocio."""
    if obj.get("object") == "checkout.session" and obj.get("mode") == "subscription":
        # La caducidad o el fallo de un checkout de recarga no cambian nada: la
        # cuenta solo se activa con `invoice.paid`.
        if raw_type == "checkout.session.completed":
            return PaymentEventType.SUBSCRIPTION_CHECKOUT_COMPLETED
        return PaymentEventType.IGNORED

    if raw_type in SUBSCRIPTION_EVENT_TYPE_MAP:
        # Una factura suelta (no de la recarga) no afecta a la cuenta.
        if obj.get("object") == "invoice" and _subscription_id(obj) is None:
            return PaymentEventType.IGNORED
        return SUBSCRIPTION_EVENT_TYPE_MAP[raw_type]

    if raw_type in PURCHASE_EVENTS_NEEDING_METADATA and purchase_id is None:
        # Sin esto, un adeudo fallido de la recarga se interpretaria como el fallo
        # de una compra inexistente y el webhook responderia 404 para siempre.
        return PaymentEventType.IGNORED

    return EVENT_TYPE_MAP.get(raw_type, PaymentEventType.IGNORED)


def _subscription_id(obj: dict[str, Any]) -> str | None:
    """Id de la suscripcion en cualquiera de las formas que usa la API de Stripe.

    Las versiones recientes movieron `invoice.subscription` a
    `invoice.parent.subscription_details.subscription`; se aceptan ambas.
    """
    if obj.get("object") == "subscription":
        return _as_id(obj.get("id"))
    direct = _as_id(obj.get("subscription"))
    if direct:
        return direct
    parent = obj.get("parent") or {}
    details = parent.get("subscription_details") or {} if isinstance(parent, dict) else {}
    return _as_id(details.get("subscription")) if isinstance(details, dict) else None


def _period_end(obj: dict[str, Any]) -> datetime | None:
    """Fin del periodo pagado.

    En la factura es el de su linea (el `period_end` de la propia factura apunta al
    periodo anterior). En la suscripcion, las versiones recientes lo llevan en cada
    item en vez de en la raiz.
    """
    kind = obj.get("object")
    if kind == "invoice":
        lines = (obj.get("lines") or {}).get("data") or []
        ends = [
            line.get("period", {}).get("end")
            for line in lines
            if isinstance(line, dict) and isinstance(line.get("period"), dict)
        ]
        valid = [end for end in ends if isinstance(end, int)]
        return _from_epoch(max(valid)) if valid else None
    if kind == "subscription":
        root = obj.get("current_period_end")
        if isinstance(root, int):
            return _from_epoch(root)
        items = (obj.get("items") or {}).get("data") or []
        item_ends: list[int] = [
            end
            for item in items
            if isinstance(item, dict) and isinstance(end := item.get("current_period_end"), int)
        ]
        return _from_epoch(max(item_ends)) if item_ends else None
    return None


def _from_epoch(value: object) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return datetime.fromtimestamp(value, tz=UTC)


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
