"""Reusable clients for Gateway upstream modules."""

from .errors import (
    UpstreamError,
    UpstreamHTTPError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from .http import UpstreamHttpClient, build_forward_headers

__all__ = [
    "UpstreamError",
    "UpstreamHTTPError",
    "UpstreamHttpClient",
    "UpstreamTimeoutError",
    "UpstreamUnavailableError",
    "build_forward_headers",
]
