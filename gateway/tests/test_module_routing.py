import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_upstream_service
from app.core.config import settings
from app.main import app
from app.services.upstreams import UpstreamService


JWT_SECRET = "test-only-routing-secret-123456789"
JWT_ALGORITHM = "HS256"
TIMEOUT = httpx.Timeout(connect=1, read=2, write=3, pool=4)


def create_token() -> str:
    """Create a short-lived token for protected routing tests."""

    payload = {
        "sub": "routing-user",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@pytest.fixture
def routing_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, list[httpx.Request]]]:
    monkeypatch.setattr(settings, "jwt_secret", JWT_SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", JWT_ALGORITHM)
    monkeypatch.setattr(settings, "module1_url", "http://module1.test")
    monkeypatch.setattr(settings, "module2_url", "http://module2.test")
    monkeypatch.setattr(settings, "module3_url", "http://module3.test")

    observed: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        if request.url.params.get("failure") == "connect":
            raise httpx.ConnectError("module unavailable", request=request)
        if request.url.params.get("failure") == "status":
            return httpx.Response(
                503,
                content=b'{"detail":"module unavailable"}',
                headers={"X-Upstream-Error": "true"},
                request=request,
            )
        return httpx.Response(
            201 if request.url.path == "/content" and request.method == "POST" else 200,
            content=b'{"accepted":true}',
            headers={"Content-Type": "application/json", "X-Upstream": "stub"},
            request=request,
        )

    upstream_http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    upstream_service = UpstreamService(
        client=upstream_http_client,
        timeout=TIMEOUT,
        config=settings,
    )
    app.dependency_overrides[get_upstream_service] = lambda: upstream_service

    try:
        with TestClient(app) as client:
            yield client, observed
    finally:
        app.dependency_overrides.pop(get_upstream_service, None)
        asyncio.run(upstream_http_client.aclose())


@pytest.mark.parametrize(
    ("method", "path", "expected_url"),
    [
        ("POST", "/api/content?draft=true", "http://module1.test/content?draft=true"),
        (
            "PUT",
            "/api/content/content-123/metadata?lang=es",
            "http://module1.test/content/content-123/metadata?lang=es",
        ),
        (
            "GET",
            "/api/content/videos/nested?tag=a&tag=b",
            "http://module1.test/content/videos/nested?tag=a&tag=b",
        ),
        (
            "GET",
            "/api/events/correlation-123?limit=10",
            "http://module2.test/events/correlation-123?limit=10",
        ),
        (
            "POST",
            "/api/publish/schedule",
            "http://module3.test/publish/schedule",
        ),
        (
            "POST",
            "/api/publish/publication-123/now",
            "http://module3.test/publish/publication-123/now",
        ),
        (
            "GET",
            "/api/publish/publication-123/status",
            "http://module3.test/publish/publication-123/status",
        ),
    ],
)
def test_module_routes_preserve_method_path_and_query(
    routing_client: tuple[TestClient, list[httpx.Request]],
    method: str,
    path: str,
    expected_url: str,
) -> None:
    client, observed = routing_client

    response = client.request(
        method,
        path,
        headers={
            "Authorization": f"Bearer {create_token()}",
            "X-Correlation-Id": "route-correlation-id",
        },
        content=b'{"contentId":"content-123"}' if method != "GET" else None,
    )

    assert response.status_code in {200, 201}
    assert response.json() == {"accepted": True}
    assert response.headers["X-Upstream"] == "stub"
    assert len(observed) == 1
    assert observed[0].method == method
    assert str(observed[0].url) == expected_url
    assert observed[0].headers["Authorization"].startswith("Bearer ")
    assert observed[0].headers["X-Correlation-Id"] == "route-correlation-id"


def test_module_route_preserves_request_body(
    routing_client: tuple[TestClient, list[httpx.Request]],
) -> None:
    client, observed = routing_client
    body = b'{"title":"Nuevo titulo"}'

    response = client.put(
        "/api/content/content-123/metadata",
        content=body,
        headers={"Authorization": f"Bearer {create_token()}"},
    )

    assert response.status_code == 200
    assert observed[0].content == body


def test_upstream_status_body_and_headers_are_propagated(
    routing_client: tuple[TestClient, list[httpx.Request]],
) -> None:
    client, observed = routing_client

    response = client.get(
        "/api/events/correlation-123?failure=status",
        headers={"Authorization": f"Bearer {create_token()}"},
    )

    assert response.status_code == 503
    assert response.content == b'{"detail":"module unavailable"}'
    assert response.headers["X-Upstream-Error"] == "true"
    assert len(observed) == 1


def test_unavailable_upstream_returns_gateway_error(
    routing_client: tuple[TestClient, list[httpx.Request]],
) -> None:
    client, _ = routing_client

    response = client.get(
        "/api/events/correlation-123?failure=connect",
        headers={"Authorization": f"Bearer {create_token()}"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Upstream module unavailable: module2",
        "code": "UPSTREAM_UNAVAILABLE",
        "module": "module2",
    }


def test_module_route_requires_jwt_before_calling_upstream(
    routing_client: tuple[TestClient, list[httpx.Request]],
) -> None:
    client, observed = routing_client

    response = client.get("/api/events/correlation-123")

    assert response.status_code == 401
    assert observed == []


def test_health_route_remains_a_local_module4_route(
    routing_client: tuple[TestClient, list[httpx.Request]],
) -> None:
    client, observed = routing_client

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "gateway"}
    assert observed == []
