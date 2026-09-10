"""Top-level router for the Gateway's HTTP API."""

from fastapi import APIRouter

from .routes.demo import router as demo_router
from .routes.health import router as health_router


# All Gateway HTTP routes are grouped below the /api prefix.
api_router = APIRouter(prefix="/api")

# Module 4-owned routes currently exposed by the Gateway.
api_router.include_router(health_router)
api_router.include_router(demo_router)

# Future route groups are intentionally not registered yet:
# - /content/* -> Module 1
# - /events/* -> Module 2
# - /publish/* -> Module 3
