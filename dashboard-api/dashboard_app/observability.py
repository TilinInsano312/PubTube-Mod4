"""Request correlation, structured logs, metrics and distributed tracing."""

import json
import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from opentelemetry import propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode
from prometheus_client import CollectorRegistry, Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .core.config import Settings

logger = logging.getLogger("pubtube.dashboard")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def configure_tracing(config: Settings) -> TracerProvider:
    """Create a provider owned by this application, including OTLP when enabled."""
    provider = TracerProvider(resource=Resource.create({
        "service.name": config.otel_service_name,
        "service.version": "0.1.0",
        "deployment.environment": config.environment,
    }))
    if config.otel_traces_exporter == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=config.otel_endpoint)))
    return provider


def configure_metrics(app) -> None:
    """Keep the service's registry independent from Gateway and other app instances."""
    registry = CollectorRegistry()
    app.state.metrics_registry = registry
    labels = ["method", "route", "status"]
    app.state.request_count = Counter(
        "pubtube_dashboard_requests_total", "Dashboard HTTP requests", labels, registry=registry
    )
    app.state.request_duration = Histogram(
        "pubtube_dashboard_request_duration_seconds", "Dashboard HTTP latency", labels, registry=registry
    )


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Propagate correlation and W3C context and record each completed request."""

    async def dispatch(self, request, call_next):
        candidate = request.headers.get("X-Correlation-Id", "").strip()
        correlation_id = candidate if (
            candidate and len(candidate) <= 128
            and not any(ord(char) < 32 or ord(char) == 127 for char in candidate)
        ) else str(uuid4())
        request.state.correlation_id = correlation_id
        started = perf_counter()
        tracer = request.app.state.tracer
        with tracer.start_as_current_span(
            "dashboard.request",
            context=propagate.extract(dict(request.headers)),
            kind=SpanKind.SERVER,
            attributes={"correlation_id": correlation_id, "http.request.method": request.method},
        ) as span:
            try:
                response = await call_next(request)
            except Exception:
                response = JSONResponse(status_code=500, content={
                    "status": "error", "code": "DASHBOARD_ERROR",
                    "message": "Dashboard request failed",
                })
            response.headers["X-Correlation-Id"] = correlation_id
            path = request.url.path.rstrip("/")
            route = path if path in {"/api/dashboard", "/api/health", "/metrics"} else "unmatched"
            duration = perf_counter() - started
            labels = {"method": request.method, "route": route, "status": str(response.status_code)}
            request.app.state.request_count.labels(**labels).inc()
            request.app.state.request_duration.labels(**labels).observe(duration)
            span.set_attribute("http.route", route)
            span.set_attribute("http.response.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR))
            context = trace.get_current_span().get_span_context()
            logger.log(logging.ERROR if response.status_code >= 500 else logging.INFO, json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR" if response.status_code >= 500 else "INFO",
                "service": request.app.state.service_name,
                "environment": request.app.state.environment,
                "correlationId": correlation_id,
                "causationId": None,
                "traceId": f"{context.trace_id:032x}", "spanId": f"{context.span_id:016x}",
                "method": request.method, "route": route, "statusCode": response.status_code,
                "durationMs": round(duration * 1000, 2),
            }))
            return response
