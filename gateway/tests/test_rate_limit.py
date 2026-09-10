from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.config import settings
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.jwt_auth import JWTAuthenticationMiddleware
from app.middleware.rate_limit import (
    InMemoryRateLimiter,
    RateLimitMiddleware,
    _client_key,
    _parse_trusted_proxy_ips,
)


JWT_SECRET = "test-only-rate-limit-secret-123456789"
JWT_ALGORITHM = "HS256"


class FakeClock:
    """Deterministic clock used to verify fixed-window rollover."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def create_token() -> str:
    """Create a short-lived token for rate-limit integration tests."""

    payload = {
        "sub": "rate-limit-user",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def build_request(client_host: str, real_ip: str) -> Request:
    """Build a request with an explicit peer and X-Real-IP header."""

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/protected",
            "query_string": b"",
            "headers": [(b"x-real-ip", real_ip.encode())],
            "client": (client_host, 1234),
        }
    )


@pytest.fixture
def limited_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, FakeClock]]:
    monkeypatch.setattr(settings, "jwt_secret", JWT_SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", JWT_ALGORITHM)
    clock = FakeClock()
    test_app = FastAPI()
    test_app.add_middleware(JWTAuthenticationMiddleware)
    test_app.add_middleware(
        RateLimitMiddleware,
        max_requests=2,
        window_seconds=10,
        clock=clock,
    )
    test_app.add_middleware(CorrelationIdMiddleware)

    @test_app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @test_app.get("/api/protected")
    def protected() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(test_app) as client:
        yield client, clock


def test_counter_is_deterministic_and_resets_after_window() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=10, clock=clock)

    first = limiter.check("client-a")
    second = limiter.check("client-a")
    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    blocked = limiter.check("client-a")
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.retry_after_seconds == 10

    clock.advance(10)
    reset = limiter.check("client-a")
    assert reset.allowed is True
    assert reset.remaining == 1


def test_requests_under_limit_are_accepted(
    limited_client: tuple[TestClient, FakeClock],
) -> None:
    client, _ = limited_client
    headers = {"Authorization": f"Bearer {create_token()}"}

    first = client.get("/api/protected", headers=headers)
    second = client.get("/api/protected", headers=headers)

    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "2"
    assert first.headers["X-RateLimit-Remaining"] == "1"
    assert second.status_code == 200
    assert second.headers["X-RateLimit-Remaining"] == "0"


def test_exceeding_limit_returns_429_and_retry_headers(
    limited_client: tuple[TestClient, FakeClock],
) -> None:
    client, _ = limited_client
    headers = {
        "Authorization": f"Bearer {create_token()}",
        "X-Correlation-Id": "rate-limit-correlation-id",
    }

    client.get("/api/protected", headers=headers)
    client.get("/api/protected", headers=headers)
    response = client.get("/api/protected", headers=headers)

    assert response.status_code == 429
    assert response.json() == {"detail": "Rate limit exceeded"}
    assert response.headers["X-RateLimit-Limit"] == "2"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert response.headers["Retry-After"] == "10"
    assert response.headers["X-Correlation-Id"] == "rate-limit-correlation-id"


def test_health_is_excluded_from_rate_limit(
    limited_client: tuple[TestClient, FakeClock],
) -> None:
    client, _ = limited_client
    for _ in range(5):
        response = client.get("/api/health")
        assert response.status_code == 200

    protected = client.get(
        "/api/protected",
        headers={"Authorization": f"Bearer {create_token()}"},
    )

    assert protected.status_code == 200


def test_rate_limit_does_not_bypass_jwt_authentication(
    limited_client: tuple[TestClient, FakeClock],
) -> None:
    client, _ = limited_client

    unauthorized = client.get("/api/protected")
    authorized = client.get(
        "/api/protected",
        headers={"Authorization": f"Bearer {create_token()}"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


def test_untrusted_peer_cannot_override_rate_limit_identity() -> None:
    request = build_request("10.0.0.5", "203.0.113.7")

    assert _client_key(request, _parse_trusted_proxy_ips("")) == "10.0.0.5"


def test_trusted_proxy_may_supply_rate_limit_identity() -> None:
    request = build_request("10.0.0.5", "203.0.113.7")
    trusted_networks = _parse_trusted_proxy_ips("10.0.0.0/8")

    assert _client_key(request, trusted_networks) == "203.0.113.7"
