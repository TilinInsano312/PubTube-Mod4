"""Top-level router for the Gateway's HTTP API."""

from fastapi import APIRouter

from .routes.health import router as health_router
from .routes.module1 import router as module1_router
from .routes.module2 import router as module2_router
from .routes.module3 import router as module3_router


# All Gateway HTTP routes are grouped below the /api prefix.
api_router = APIRouter(prefix="/api")

# Module 4-owned technical routes currently exposed by the Gateway.
api_router.include_router(health_router)

# Module routes are explicit so each public contract has one downstream owner.
api_router.include_router(module1_router)
api_router.include_router(module2_router)
api_router.include_router(module3_router)
