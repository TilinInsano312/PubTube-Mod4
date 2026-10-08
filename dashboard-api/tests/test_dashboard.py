from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from dashboard_app.api.routes.dashboard import get_dashboard_aggregator
from dashboard_app.main import app, create_app


@pytest.fixture
def dashboard():
    test_app = create_app()
    aggregator = AsyncMock()
    aggregator.aggregate.return_value = {"scheduled": 3, "published": 5, "failed": 1}
    test_app.dependency_overrides[get_dashboard_aggregator] = lambda: aggregator
    with TestClient(test_app) as client:
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


@pytest.mark.parametrize("authorization", [None, "Basic invalid", "Bearer invalid"])
def test_dashboard_does_not_require_jwt(dashboard, authorization):
    client, aggregator = dashboard
    response = client.get(
        "/api/dashboard",
        headers={"Authorization": authorization} if authorization else {},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "WWW-Authenticate" not in response.headers
    assert "X-Correlation-Id" in response.headers
    aggregator.aggregate.assert_awaited_once_with(from_=None, to=None)


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


def test_dashboard_is_public_and_documented_in_real_app():
    schema = app.openapi()
    operation = schema["paths"]["/api/dashboard"]["get"]
    assert {p["name"] for p in operation["parameters"]} == {"from", "to"}
    assert all(not p["required"] for p in operation["parameters"])
    assert not operation.get("security")
    assert "401" not in operation["responses"]
    assert {"200", "422", "500", "503", "504"} <= operation["responses"].keys()
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/DashboardResponse")
    assert operation["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith("/DashboardError")
