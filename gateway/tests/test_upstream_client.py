import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.clients.errors import (
    UpstreamHTTPError,
    UpstreamTimeoutError,
)
from app.clients.http import UpstreamHttpClient, build_forward_headers
from app.main import app
from app.services.upstreams import UpstreamModule

TIMEOUT = httpx.Timeout(connect=1, read=2, write=3, pool=4)


def run(coroutine: object) -> object:
    """Run one async client operation from the synchronous test suite."""

    return asyncio.run(coroutine)  # type: ignore[arg-type]


def test_build_forward_headers_filters_hop_by_hop_headers() -> None:
    headers = build_forward_headers(
        {
            "Host": "frontend.example",
            "Authorization": "Bearer token",
            "Connection": "keep-alive",
            "X-Correlation-Id": "incoming-id",
        },
        correlation_id="application-id",
    )

    assert "Host" not in headers
    assert "Connection" not in headers
    assert headers["Authorization"] == "Bearer token"
    assert headers["X-Correlation-Id"] == "application-id"


def test_client_builds_explicit_relative_upstream_url_and_propagates_headers() -> None:
    observed: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["correlation_id"] = request.headers["X-Correlation-Id"]
        return httpx.Response(200, json={"status": "ok"}, request=request)

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = UpstreamHttpClient(
        module="module1",
        base_url="http://module-one.test/",
        client=async_client,
        timeout=TIMEOUT,
    )

    response = run(
        client.request(
            "GET",
            "/content",
            headers={"X-Correlation-Id": "incoming-id"},
            correlation_id="application-id",
        )
    )
    run(async_client.aclose())

    assert response.status_code == 200  # type: ignore[union-attr]
    assert observed == {
        "url": "http://module-one.test/content",
        "correlation_id": "application-id",
    }


def test_client_rejects_absolute_or_non_rooted_paths() -> None:
    async_client = httpx.AsyncClient()
    client = UpstreamHttpClient(
        module="module1",
        base_url="http://module-one.test",
        client=async_client,
        timeout=TIMEOUT,
    )

    with pytest.raises(ValueError):
        client.build_url("https://untrusted.example/path")
    with pytest.raises(ValueError):
        client.build_url("content")

    run(async_client.aclose())


def test_client_maps_timeout_without_exposing_internal_exception() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("internal timeout", request=request)

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = UpstreamHttpClient(
        module="module1",
        base_url="http://module-one.test",
        client=async_client,
        timeout=TIMEOUT,
    )

    with pytest.raises(UpstreamTimeoutError) as error:
        run(client.request("GET", "/content"))
    run(async_client.aclose())

    assert error.value.code == "UPSTREAM_TIMEOUT"
    assert error.value.module == "module1"
    assert "internal timeout" not in str(error.value)


def test_client_maps_upstream_http_errors() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = UpstreamHttpClient(
        module="module2",
        base_url="http://module-two.test",
        client=async_client,
        timeout=TIMEOUT,
    )

    with pytest.raises(UpstreamHTTPError) as error:
        run(client.request("GET", "/events"))
    run(async_client.aclose())

    assert error.value.code == "UPSTREAM_HTTP_ERROR"
    assert error.value.status_code == 503


def test_application_lifespan_closes_shared_http_client() -> None:
    with TestClient(app):
        upstream_service = app.state.upstream_service
        shared_client = upstream_service._client
        assert not shared_client.is_closed
        assert upstream_service.client_for(UpstreamModule.MODULE1).base_url

    assert shared_client.is_closed
