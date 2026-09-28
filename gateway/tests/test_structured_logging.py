import json
import logging
from collections.abc import Iterator
from io import StringIO
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.clients.http import build_forward_headers
from app.main import app
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.observability.logging import (
    JsonLogFormatter,
    get_correlation_id,
    get_logger,
    reset_log_context,
    set_log_context,
)


@pytest.fixture
def log_stream() -> Iterator[StringIO]:
    """Capture structured application records without replacing stdout."""

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger = get_logger()
    logger.addHandler(handler)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)


def _last_log(stream: StringIO) -> dict[str, object]:
    """Return the last JSON record emitted to the test stream."""

    records = [line for line in stream.getvalue().splitlines() if line]
    assert records
    return json.loads(records[-1])


def test_request_log_contains_common_structured_fields(
    log_stream: StringIO,
) -> None:
    correlation_id = "structured-correlation-id"

    with TestClient(app) as client:
        response = client.get(
            "/api/health",
            headers={"X-Correlation-Id": correlation_id},
        )

    record = _last_log(log_stream)

    assert response.status_code == 200
    assert record["timestamp"]
    assert record["level"] == "INFO"
    assert record["service"] == "module4-gateway"
    assert record["environment"] == "local"
    assert record["correlationId"] == correlation_id
    assert record["causationId"] is None
    assert record["message"] == "request completed"
    assert record["route"] == "/api/health"
    assert record["method"] == "GET"
    assert record["statusCode"] == 200
    assert isinstance(record["durationMs"], (int, float))


def test_generated_correlation_id_is_in_context_and_log(
    log_stream: StringIO,
) -> None:
    test_app = FastAPI()
    test_app.add_middleware(CorrelationIdMiddleware)

    @test_app.get("/context")
    def context() -> dict[str, str | None]:
        return {"correlationId": get_correlation_id()}

    with TestClient(test_app) as client:
        response = client.get("/context")

    correlation_id = response.headers["X-Correlation-Id"]
    UUID(correlation_id)
    assert response.json() == {"correlationId": correlation_id}
    assert _last_log(log_stream)["correlationId"] == correlation_id


def test_error_log_contains_correlation_id_without_authorization_secret(
    log_stream: StringIO,
) -> None:
    test_app = FastAPI()
    test_app.add_middleware(CorrelationIdMiddleware)

    @test_app.get("/boom")
    def boom() -> None:
        raise RuntimeError("internal failure")

    secret = "Bearer should-not-appear-in-logs"
    correlation_id = "error-correlation-id"
    with TestClient(test_app, raise_server_exceptions=False) as client:
        response = client.get(
            "/boom",
            headers={
                "Authorization": secret,
                "X-Correlation-Id": correlation_id,
            },
        )

    record = _last_log(log_stream)
    raw_logs = log_stream.getvalue()

    assert response.status_code == 500
    assert record["level"] == "ERROR"
    assert record["message"] == "request failed"
    assert record["correlationId"] == correlation_id
    assert record["statusCode"] == 500
    assert record["errorCode"] == "INTERNAL_SERVER_ERROR"
    assert record["errorType"] == "RuntimeError"
    assert secret not in raw_logs


def test_forward_headers_fall_back_to_context_correlation_id() -> None:
    tokens = set_log_context("context-correlation-id")
    try:
        headers = build_forward_headers(
            {
                "Authorization": "Bearer token",
                "X-Correlation-Id": "incoming-id",
            }
        )
    finally:
        reset_log_context(tokens)

    assert headers["Authorization"] == "Bearer token"
    assert headers["X-Correlation-Id"] == "context-correlation-id"
