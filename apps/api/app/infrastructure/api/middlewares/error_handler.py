"""Traduccion de errores de dominio a respuestas HTTP.

El dominio nunca importa FastAPI: declara un `code` y un `status` y es aqui donde
eso se convierte en una respuesta. Cualquier excepcion no prevista se registra
entera y se devuelve como 500 sin filtrar detalles internos al cliente.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.exceptions import DomainError

# Starlette deprecio `HTTP_422_UNPROCESSABLE_ENTITY` en favor de este nombre.
HTTP_422_UNPROCESSABLE_CONTENT = 422

logger = structlog.get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        # 4xx son decisiones de negocio esperadas: se registran a nivel info.
        logger.info(
            "domain_error",
            code=exc.code,
            status=exc.status,
            path=request.url.path,
            detail=exc.message,
        )
        return JSONResponse(
            status_code=exc.status,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details or None,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "code": "VALIDATION_ERROR",
                "message": "Los datos enviados no son validos",
                "details": {"errors": _clean_errors(exc)},
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            content = {
                "code": detail["code"],
                "message": detail.get("message", ""),
                "details": detail.get("details"),
            }
        else:
            content = {"code": "HTTP_ERROR", "message": str(detail), "details": None}
        return JSONResponse(
            status_code=exc.status_code, content=content, headers=dict(exc.headers or {})
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", path=request.url.path, method=request.method)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "INTERNAL_ERROR",
                "message": "Se produjo un error inesperado",
                "details": None,
            },
        )


def _clean_errors(exc: RequestValidationError) -> list[dict[str, object]]:
    """Deja los errores de Pydantic serializables y sin exponer los valores enviados."""
    return [
        {
            "field": ".".join(str(part) for part in error.get("loc", ())[1:]),
            "type": error.get("type"),
            "message": error.get("msg"),
        }
        for error in exc.errors()
    ]
