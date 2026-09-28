"""Structured JSON logging and request-scoped observability context."""

from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any

from .tracing import get_span_id, get_trace_id


DEFAULT_SERVICE_NAME = "module4-gateway"
DEFAULT_ENVIRONMENT = "local"
LOGGER_NAME = "pubtube.gateway"

_correlation_id: ContextVar[str | None] = ContextVar(
    "pubtube_correlation_id",
    default=None,
)
_causation_id: ContextVar[str | None] = ContextVar(
    "pubtube_causation_id",
    default=None,
)

LogContextTokens = tuple[Token[str | None], Token[str | None]]


def get_logger() -> logging.Logger:
    """Return the application logger used by Gateway components."""

    return logging.getLogger(LOGGER_NAME)


def configure_structured_logging(
    *,
    service: str = DEFAULT_SERVICE_NAME,
    environment: str = DEFAULT_ENVIRONMENT,
) -> logging.Logger:
    """Configure one idempotent JSON stdout handler for Gateway logs.

    Args:
        service: Logical service name written to each log record.
        environment: Deployment environment written to each log record.

    Returns:
        The configured application logger.
    """

    logger = get_logger()
    if getattr(logger, "_structured_logging_configured", False):
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonLogFormatter(service=service, environment=environment)
    )
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    logger._structured_logging_configured = True  # type: ignore[attr-defined]
    return logger


def set_log_context(
    correlation_id: str,
    causation_id: str | None = None,
) -> LogContextTokens:
    """Set request-scoped identifiers and return tokens for later reset."""

    return (
        _correlation_id.set(correlation_id),
        _causation_id.set(causation_id),
    )


def reset_log_context(tokens: LogContextTokens) -> None:
    """Restore the previous request-scoped identifiers."""

    correlation_token, causation_token = tokens
    _causation_id.reset(causation_token)
    _correlation_id.reset(correlation_token)


def get_correlation_id() -> str | None:
    """Return the correlation ID for the current execution context."""

    return _correlation_id.get()


def get_causation_id() -> str | None:
    """Return the optional causation ID for the current execution context."""

    return _causation_id.get()


class JsonLogFormatter(logging.Formatter):
    """Format application log records as one JSON object per line."""

    _OPTIONAL_FIELDS = (
        "route",
        "method",
        "statusCode",
        "durationMs",
        "errorCode",
        "errorType",
        "upstreamService",
        "upstreamStatusCode",
    )

    def __init__(
        self,
        *,
        service: str = DEFAULT_SERVICE_NAME,
        environment: str = DEFAULT_ENVIRONMENT,
    ) -> None:
        super().__init__()
        self.service = service
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record with the common observability fields."""

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            )
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "service": self.service,
            "environment": self.environment,
            "correlationId": get_correlation_id(),
            "causationId": get_causation_id(),
            "traceId": get_trace_id(),
            "spanId": get_span_id(),
            "eventId": getattr(record, "eventId", None),
            "message": record.getMessage(),
        }

        for field_name in self._OPTIONAL_FIELDS:
            if hasattr(record, field_name):
                payload[field_name] = getattr(record, field_name)

        if record.exc_info:
            payload["errorType"] = record.exc_info[0].__name__

        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
