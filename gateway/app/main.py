"""FastAPI entry point for the PubTube API Gateway."""

from fastapi import FastAPI

from .api.router import api_router
from .core.config import settings
from .core.lifespan import lifespan
from .middleware.correlation_id import CorrelationIdMiddleware
from .middleware.jwt_auth import JWTAuthenticationMiddleware

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FastAPI Gateway/BFF behind an NGINX edge proxy for PubTube.",
    lifespan=lifespan,
)


# Keep correlation IDs on authentication failures as well as successful responses.
app.add_middleware(JWTAuthenticationMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=settings.gateway_port)
