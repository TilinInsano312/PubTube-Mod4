"""Exercise Gateway forwarding through the real dashboard API and domain service."""

import asyncio
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_upstream_service
from app.core.config import settings
from app.main import app as gateway
from app.services.upstreams import UpstreamService
from dashboard_app.main import create_app
from dashboard_app.services.publication_dashboard import PublicationDashboardService, PublicationRecord


@pytest.fixture
def stack(monkeypatch):
    monkeypatch.setattr(settings, "public_test_routes", False)
    monkeypatch.setattr(settings, "dashboard_url", "http://dashboard.test")
    calls = []

    class Source:
        async def list_publications(self, **filters):
            calls.append(filters)
            return [PublicationRecord("one", "content-one", "published", datetime(2026, 10, 1, tzinfo=timezone.utc), "UTC")]

    dashboard = create_app()
    dashboard.state.dashboard_aggregator = PublicationDashboardService(Source())
    upstream_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=dashboard))
    service = UpstreamService(client=upstream_client, timeout=httpx.Timeout(2), config=settings)
    gateway.dependency_overrides[get_upstream_service] = lambda: service
    try:
        with TestClient(gateway) as client:
            yield client, calls, dashboard
    finally:
        gateway.dependency_overrides.pop(get_upstream_service, None)
        asyncio.run(upstream_client.aclose())


def test_public_request_reaches_real_aggregation(stack):
    client, calls, dashboard = stack
    response = client.get("/api/dashboard", headers={"X-Correlation-Id": "stack-smoke"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data": {"scheduled": 0, "published": 1, "failed": 0}}
    assert response.headers["X-Correlation-Id"] == "stack-smoke"
    assert calls == [{"from_at": None, "to_at": None}]
    assert dashboard.state.request_count.labels(method="GET", route="/api/dashboard", status="200")._value.get() == 1


@pytest.mark.parametrize("params,expected", [
    ({"from": "2026-10-02"}, 0), ({"from": "2026-10-01", "to": "2026-10-01"}, 1),
])
def test_dates_are_validated_and_filtered_by_dashboard_service(stack, params, expected):
    client, calls, _ = stack
    response = client.get("/api/dashboard", params=params)
    assert response.status_code == 200
    assert response.json()["data"]["published"] == expected
    assert len(calls) == 1


def test_invalid_dates_never_call_publication_source(stack):
    client, calls, _ = stack
    response = client.get("/api/dashboard?from=invalid")
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_DATE_RANGE"
    assert calls == []
