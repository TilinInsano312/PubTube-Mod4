"""Prometheus HTTP request instrumentation middleware."""

from time import monotonic

from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.requests import Request

from ..observability.metrics import (
    REQUESTS,
    REQUEST_DURATION,
    normalized_route,
    status_class,
)


METRICS_PATHS = frozenset({"/metrics", "/metrics/"})


class MetricsMiddleware:
    """Record HTTP traffic while preserving ASGI response and route behavior."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in METRICS_PATHS:
            await self.app(scope, receive, send)
            return

        started_at = monotonic()
        status_code = 500

        async def capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            request = Request(scope)
            _record(request, status_code, monotonic() - started_at)


def _record(request: Request, response_status: int, duration: float) -> None:
    method = request.method.upper()
    route = normalized_route(request)
    REQUESTS.labels(method, route, status_class(response_status)).inc()
    REQUEST_DURATION.labels(method, route).observe(duration)
