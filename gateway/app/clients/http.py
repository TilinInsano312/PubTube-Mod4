"""HTTP client abstraction for controlled upstream module calls."""

from collections.abc import AsyncIterable, Mapping, Sequence
from typing import Any

import httpx

from .errors import (
    UpstreamHTTPError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)

HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "content-length",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
QueryParamValue = str | int | float | None
QueryParams = Mapping[str, QueryParamValue] | Sequence[tuple[str, QueryParamValue]]
RequestContent = bytes | AsyncIterable[bytes]


def build_forward_headers(
    headers: Mapping[str, str] | None = None,
    *,
    correlation_id: str | None = None,
) -> dict[str, str]:
    """Filter request headers and optionally set the application correlation ID.

    Args:
        headers: Headers received from the caller.
        correlation_id: Correlation ID generated or selected by the Gateway.

    Returns:
        Headers safe to pass to an upstream HTTP request.
    """

    incoming_headers = headers or {}
    hop_by_hop_headers = set(HOP_BY_HOP_HEADERS)

    # RFC 9110 allows Connection to nominate additional hop-by-hop fields.
    # Those fields must not cross the proxy boundary either.
    for name, value in incoming_headers.items():
        if name.lower() == "connection":
            hop_by_hop_headers.update(
                token.strip().lower() for token in value.split(",") if token.strip()
            )

    forwarded: dict[str, str] = {}
    for name, value in incoming_headers.items():
        normalized_name = name.lower()
        if normalized_name in hop_by_hop_headers or normalized_name == "host":
            continue
        forwarded[name] = value

    if correlation_id is not None:
        for name in list(forwarded):
            if name.lower() == "x-correlation-id":
                del forwarded[name]
        forwarded["X-Correlation-Id"] = correlation_id

    return forwarded


class UpstreamHttpClient:
    """Make controlled asynchronous requests to one configured module."""

    def __init__(
        self,
        *,
        module: str,
        base_url: str,
        client: httpx.AsyncClient,
        timeout: httpx.Timeout,
    ) -> None:
        if not base_url or not base_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid base URL for upstream module: {module}")

        self.module = module
        self.base_url = base_url.rstrip("/")
        self._client = client
        self.timeout = timeout

    def build_url(self, path: str) -> str:
        """Build a URL from a relative, explicitly selected upstream path."""

        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Upstream paths must be relative and start with '/'")
        return f"{self.base_url}{path}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: QueryParams | None = None,
        content: RequestContent | None = None,
        json: Any = None,
        correlation_id: str | None = None,
        raise_for_status: bool = True,
    ) -> httpx.Response:
        """Execute an asynchronous request against the configured module.

        Args:
            method: HTTP method to send.
            path: Relative path explicitly selected by a future BFF service.
            headers: End-to-end request headers to forward.
            params: Query parameters for the upstream request.
            content: Optional raw request body or asynchronous byte stream.
            json: Optional JSON request body.
            correlation_id: Application correlation ID to propagate.
            raise_for_status: Whether to map upstream 4xx/5xx responses to an
                ``UpstreamHTTPError``. Gateway proxy routes disable this to
                preserve the upstream response contract.

        Returns:
            The successful upstream response.

        Raises:
            UpstreamTimeoutError: If the upstream exceeds its timeout.
            UpstreamUnavailableError: If the upstream cannot be reached.
            UpstreamHTTPError: If the upstream returns a 4xx or 5xx response.
        """

        try:
            response = await self._client.request(
                method=method,
                url=self.build_url(path),
                headers=build_forward_headers(headers, correlation_id=correlation_id),
                params=params,
                content=content,
                json=json,
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError(self.module) from exc
        except httpx.RequestError as exc:
            raise UpstreamUnavailableError(self.module) from exc

        if raise_for_status and response.is_error:
            raise UpstreamHTTPError(self.module, response.status_code)

        return response
