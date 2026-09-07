"""Configurable in-memory rate limiting for Gateway requests."""

from collections.abc import Callable, Collection
from dataclasses import dataclass
from math import ceil
from threading import Lock
from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from ..core.config import settings


RATE_LIMIT_EXCLUDED_PATHS = frozenset({"/api/health", "/api/health/"})


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of evaluating one request against a fixed-window limit."""

    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int | None = None


@dataclass
class _Window:
    """Mutable counter for one client and one fixed time window."""

    started_at: float
    count: int = 0


class InMemoryRateLimiter:
    """Track request counts in process memory using fixed time windows."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be greater than zero")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._windows: dict[str, _Window] = {}
        self._lock = Lock()

    def check(self, client_key: str) -> RateLimitDecision:
        """Consume one request slot and return the resulting decision."""

        now = self._clock()
        with self._lock:
            window = self._windows.get(client_key)
            if window is None or now - window.started_at >= self.window_seconds:
                window = _Window(started_at=now)
                self._windows[client_key] = window

            if window.count >= self.max_requests:
                retry_after = max(
                    1,
                    ceil(window.started_at + self.window_seconds - now),
                )
                return RateLimitDecision(
                    allowed=False,
                    limit=self.max_requests,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            window.count += 1
            return RateLimitDecision(
                allowed=True,
                limit=self.max_requests,
                remaining=self.max_requests - window.count,
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limit requests per client while leaving the health route available."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_requests: int | None = None,
        window_seconds: float | None = None,
        excluded_paths: Collection[str] = RATE_LIMIT_EXCLUDED_PATHS,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        super().__init__(app)
        self.excluded_paths = frozenset(excluded_paths)
        self.limiter = InMemoryRateLimiter(
            max_requests=(
                settings.rate_limit_requests
                if max_requests is None
                else max_requests
            ),
            window_seconds=(
                settings.rate_limit_window_seconds
                if window_seconds is None
                else window_seconds
            ),
            clock=clock,
        )

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Apply the configured limit or return HTTP 429."""

        if request.url.path in self.excluded_paths:
            return await call_next(request)

        decision = self.limiter.check(_client_key(request))
        headers = {
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": str(decision.remaining),
        }

        if not decision.allowed:
            headers["Retry-After"] = str(decision.retry_after_seconds)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers=headers,
            )

        response = await call_next(request)
        for name, value in headers.items():
            response.headers[name] = value
        return response


def _client_key(request: Request) -> str:
    """Return the client identity supplied by the trusted edge when present."""

    real_ip = request.headers.get("X-Real-IP")
    if real_ip and real_ip.strip():
        return real_ip.strip()

    if request.client is not None and request.client.host:
        return request.client.host

    return "unknown"
