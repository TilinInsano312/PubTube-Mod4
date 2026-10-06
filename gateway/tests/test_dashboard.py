from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.api.routes.dashboard import get_dashboard_aggregator
from app.core.config import settings
from app.main import app
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.jwt_auth import JWTAuthenticationMiddleware
from app.middleware.rate_limit import RateLimitMiddleware


SECRET = "dashboard-tests-only-secret-1234567890"


def token(**claims):
    return jwt.encode(
        {"sub": "viewer", "exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims},
        SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def dashboard(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    test_app = FastAPI()
    test_app.include_router(api_router)
    test_app.add_middleware(JWTAuthenticationMiddleware)
    test_app.add_middleware(RateLimitMiddleware, max_requests=1000)
    test_app.add_middleware(CorrelationIdMiddleware)
    aggregator = AsyncMock()
    aggregator.aggregate.return_value = {"scheduled": 3, "published": 5, "failed": 1}
    test_app.dependency_overrides[get_dashboard_aggregator] = lambda: aggregator
    with TestClient(test_app) as client:
        client.headers["Authorization"] = f"Bearer {token()}"
        yield client, aggregator


@pytest.mark.parametrize(
    "params, start, end",
    [
        ({}, None, None),
        ({"from": "2026-10-01"}, "2026-10-01T00:00:00+00:00", None),
        ({"to": "2026-10-05"}, None, "2026-10-05T23:59:59.999999+00:00"),
        (
            {"from": "2026-10-01", "to": "2026-10-01"},
            "2026-10-01T00:00:00+00:00", "2026-10-01T23:59:59.999999+00:00",
        ),
        (
            {"from": "2026-10-05T08:00:00-03:00", "to": "2026-10-05T11:00:00Z"},
            "2026-10-05T11:00:00+00:00", "2026-10-05T11:00:00+00:00",
        ),
    ],
)
def test_dashboard_passes_normalized_filters(dashboard, params, start, end):
    client, aggregator = dashboard
    response = client.get("/api/dashboard", params=params, headers={"X-Correlation-Id": "dashboard-test"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data": {"scheduled": 3, "published": 5, "failed": 1}}
    assert response.headers["X-Correlation-Id"] == "dashboard-test"
    aggregator.aggregate.assert_awaited_once_with(
        from_=datetime.fromisoformat(start) if start else None,
        to=datetime.fromisoformat(end) if end else None,
    )


@pytest.mark.parametrize(
    "params",
    [
        {"from": ""}, {"to": "not-a-date"}, {"from": "2026-02-30"},
        {"to": "2026-13-01"}, {"from": "1728000000"},
        {"from": "2026-10-05T12:00:00"},
        {"from": "2026-10-05", "to": "2026-10-04"},
        {"from": "2026-10-05T12:00:00-03:00", "to": "2026-10-05T14:00:00Z"},
        {"from": "0001-01-01T00:00:00+01:00"},
        {"to": "2026-10-05T25:00:00Z"},
        {"from": "2026-10-05T12:00:00+00:99"},
    ],
)
def test_invalid_range_is_standard_error_without_aggregation(dashboard, params):
    client, aggregator = dashboard
    response = client.get("/api/dashboard", params=params)
    assert response.status_code == 422
    assert response.json()["status"] == "error"
    assert response.json()["code"] == "INVALID_DATE_RANGE"
    assert set(response.json()) == {"status", "code", "message"}
    assert "X-Correlation-Id" in response.headers
    aggregator.aggregate.assert_not_called()


def test_empty_aggregation_returns_zero_counts(dashboard):
    client, aggregator = dashboard
    aggregator.aggregate.return_value = {"scheduled": 0, "published": 0, "failed": 0}
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    assert response.json()["data"] == {"scheduled": 0, "published": 0, "failed": 0}


@pytest.mark.parametrize("authorization", [None, "Basic invalid", "Bearer invalid", "expired"])
def test_dashboard_uses_d1_authentication(dashboard, authorization):
    client, aggregator = dashboard
    client.headers.pop("Authorization")
    if authorization == "expired":
        authorization = "Bearer " + token(exp=datetime.now(timezone.utc) - timedelta(minutes=1))
    response = client.get(
        "/api/dashboard",
        params={"from": "invalid"},
        headers={"Authorization": authorization} if authorization else {},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
    assert response.json()["status"] == "error"
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert "X-Correlation-Id" in response.headers
    aggregator.aggregate.assert_not_called()


def test_missing_aggregator_is_not_a_successful_empty_dashboard(dashboard):
    client, _ = dashboard
    client.app.dependency_overrides.clear()
    response = client.get("/api/dashboard")
    assert response.status_code == 503
    assert response.json()["code"] == "DASHBOARD_UNAVAILABLE"
    assert response.json()["status"] == "error"


def test_registered_aggregator_is_used(dashboard):
    client, aggregator = dashboard
    client.app.dependency_overrides.clear()
    client.app.state.dashboard_aggregator = aggregator
    assert client.get("/api/dashboard").status_code == 200
    aggregator.aggregate.assert_awaited_once_with(from_=None, to=None)


@pytest.mark.parametrize("error, status, code", [
    (TimeoutError("internal timeout details"), 504, "DASHBOARD_TIMEOUT"),
    (RuntimeError("internal credential details"), 500, "DASHBOARD_ERROR"),
])
def test_aggregation_errors_are_sanitized(dashboard, error, status, code):
    client, aggregator = dashboard
    aggregator.aggregate.side_effect = error
    response = client.get("/api/dashboard")
    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.json()["status"] == "error"
    assert "internal" not in response.text


@pytest.mark.parametrize("counts", [
    {"scheduled": -1, "published": 0, "failed": 0},
    {"scheduled": "3", "published": 0, "failed": 0},
    {"scheduled": True, "published": 0, "failed": 0},
    {},
])
def test_invalid_aggregates_are_not_exposed(dashboard, counts):
    client, aggregator = dashboard
    aggregator.aggregate.return_value = counts
    response = client.get("/api/dashboard")
    assert response.status_code == 500
    assert response.json()["code"] == "DASHBOARD_ERROR"


def test_rate_limit_keeps_standard_error_and_headers(dashboard):
    limited_app = FastAPI()
    limited_app.add_middleware(RateLimitMiddleware, max_requests=1)
    limited_app.add_middleware(CorrelationIdMiddleware)
    with TestClient(limited_app) as limited:
        limited.get("/api/dashboard")
        response = limited.get("/api/dashboard")
    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert response.json()["status"] == "error"
    assert int(response.headers["Retry-After"]) > 0
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert "X-Correlation-Id" in response.headers


def test_dashboard_is_registered_and_documented_in_real_app():
    schema = app.openapi()
    operation = schema["paths"]["/api/dashboard"]["get"]
    assert {p["name"] for p in operation["parameters"]} == {"from", "to"}
    assert all(not p["required"] for p in operation["parameters"])
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {"200", "401", "422", "429", "500", "503", "504"} <= operation["responses"].keys()
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/DashboardResponse")
    assert operation["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith("/DashboardError")
