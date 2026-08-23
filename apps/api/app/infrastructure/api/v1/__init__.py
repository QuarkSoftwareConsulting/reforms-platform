"""Router raiz de la version 1 del API."""

from fastapi import APIRouter

from app.infrastructure.api.v1 import catalog, leads, professionals, webhooks

api_router = APIRouter()
api_router.include_router(catalog.router)
api_router.include_router(leads.router)
api_router.include_router(professionals.router)
api_router.include_router(webhooks.router)

__all__ = ["api_router"]
