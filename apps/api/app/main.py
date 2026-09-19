"""Punto de entrada del API y ensamblaje de la infraestructura."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import Settings, get_settings
from app.config.logging import configure_logging
from app.infrastructure.adapters.auth.firebase_token_verifier import (
    FirebaseTokenVerifier,
    init_firebase_app,
)
from app.infrastructure.adapters.clock import SystemClock, Uuid4Generator
from app.infrastructure.adapters.db.session import create_engine, create_session_factory
from app.infrastructure.adapters.payments.stripe_adapter import StripePaymentGateway
from app.infrastructure.api.dependencies import Infrastructure, create_storage
from app.infrastructure.api.middlewares.error_handler import register_exception_handlers
from app.infrastructure.api.middlewares.request_context import RequestContextMiddleware
from app.infrastructure.api.schemas.common import HealthOut
from app.infrastructure.api.v1 import api_router

logger = structlog.get_logger(__name__)


def build_infrastructure(settings: Settings) -> Infrastructure:
    """Elige e instancia los adaptadores concretos de cada puerto.

    Es el unico lugar del backend donde aparecen Stripe, Firebase y S3 a la vez.
    Sustituir cualquiera de los tres es cambiar una linea aqui.
    """
    engine = create_engine(settings)
    return Infrastructure(
        settings=settings,
        engine=engine,
        session_factory=create_session_factory(engine),
        payments=StripePaymentGateway(
            secret_key=settings.stripe_secret_key,
            webhook_secret=settings.stripe_webhook_secret,
        ),
        storage=create_storage(settings),
        token_verifier=FirebaseTokenVerifier(init_firebase_app(settings)),
        clock=SystemClock(),
        ids=Uuid4Generator(),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.assert_production_ready()
    configure_logging(level=settings.log_level, json_output=settings.is_production)

    # ADC puede consultar el metadata server durante la inicializacion.
    app.state.infrastructure = await asyncio.to_thread(build_infrastructure, settings)
    logger.info(
        "api_iniciada",
        environment=settings.environment,
        lead_cap=settings.lead_max_purchases,
        auth_emulator=settings.uses_auth_emulator,
    )
    try:
        yield
    finally:
        await app.state.infrastructure.engine.dispose()
        logger.info("api_detenida")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="Reforma Hub API",
        description=(
            "Marketplace pay-per-lead de oficios y reformas. "
            "Los clientes publican solicitudes gratis; los profesionales pagan por "
            "desbloquear el contacto, con un maximo de compras por solicitud."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept-Language", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health", response_model=HealthOut, tags=["ops"])
    async def health() -> HealthOut:
        """Comprueba que el proceso responde y que la base de datos esta accesible."""
        database_ok = True
        try:
            async with app.state.infrastructure.session_factory() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            logger.exception("health_db_error")
            database_ok = False
        return HealthOut(
            status="ok" if database_ok else "degraded",
            environment=settings.environment,
            database=database_ok,
        )

    return app


app = create_app()
