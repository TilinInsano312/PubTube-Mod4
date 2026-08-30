from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_preserves_received_correlation_id() -> None:
    correlation_id = "request-correlation-id-123"

    response = client.get(
        "/api/health",
        headers={"X-Correlation-Id": correlation_id},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == correlation_id


def test_generates_correlation_id_when_missing() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    generated_correlation_id = response.headers.get("X-Correlation-Id")
    assert generated_correlation_id is not None
    UUID(generated_correlation_id)
