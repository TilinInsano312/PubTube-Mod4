"""OpenTelemetry tracing and W3C context propagation for the Gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import (
    DEPLOYMENT_ENVIRONMENT,
    SERVICE_NAME,
    SERVICE_VERSION,
    Resource,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)
from opentelemetry.trace import SpanKind, Status, StatusCode, Tracer
from starlette.types import ASGIApp, Message, Receive, Scope, Send


TRACER_NAME = "pubtube.gateway"
W3C_CONTEXT_HEADERS = frozenset({"traceparent", "tracestate", "baggage"})


@dataclass
class TracingRuntime:
    """Runtime-owned OpenTelemetry provider and lifecycle operations."""

    provider: TracerProvider
    tracer: Tracer
    exporter_enabled: bool
    _closed: bool = False

    def force_flush(self) -> None:
        """Flush finished spans without making shutdown mandatory in tests."""

        if not self.exporter_enabled or self._closed:
            return
        self.provider.force_flush(timeout_millis=5_000)

    def shutdown(self) -> None:
        """Release exporter resources once during application shutdown."""

        if not self.exporter_enabled or self._closed:
            return
        self.provider.shutdown()
        self._closed = True


def configure_tracing(
    *,
    service_name: str,
    service_version: str,
    environment: str,
    exporter: str = "none",
    endpoint: str = "",
    sampler: str = "always_on",
    sampler_arg: str = "",
) -> TracingRuntime:
    """Build and register the Gateway tracer provider from explicit settings."""

    provider = TracerProvider(
        resource=Resource.create(
            {
                SERVICE_NAME: service_name,
                SERVICE_VERSION: service_version,
                DEPLOYMENT_ENVIRONMENT: environment,
            }
        ),
        sampler=_build_sampler(sampler, sampler_arg),
    )
    exporter_name = exporter.strip().lower()
    if exporter_name == "otlp":
        span_exporter = (
            OTLPSpanExporter(endpoint=endpoint)
            if endpoint.strip()
            else OTLPSpanExporter()
        )
        provider.add_span_processor(BatchSpanProcessor(span_exporter))
    elif exporter_name == "console":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    elif exporter_name != "none":
        raise ValueError(
            "OTEL_TRACES_EXPORTER must be one of: none, console, otlp"
        )

    trace.set_tracer_provider(provider)
    return TracingRuntime(
        provider=provider,
        tracer=provider.get_tracer(TRACER_NAME),
        exporter_enabled=exporter_name != "none",
    )


def _build_sampler(name: str, argument: str) -> Sampler:
    """Translate the supported OTEL_TRACES_SAMPLER values to SDK samplers."""

    normalized_name = name.strip().lower()
    if normalized_name in {"always_on", "parentbased_always_on"}:
        sampler: Sampler = ALWAYS_ON
    elif normalized_name in {"always_off", "parentbased_always_off"}:
        sampler = ALWAYS_OFF
    elif normalized_name in {"traceidratio", "parentbased_traceidratio"}:
        try:
            ratio = float(argument or "1.0")
        except ValueError as exc:
            raise ValueError("OTEL_TRACES_SAMPLER_ARG must be a number") from exc
        if not 0.0 <= ratio <= 1.0:
            raise ValueError("OTEL_TRACES_SAMPLER_ARG must be between 0 and 1")
        sampler = TraceIdRatioBased(ratio)
    else:
        raise ValueError(
            "OTEL_TRACES_SAMPLER must be one of: always_on, always_off, "
            "traceidratio"
        )

    if normalized_name.startswith("parentbased_"):
        return ParentBased(sampler)
    return sampler


class GatewayTracingMiddleware:
    """Create one server span per incoming HTTP request."""

    def __init__(self, app: ASGIApp, *, tracer: Tracer | None = None) -> None:
        self.app = app
        self.tracer = tracer or trace.get_tracer(TRACER_NAME)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        parent_context = _extract_context(scope)
        status_code = 500

        with self.tracer.start_as_current_span(
            "gateway.request",
            context=parent_context,
            kind=SpanKind.SERVER,
        ) as span:
            span.set_attribute("http.request.method", scope.get("method", ""))
            span.set_attribute("url.path", scope.get("path", ""))

            async def capture_status(message: Message) -> None:
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = int(message["status"])
                    span.set_attribute("http.response.status_code", status_code)
                await send(message)

            try:
                await self.app(scope, receive, capture_status)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                raise
            finally:
                correlation_id = _scope_correlation_id(scope)
                if correlation_id:
                    span.set_attribute("correlation_id", correlation_id)
                route = _scope_route(scope)
                if route:
                    span.set_attribute("http.route", route)
                span.set_attribute("http.status_code", status_code)
                if status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {status_code}"))


def _extract_context(scope: Scope) -> Any:
    """Extract W3C headers from an ASGI request scope."""

    carrier = {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }
    return propagate.extract(carrier)


def _scope_correlation_id(scope: Scope) -> str | None:
    state = scope.get("state") or {}
    value = state.get("correlation_id") if isinstance(state, dict) else None
    return value if isinstance(value, str) else None


def _scope_route(scope: Scope) -> str | None:
    route = scope.get("route")
    route_template = getattr(route, "path", None)
    if isinstance(route_template, str):
        return route_template
    path = scope.get("path")
    return path if isinstance(path, str) else None


def inject_trace_context(headers: dict[str, str]) -> None:
    """Inject the active W3C context into a mutable outgoing header mapping."""

    propagate.inject(headers)


def get_trace_id() -> str | None:
    """Return the active trace ID in the canonical 32-character form."""

    context = trace.get_current_span().get_span_context()
    return f"{context.trace_id:032x}" if context.is_valid else None


def get_span_id() -> str | None:
    """Return the active span ID in the canonical 16-character form."""

    context = trace.get_current_span().get_span_context()
    return f"{context.span_id:016x}" if context.is_valid else None
