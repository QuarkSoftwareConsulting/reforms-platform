"""Middleware de contexto de peticion: request-id y log de acceso."""

from __future__ import annotations

import ipaddress
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            structlog.contextvars.unbind_contextvars("request_id")

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return response


def client_ip(request: Request, trusted_proxy_hops: int = 1) -> str | None:
    """IP real del cliente, detras de `trusted_proxy_hops` proxies propios.

    Cada proxy anade a `X-Forwarded-For` la IP de quien le llama, asi que la del
    cliente es la que esta a `trusted_proxy_hops` posiciones desde la DERECHA. Las de
    la izquierda las puede escribir el propio cliente: tomar la primera dejaria
    falsear la IP del consentimiento (RGPD) y saltarse el limite de SMS.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if trusted_proxy_hops > 0 and forwarded:
        hops = [part.strip() for part in forwarded.split(",") if part.strip()]
        if len(hops) >= trusted_proxy_hops:
            return hops[-trusted_proxy_hops]
    return request.client.host if request.client else None


UNKNOWN_ORIGIN = "unknown"


def rate_limit_origin(ip: str | None) -> str:
    """Origen para limitar: la IP, o su red /64 en IPv6.

    Un solo cliente IPv6 suele tener un /64 entero: limitar por direccion exacta
    le daria millones de cupos. Lo que no se entiende comparte un unico cupo: si un
    origen ilegible no se limitara, bastaria con mandarlo para saltarse el limite.
    """
    if ip is None:
        return UNKNOWN_ORIGIN
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return UNKNOWN_ORIGIN
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)
