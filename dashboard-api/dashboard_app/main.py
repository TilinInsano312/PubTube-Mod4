"""Standalone FastAPI entry point for the publication dashboard."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from opentelemetry import trace
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from .api.router import api_router
from .core.config import settings
from .observability import ObservabilityMiddleware, configure_metrics, configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage tracing resources without inventing a publication source for M3."""
    provider = configure_tracing(settings)
    app.state.tracer = provider.get_tracer("pubtube.dashboard")
    try:
        yield
    finally:
        provider.shutdown()


def create_app() -> FastAPI:
    """Build an independently runnable dashboard application."""
    app = FastAPI(title="PubTube Dashboard API", version="0.1.0", lifespan=lifespan)
    app.state.tracer = trace.get_tracer("pubtube.dashboard")
    app.state.service_name = settings.otel_service_name
    app.state.environment = settings.environment
    configure_metrics(app)
    app.add_middleware(ObservabilityMiddleware)
    app.include_router(api_router)

    @app.get("/api/health", tags=["health"])
    async def health():
        return {"status": "ok", "service": "dashboard-api"}

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request):
        return Response(generate_latest(request.app.state.metrics_registry), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(app, host="127.0.0.1", port=settings.dashboard_port, access_log=False)
