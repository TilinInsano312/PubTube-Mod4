"""Public dashboard HTTP API."""

from fastapi import APIRouter

from .routes.dashboard import router as dashboard_router

api_router = APIRouter(prefix="/api")
api_router.include_router(dashboard_router)
