"""Low-cardinality Prometheus metrics for Gateway HTTP traffic."""

from starlette.requests import Request

from prometheus_client import REGISTRY, Counter, Histogram


METRICS_REGISTRY = REGISTRY


REQUESTS = Counter(
    "pubtube_gateway_requests_total",
    "HTTP requests handled by the PubTube Gateway.",
    ("method", "route", "status_class"),
)
REQUEST_DURATION = Histogram(
    "pubtube_gateway_request_duration_seconds",
    "HTTP request duration in seconds for the PubTube Gateway.",
    ("method", "route"),
)


def status_class(status_code: int) -> str:
    """Return a bounded status class for an HTTP status code."""

    category = status_code // 100
    if category in {2, 3, 4, 5}:
        return f"{category}xx"
    return "other"


def normalized_route(request: Request) -> str:
    """Get a route template, never a concrete path containing user input."""

    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "unmatched"
