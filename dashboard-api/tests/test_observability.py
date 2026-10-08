"""Verify standalone health, bounded metric labels and W3C trace propagation."""

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from dashboard_app import main


def test_standalone_health_metrics_and_unavailable_source():
    with TestClient(main.create_app()) as client:
        assert client.get("/api/health").json() == {"status": "ok", "service": "dashboard-api"}
        response = client.get("/api/dashboard", headers={"X-Correlation-Id": "no-source"})
        assert response.status_code == 503
        assert response.json()["code"] == "DASHBOARD_UNAVAILABLE"
        assert response.headers["X-Correlation-Id"] == "no-source"
        client.get("/unknown-private-id")
        metrics = client.get("/metrics").text
    assert 'pubtube_dashboard_requests_total{method="GET",route="/api/dashboard",status="503"} 1.0' in metrics
    assert 'route="unmatched"' in metrics
    assert "unknown-private-id" not in metrics


def test_dashboard_span_uses_incoming_trace_parent(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(main, "configure_tracing", lambda config: provider)
    with TestClient(main.create_app()) as client:
        response = client.get("/api/health", headers={
            "X-Correlation-Id": "trace-smoke",
            "traceparent": "00-12345678901234567890123456789012-1234567890123456-01",
        })
        assert response.status_code == 200
        span = exporter.get_finished_spans()[0]
        assert span.name == "dashboard.request"
        assert span.context.trace_id == int("12345678901234567890123456789012", 16)
        assert span.parent.span_id == int("1234567890123456", 16)
        assert span.attributes["correlation_id"] == "trace-smoke"
        assert span.attributes["http.route"] == "/api/health"
