"""Job periodico: libera las plazas de reservas de compra caducadas.

Stripe emite `checkout.session.expired`, pero puede tardar o no llegar si el
profesional nunca abrio el checkout. Este job es la red de seguridad.

    uv run python -m app.jobs.release_reservations
"""

from __future__ import annotations

import asyncio
import sys

import structlog

from app.config import get_settings
from app.config.logging import configure_logging
from app.infrastructure.api.dependencies import RequestContainer
from app.main import build_infrastructure

logger = structlog.get_logger(__name__)


async def main() -> int:
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.is_production)
    infra = build_infrastructure(settings)

    try:
        async with infra.session_factory() as session:
            container = RequestContainer.build(infra, session)
            released = await container.release_reservations.execute()
        logger.info("reservas_liberadas", count=released)
        print(f"Reservas liberadas: {released}")
    finally:
        await infra.engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
