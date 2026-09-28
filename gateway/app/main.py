"""FastAPI entry point for the PubTube API Gateway."""

from fastapi import FastAPI

from .api.router import api_router
from .api.routes.metrics import router as metrics_router
from .core.config import settings
from .core.lifespan import lifespan
from .middleware.correlation_id import CorrelationIdMiddleware
from .middleware.jwt_auth import JWTAuthenticationMiddleware
from .middleware.metrics import MetricsMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .observability.logging import configure_structured_logging
from .observability.tracing import GatewayTracingMiddleware, configure_tracing


configure_structured_logging(environment=settings.environment)
tracing_runtime = configure_tracing(
    service_name=settings.otel_service_name,
    service_version=settings.app_version,
    environment=settings.environment,
    exporter=settings.otel_traces_exporter,
    endpoint=settings.otel_exporter_otlp_traces_endpoint,
    sampler=settings.otel_traces_sampler,
    sampler_arg=settings.otel_traces_sampler_arg,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FastAPI Gateway/BFF behind an NGINX edge proxy for PubTube.",
    lifespan=lifespan,
)
app.state.tracing_runtime = tracing_runtime


# Keep correlation IDs on authentication failures as well as successful responses.
app.add_middleware(JWTAuthenticationMiddleware)
# Apply the limit before authentication while keeping correlation IDs outermost.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(GatewayTracingMiddleware, tracer=tracing_runtime.tracer)
app.include_router(api_router)
app.include_router(metrics_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=settings.gateway_port,
        access_log=False,
    )
