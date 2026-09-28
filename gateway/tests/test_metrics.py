from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from prometheus_client import CollectorRegistry, Counter, Histogram

from app.api.routes import metrics as metrics_route
from app.core.config import settings
from app.middleware import metrics as metrics_middleware
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.jwt_auth import JWTAuthenticationMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.observability import metrics as gateway_metrics


JWT_SECRET = "test-only-metrics-secret-123456789"


@pytest.fixture
def metrics_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    registry = CollectorRegistry()
    monkeypatch.setattr(metrics_route, "METRICS_REGISTRY", registry)
    requests = Counter(
        "pubtube_gateway_requests_total",
        "HTTP requests handled by the PubTube Gateway.",
        ("method", "route", "status_class"),
        registry=registry,
    )
    duration = Histogram(
        "pubtube_gateway_request_duration_seconds",
        "HTTP request duration in seconds for the PubTube Gateway.",
        ("method", "route"),
        registry=registry,
    )
    monkeypatch.setattr(gateway_metrics, "REQUESTS", requests)
    monkeypatch.setattr(gateway_metrics, "REQUEST_DURATION", duration)
    monkeypatch.setattr(metrics_middleware, "REQUESTS", requests)
    monkeypatch.setattr(metrics_middleware, "REQUEST_DURATION", duration)
    monkeypatch.setattr(settings, "jwt_secret", JWT_SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")

    test_app = FastAPI()
    # Match production ordering: MetricsMiddleware is the outermost layer.
    test_app.add_middleware(JWTAuthenticationMiddleware)
    test_app.add_middleware(
        RateLimitMiddleware,
        max_requests=2,
        window_seconds=60,
    )
    test_app.add_middleware(CorrelationIdMiddleware)
    test_app.add_middleware(metrics_middleware.MetricsMiddleware)
    test_app.include_router(metrics_route.router)

    @test_app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @test_app.get("/api/protected/{item_id}")
    def protected(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    return TestClient(test_app)


def _token() -> str:
    import jwt

    return jwt.encode(
        {"sub": "metrics-test", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        JWT_SECRET,
        algorithm="HS256",
    )


def _scraped(metrics_client: TestClient) -> str:
    response = metrics_client.get("/metrics")
    assert response.status_code == 200
    return response.text


def test_metrics_endpoint_is_public_and_exposes_http_families(
    metrics_client: TestClient,
) -> None:
    response = metrics_client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "pubtube_gateway_requests_total" in response.text
    assert "pubtube_gateway_request_duration_seconds" in response.text


def test_successful_request_records_counter_and_histogram(
    metrics_client: TestClient,
) -> None:
    response = metrics_client.get("/api/health")
    payload = _scraped(metrics_client)

    assert response.status_code == 200
    assert 'route="/api/health",status_class="2xx"' in payload
    assert 'pubtube_gateway_request_duration_seconds_count{method="GET",route="/api/health"} 1.0' in payload


def test_authentication_failure_is_counted_without_concrete_path_label(
    metrics_client: TestClient,
) -> None:
    response = metrics_client.get("/api/protected/secret-item-id")
    payload = _scraped(metrics_client)

    assert response.status_code == 401
    assert 'route="unmatched",status_class="4xx"' in payload
    assert "secret-item-id" not in payload


def test_rate_limit_rejection_is_counted(metrics_client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token()}"}
    assert metrics_client.get("/api/protected/first-id", headers=headers).status_code == 200
    assert metrics_client.get("/api/protected/second-id", headers=headers).status_code == 200

    rejected = metrics_client.get("/api/protected/third-id", headers=headers)
    payload = _scraped(metrics_client)

    assert rejected.status_code == 429
    assert 'route="unmatched",status_class="4xx"' in payload
    assert "third-id" not in payload


def test_metrics_scrape_does_not_consume_rate_limit_or_instrument_itself(
    metrics_client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token()}"}
    first = metrics_client.get("/metrics")
    second = metrics_client.get("/metrics/")
    after_scrapes = _scraped(metrics_client)

    assert first.status_code == second.status_code == 200
    assert 'route="/metrics"' not in after_scrapes
    assert 'route="/metrics/"' not in after_scrapes

    protected = metrics_client.get("/api/protected/another-id", headers=headers)
    assert protected.status_code == 200
