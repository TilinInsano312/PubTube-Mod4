"""Verify the HTTP contract through real aggregation and a simulated M3 source."""

from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.core.config import settings
from app.main import app
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.jwt_auth import JWTAuthenticationMiddleware
from app.services.publication_dashboard import (
    PublicationDashboardService,
    PublicationRecord,
)


SECRET = "test-only-dashboard-integration-secret-123456789"
BASE_TIME = datetime(2026, 10, 1, tzinfo=timezone.utc)


def publication(identifier: str, state: str, day: int = 0) -> PublicationRecord:
    return PublicationRecord(
        id=identifier,
        content_id=f"content-{identifier}",
        state=state,
        schedule_at=BASE_TIME + timedelta(days=day),
        timezone="UTC",
    )


class SimulatedM3Source:
    """Return records without filtering, or reproduce a source failure."""

    def __init__(self) -> None:
        self.records: list[PublicationRecord] = []
        self.error: Exception | None = None
        self.calls: list[tuple[datetime | None, datetime | None]] = []

    async def list_publications(self, *, from_at=None, to_at=None):
        self.calls.append((from_at, to_at))
        if self.error is not None:
            raise self.error
        return self.records


@pytest.fixture
def dashboard_integration(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    test_app = FastAPI()
    test_app.include_router(api_router)
    test_app.add_middleware(JWTAuthenticationMiddleware)
    test_app.add_middleware(CorrelationIdMiddleware)
    source = SimulatedM3Source()
    test_app.state.dashboard_aggregator = PublicationDashboardService(source)
    with TestClient(test_app) as client:
        client.headers["Authorization"] = "Bearer " + jwt.encode(
            {"sub": "dashboard-viewer", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
            SECRET,
            algorithm="HS256",
        )
        yield client, source


@pytest.mark.parametrize("state", ["scheduled", "published", "failed"])
def test_endpoint_aggregates_each_state(dashboard_integration, state):
    client, source = dashboard_integration
    source.records = [publication("first", state), publication("second", state)]
    response = client.get("/api/dashboard", headers={"X-Correlation-Id": "dashboard-state"})
    expected = {"scheduled": 0, "published": 0, "failed": 0}
    expected[state] = 2
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data": expected}
    assert response.headers["X-Correlation-Id"] == "dashboard-state"
    assert source.calls == [(None, None)]


def test_endpoint_aggregates_combined_states(dashboard_integration):
    client, source = dashboard_integration
    source.records = [
        publication("s1", "scheduled"), publication("s2", "scheduled"),
        publication("p1", "published"), publication("f1", "failed"),
    ]
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data": {"scheduled": 2, "published": 1, "failed": 1}}


@pytest.mark.parametrize("params, expected, lower, upper", [
    (
        {"from": "2026-10-01"}, {"scheduled": 1, "published": 1, "failed": 1},
        BASE_TIME, None,
    ),
    (
        {"to": "2026-10-02"}, {"scheduled": 1, "published": 1, "failed": 1},
        None, datetime(2026, 10, 2, 23, 59, 59, 999999, tzinfo=timezone.utc),
    ),
    (
        {"from": "2026-10-01", "to": "2026-10-02"},
        {"scheduled": 1, "published": 1, "failed": 0},
        BASE_TIME, datetime(2026, 10, 2, 23, 59, 59, 999999, tzinfo=timezone.utc),
    ),
    (
        {"from": "2026-09-30T21:00:00-03:00", "to": "2026-10-01T00:00:00Z"},
        {"scheduled": 1, "published": 0, "failed": 0}, BASE_TIME, BASE_TIME,
    ),
])
def test_endpoint_filters_actual_records(dashboard_integration, params, expected, lower, upper):
    client, source = dashboard_integration
    source.records = [
        publication("before", "failed", -1), publication("start", "scheduled"),
        publication("end", "published", 1), publication("after", "failed", 2),
    ]
    response = client.get("/api/dashboard", params=params)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data": expected}
    assert source.calls == [(lower, upper)]


@pytest.mark.parametrize("records, params", [
    ([], {}),
    ([publication("outside", "scheduled")], {"from": "2026-11-01"}),
])
def test_endpoint_returns_empty_aggregation(dashboard_integration, records, params):
    client, source = dashboard_integration
    source.records = records
    response = client.get("/api/dashboard", params=params)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data": {"scheduled": 0, "published": 0, "failed": 0}}


@pytest.mark.parametrize("params", [
    {"from": "2026-02-30"}, {"to": "not-a-date"},
    {"from": "2026-10-03", "to": "2026-10-01"},
])
def test_invalid_date_never_reaches_m3_source(dashboard_integration, params):
    client, source = dashboard_integration
    response = client.get("/api/dashboard", params=params)
    assert response.status_code == 422
    assert response.json()["status"] == "error"
    assert response.json()["code"] == "INVALID_DATE_RANGE"
    assert source.calls == []


@pytest.mark.parametrize("error, status_code, code", [
    (httpx.ConnectError("private M3 connection detail"), 500, "DASHBOARD_ERROR"),
    (httpx.ReadTimeout("private M3 timeout detail"), 504, "DASHBOARD_TIMEOUT"),
    (
        httpx.HTTPStatusError(
            "private M3 server detail",
            request=httpx.Request("GET", "http://module3.test"),
            response=httpx.Response(503),
        ), 500, "DASHBOARD_ERROR",
    ),
])
def test_m3_failure_crosses_aggregation_and_preserves_standard_error(
    dashboard_integration, error, status_code, code,
):
    client, source = dashboard_integration
    source.error = error
    response = client.get("/api/dashboard", headers={"X-Correlation-Id": "m3-failure"})
    assert response.status_code == status_code
    assert set(response.json()) == {"status", "code", "message"}
    assert response.json()["status"] == "error"
    assert response.json()["code"] == code
    assert "private" not in response.text
    assert "data" not in response.json()
    assert response.headers["X-Correlation-Id"] == "m3-failure"
    assert source.calls == [(None, None)]


def test_d1_blocks_source_access_without_jwt(dashboard_integration):
    client, source = dashboard_integration
    client.headers.pop("Authorization")
    response = client.get("/api/dashboard")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert source.calls == []


def test_real_gateway_serves_registered_domain_aggregation(dashboard_integration, monkeypatch):
    client, source = dashboard_integration
    source.records = [publication("real-route", "published")]
    monkeypatch.setattr(app.state, "dashboard_aggregator", PublicationDashboardService(source), raising=False)
    with TestClient(app) as gateway:
        response = gateway.get("/api/dashboard", headers={"Authorization": client.headers["Authorization"]})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data": {"scheduled": 0, "published": 1, "failed": 0}}
