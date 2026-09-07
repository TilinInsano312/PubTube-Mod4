"""Shared helpers for forwarding Gateway requests to internal modules."""

from urllib.parse import quote

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from ...clients.errors import (
    UpstreamError,
    UpstreamHTTPError,
    UpstreamTimeoutError,
)
from ...clients.http import HOP_BY_HOP_HEADERS
from ...services.upstreams import UpstreamModule, UpstreamService


def quote_path_segment(value: str) -> str:
    """Encode one public path parameter before adding it to an upstream path."""

    return quote(value, safe="")


def quote_nested_path(value: str) -> str:
    """Encode a catch-all path while preserving its path separators."""

    return quote(value, safe="/")


async def proxy_request(
    request: Request,
    upstream_service: UpstreamService,
    module: UpstreamModule,
    path: str,
) -> Response:
    """Forward a request to a configured module and preserve its response.

    Args:
        request: Incoming Gateway request.
        upstream_service: Configured service boundary for internal modules.
        module: Module that owns the selected route.
        path: Explicit relative path on the selected module.

    Returns:
        The upstream response, or a stable Gateway error when the module
        cannot be reached.
    """

    try:
        upstream_response = await upstream_service.client_for(module).request(
            method=request.method,
            path=path,
            headers=request.headers,
            params=list(request.query_params.multi_items()),
            content=await request.body(),
            correlation_id=getattr(request.state, "correlation_id", None),
            raise_for_status=False,
        )
    except UpstreamTimeoutError as exc:
        return _upstream_error_response(exc, status_code=504)
    except UpstreamHTTPError as exc:
        return _upstream_error_response(exc, status_code=exc.status_code)
    except UpstreamError as exc:
        return _upstream_error_response(exc, status_code=502)
    except ValueError:
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Upstream module configuration is invalid",
                "code": "UPSTREAM_CONFIGURATION_ERROR",
                "module": module.value,
            },
        )

    return _response_from_upstream(upstream_response)


def _response_from_upstream(upstream_response: httpx.Response) -> Response:
    """Convert an HTTPX response into a safe FastAPI response."""

    headers = {
        name: value
        for name, value in upstream_response.headers.items()
        if name.lower() not in HOP_BY_HOP_HEADERS
    }
    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=headers,
    )


def _upstream_error_response(error: UpstreamError, *, status_code: int) -> JSONResponse:
    """Build a non-sensitive response for an upstream transport failure."""

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": str(error),
            "code": error.code,
            "module": error.module,
        },
    )
