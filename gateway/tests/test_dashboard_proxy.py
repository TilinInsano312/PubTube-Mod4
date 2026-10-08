"""Verify the public dashboard boundary without importing its implementation."""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_upstream_service
from app.api.router import api_router
from app.core.config import settings
from app.main import app
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.jwt_auth import JWTAuthenticationMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.upstreams import UpstreamService


@pytest.fixture
def dashboard_proxy(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_url", "http://dashboard.test")
    monkeypatch.setattr(settings, "public_test_routes", False)
    monkeypatch.setattr(settings, "jwt_secret", "dashboard-proxy-test-secret-1234567890")
    observed = []

    async def handler(request):
        observed.append(request)
        if request.url.params.get("failure") == "timeout":
            raise httpx.ReadTimeout("private connection", request=request)
        if request.url.params.get("failure") == "connect":
            raise httpx.ConnectError("private connection", request=request)
        status = int(request.url.params.get("status", "200"))
        payload = {"status": "ok", "data": {"scheduled": 3, "published": 5, "failed": 1}}
        if status != 200:
            payload = {"status": "error", "code": "DASHBOARD_ERROR", "message": "Source failure"}
        return httpx.Response(status, json=payload, headers={"X-Upstream": "dashboard"})

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    upstream_service = UpstreamService(client=upstream_client, timeout=httpx.Timeout(2), config=settings)
    test_app = FastAPI()
    test_app.include_router(api_router)
    test_app.add_middleware(JWTAuthenticationMiddleware)
    test_app.add_middleware(RateLimitMiddleware, max_requests=1000)
    test_app.add_middleware(CorrelationIdMiddleware)
    test_app.dependency_overrides[get_upstream_service] = lambda: upstream_service
    try:
        with TestClient(test_app) as client:
            yield client, observed
    finally:
        asyncio.run(upstream_client.aclose())


@pytest.mark.parametrize("authorization", [None, "Basic invalid", "Bearer invalid", "expired"])
@pytest.mark.parametrize("path", ["/api/dashboard", "/api/dashboard/"])
def test_dashboard_is_public_even_with_invalid_credentials(dashboard_proxy, authorization, path):
    client, observed = dashboard_proxy
    if authorization == "expired":
        authorization = "Bearer " + jwt.encode(
            {"sub": "viewer", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
            settings.jwt_secret, algorithm="HS256",
        )
    response = client.get(path, headers={"Authorization": authorization} if authorization else {})
    assert response.status_code == 200
    assert "WWW-Authenticate" not in response.headers
    assert len(observed) == 1


def test_proxy_preserves_filters_and_correlation(dashboard_proxy):
    client, observed = dashboard_proxy
    response = client.get(
        "/api/dashboard", params=[("from", "2026-10-01"), ("to", "2026-10-05"), ("tag", "a"), ("tag", "b")],
        headers={"X-Correlation-Id": "dashboard-proxy"},
    )
    assert response.json() == {"status": "ok", "data": {"scheduled": 3, "published": 5, "failed": 1}}
    assert response.headers["X-Correlation-Id"] == "dashboard-proxy"
    assert response.headers["X-Upstream"] == "dashboard"
    assert observed[0].url.path == "/api/dashboard"
    assert str(observed[0].url).startswith("http://dashboard.test/")
    assert observed[0].url.params.get_list("tag") == ["a", "b"]
    assert observed[0].url.params["from"] == "2026-10-01"
    assert observed[0].url.params["to"] == "2026-10-05"
    assert observed[0].headers["X-Correlation-Id"] == "dashboard-proxy"


@pytest.mark.parametrize("status", [422, 500, 503, 504])
def test_proxy_preserves_dashboard_error_contract(dashboard_proxy, status):
    client, _ = dashboard_proxy
    response = client.get("/api/dashboard", params={"status": status})
    assert response.status_code == status
    assert response.json() == {"status": "error", "code": "DASHBOARD_ERROR", "message": "Source failure"}


@pytest.mark.parametrize("failure,status,code", [
    ("timeout", 504, "DASHBOARD_TIMEOUT"), ("connect", 503, "DASHBOARD_UNAVAILABLE"),
])
def test_transport_errors_preserve_dashboard_envelope(dashboard_proxy, failure, status, code):
    client, _ = dashboard_proxy
    response = client.get("/api/dashboard", params={"failure": failure})
    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.json()["status"] == "error"
    assert "private" not in response.text


@pytest.mark.parametrize("path", ["/api/events", "/api/dashboard/private", "/api/dashboard-other"])
def test_other_routes_still_require_jwt(dashboard_proxy, path):
    client, observed = dashboard_proxy
    assert client.get(path).status_code == 401
    assert observed == []


def test_public_dashboard_keeps_rate_limiting():
    limited_app = FastAPI()
    limited_app.add_middleware(JWTAuthenticationMiddleware)
    limited_app.add_middleware(RateLimitMiddleware, max_requests=1)
    limited_app.add_middleware(CorrelationIdMiddleware)
    with TestClient(limited_app) as client:
        client.get("/api/dashboard")
        response = client.get("/api/dashboard")
    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert int(response.headers["Retry-After"]) > 0
    assert "X-Correlation-Id" in response.headers


def test_gateway_documents_dashboard_without_bearer():
    operation = app.openapi()["paths"]["/api/dashboard"]["get"]
    assert not operation.get("security")
    assert "401" not in operation["responses"]
    assert {p["name"] for p in operation["parameters"]} == {"from", "to"}
    assert {"200", "422", "429", "500", "503", "504"} <= operation["responses"].keys()
