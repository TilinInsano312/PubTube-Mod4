"""Gateway routes owned by PubTube Module 2."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from ...api.dependencies import get_upstream_service
from ...services.upstreams import UpstreamModule, UpstreamService
from .proxy import proxy_request, quote_path_segment


router = APIRouter(tags=["module2"])


@router.get("/events/{correlation_id}")
async def get_events(
    correlation_id: str,
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward a correlation ID event query to Module 2."""

    path = f"/events/{quote_path_segment(correlation_id)}"
    return await proxy_request(request, upstream_service, UpstreamModule.MODULE2, path)
