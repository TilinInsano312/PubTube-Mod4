"""Prometheus scrape endpoint for the Gateway."""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from ...observability.metrics import METRICS_REGISTRY


router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Return the current Prometheus exposition payload."""

    return Response(
        content=generate_latest(METRICS_REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
