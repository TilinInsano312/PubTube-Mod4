"""Structured logging and request context utilities for the Gateway."""

from .logging import (
    DEFAULT_ENVIRONMENT,
    DEFAULT_SERVICE_NAME,
    JsonLogFormatter,
    configure_structured_logging,
    get_correlation_id,
    get_causation_id,
    get_logger,
    reset_log_context,
    set_log_context,
)

__all__ = [
    "DEFAULT_ENVIRONMENT",
    "DEFAULT_SERVICE_NAME",
    "JsonLogFormatter",
    "configure_structured_logging",
    "get_correlation_id",
    "get_causation_id",
    "get_logger",
    "reset_log_context",
    "set_log_context",
]
