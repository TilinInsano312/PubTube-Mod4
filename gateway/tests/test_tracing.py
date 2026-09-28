import asyncio

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    TraceFlags,
    TraceState,
    StatusCode,
    get_current_span,
    set_span_in_context,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.clients.http import UpstreamHttpClient
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.observability.tracing import GatewayTracingMiddleware, _extract_context


TIMEOUT = httpx.Timeout(connect=1, read=2, write=3, pool=4)


def _tracer() -> tuple[object, object, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, provider.get_tracer("test.gateway"), exporter


def _traced_app(tracer: object) -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(CorrelationIdMiddleware)
    test_app.add_middleware(GatewayTracingMiddleware, tracer=tracer)

    @test_app.get("/api/items/{item_id}")
    def item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    return test_app


def _run(coroutine: object) -> object:
    return asyncio.run(coroutine)  # type: ignore[arg-type]


def test_gateway_request_span_contains_route_status_and_correlation_id() -> None:
    _provider, tracer, exporter = _tracer()
    test_app = _traced_app(tracer)

    with TestClient(test_app) as client:
        response = client.get(
            "/api/items/42",
            headers={"X-Correlation-Id": "trace-correlation-id"},
        )

    span = next(
        span for span in exporter.get_finished_spans() if span.name == "gateway.request"
    )
    assert response.status_code == 200
    assert span.attributes["correlation_id"] == "trace-correlation-id"
    assert span.attributes["http.route"] == "/api/items/{item_id}"
    assert span.attributes["http.status_code"] == 200
    assert span.context.is_valid


def test_gateway_request_span_uses_incoming_w3c_parent() -> None:
    _provider, tracer, exporter = _tracer()
    test_app = _traced_app(tracer)
    parent = SpanContext(
        trace_id=0x1234567890ABCDEF1234567890ABCDEF,
        span_id=0x1234567890ABCDEF,
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=TraceState(),
    )
    carrier: dict[str, str] = {}
    TraceContextTextMapPropagator().inject(
        carrier,
        context=set_span_in_context(NonRecordingSpan(parent)),
    )

    with TestClient(test_app) as client:
        response = client.get("/api/items/42", headers=carrier)

    span = next(
        span for span in exporter.get_finished_spans() if span.name == "gateway.request"
    )
    assert response.status_code == 200
    assert span.context.trace_id == parent.trace_id
    assert span.parent is not None
    assert span.parent.span_id == parent.span_id


def test_gateway_request_extracts_case_insensitive_w3c_headers() -> None:
    parent = SpanContext(
        trace_id=0x2234567890ABCDEF1234567890ABCDEF,
        span_id=0x2234567890ABCDEF,
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=TraceState(),
    )
    carrier: dict[str, str] = {}
    TraceContextTextMapPropagator().inject(
        carrier,
        context=set_span_in_context(NonRecordingSpan(parent)),
    )
    scope = {
        "headers": [
            (key.upper().encode("latin-1"), value.encode("latin-1"))
            for key, value in carrier.items()
        ]
    }

    extracted = get_current_span(_extract_context(scope)).get_span_context()

    assert extracted.trace_id == parent.trace_id
    assert extracted.span_id == parent.span_id


def test_upstream_span_injects_active_w3c_context_and_correlation_id() -> None:
    _provider, tracer, exporter = _tracer()
    observed: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        observed["traceparent"] = request.headers["traceparent"]
        observed["correlation_id"] = request.headers["X-Correlation-Id"]
        return httpx.Response(204, request=request)

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    upstream_client = UpstreamHttpClient(
        module="module1",
        base_url="http://module-one.test",
        client=async_client,
        timeout=TIMEOUT,
        tracer=tracer,
    )

    try:
        with tracer.start_as_current_span("gateway.request") as request_span:
            response = _run(
                upstream_client.request(
                    "GET",
                    "/content",
                    headers={
                        "traceparent": (
                            "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-"
                            "bbbbbbbbbbbbbbbb-01"
                        ),
                    },
                    correlation_id="upstream-correlation-id",
                )
            )
            request_span_context = request_span.get_span_context()
    finally:
        _run(async_client.aclose())

    spans = exporter.get_finished_spans()
    upstream_span = next(span for span in spans if span.name == "gateway.upstream")
    outgoing_context = TraceContextTextMapPropagator().extract(observed)
    outgoing_span_context = get_current_span(outgoing_context).get_span_context()

    assert response.status_code == 204  # type: ignore[union-attr]
    assert observed["correlation_id"] == "upstream-correlation-id"
    assert outgoing_span_context.trace_id == upstream_span.context.trace_id
    assert outgoing_span_context.span_id == upstream_span.context.span_id
    assert outgoing_span_context.trace_id == request_span_context.trace_id
    assert upstream_span.parent is not None
    assert upstream_span.parent.span_id == request_span_context.span_id
    assert upstream_span.attributes["correlation_id"] == "upstream-correlation-id"


def test_upstream_5xx_span_is_error_when_response_is_returned() -> None:
    _provider, tracer, exporter = _tracer()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    upstream_client = UpstreamHttpClient(
        module="module1",
        base_url="http://module-one.test",
        client=async_client,
        timeout=TIMEOUT,
        tracer=tracer,
    )

    try:
        response = _run(
            upstream_client.request(
                "GET",
                "/content",
                raise_for_status=False,
            )
        )
    finally:
        _run(async_client.aclose())

    upstream_span = next(
        span for span in exporter.get_finished_spans() if span.name == "gateway.upstream"
    )

    assert response.status_code == 503  # type: ignore[union-attr]
    assert upstream_span.status.status_code == StatusCode.ERROR
