"""Errors raised while communicating with upstream modules."""


class UpstreamError(RuntimeError):
    """Base error for an unavailable or unsuccessful upstream module."""

    code = "UPSTREAM_ERROR"

    def __init__(self, module: str, message: str) -> None:
        super().__init__(message)
        self.module = module


class UpstreamTimeoutError(UpstreamError):
    """Raised when an upstream request exceeds its configured timeout."""

    code = "UPSTREAM_TIMEOUT"

    def __init__(self, module: str) -> None:
        super().__init__(module, f"Upstream module timed out: {module}")


class UpstreamUnavailableError(UpstreamError):
    """Raised when an upstream connection cannot be established."""

    code = "UPSTREAM_UNAVAILABLE"

    def __init__(self, module: str) -> None:
        super().__init__(module, f"Upstream module unavailable: {module}")


class UpstreamHTTPError(UpstreamError):
    """Raised when an upstream returns an HTTP error response."""

    code = "UPSTREAM_HTTP_ERROR"

    def __init__(self, module: str, status_code: int) -> None:
        super().__init__(
            module, f"Upstream module returned HTTP {status_code}: {module}"
        )
        self.status_code = status_code
