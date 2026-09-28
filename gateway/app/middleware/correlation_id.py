"""Correlation ID middleware for Gateway requests and responses."""

import logging
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from ..observability.logging import (
    get_logger,
    reset_log_context,
    set_log_context,
)


CORRELATION_ID_HEADER = "X-Correlation-Id"
MAX_CORRELATION_ID_LENGTH = 128
logger = get_logger()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Keep or generate a correlation ID for the lifetime of a request."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        correlation_id = _resolve_correlation_id(
            request.headers.get(CORRELATION_ID_HEADER)
        )

        request.state.correlation_id = correlation_id
        request.state.causation_id = None
        context_tokens = set_log_context(correlation_id)
        started_at = perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            _log_request(
                request,
                status_code=500,
                duration_ms=_duration_ms(started_at),
                error_code="INTERNAL_SERVER_ERROR",
                error_type=type(exc).__name__,
            )
            raise
        else:
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            _log_request(
                request,
                status_code=response.status_code,
                duration_ms=_duration_ms(started_at),
                error_code=(
                    f"HTTP_{response.status_code}"
                    if response.status_code >= 400
                    else None
                ),
            )
            return response
        finally:
            reset_log_context(context_tokens)


def _resolve_correlation_id(value: str | None) -> str:
    """Reuse a safe incoming ID or generate a UUID v4 when absent."""

    candidate = (value or "").strip()
    if (
        candidate
        and len(candidate) <= MAX_CORRELATION_ID_LENGTH
        and not any(
            ord(character) < 32 or ord(character) == 127
            for character in candidate
        )
    ):
        return candidate
    return str(uuid4())


def _duration_ms(started_at: float) -> float:
    """Return elapsed request time in milliseconds."""

    return round((perf_counter() - started_at) * 1000, 2)


def _log_request(
    request: Request,
    *,
    status_code: int,
    duration_ms: float,
    error_code: str | None = None,
    error_type: str | None = None,
) -> None:
    """Write a safe structured request completion or failure record."""

    extra: dict[str, object] = {
        "route": request.url.path,
        "method": request.method,
        "statusCode": status_code,
        "durationMs": duration_ms,
    }
    if error_code is not None:
        extra["errorCode"] = error_code
    if error_type is not None:
        extra["errorType"] = error_type

    if status_code >= 500:
        level = logging.ERROR
    elif status_code >= 400:
        level = logging.WARNING
    else:
        level = logging.INFO

    logger.log(
        level,
        "request failed" if status_code >= 400 else "request completed",
        extra=extra,
    )
