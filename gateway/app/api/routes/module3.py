"""Gateway routes owned by PubTube Module 3."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from ...api.dependencies import get_upstream_service
from ...services.upstreams import UpstreamModule, UpstreamService
from .proxy import proxy_request, quote_path_segment


router = APIRouter(tags=["module3"])


@router.post("/publish/schedule")
async def schedule_publication(
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward publication scheduling to Module 3."""

    return await proxy_request(
        request,
        upstream_service,
        UpstreamModule.MODULE3,
        "/publish/schedule",
    )


@router.post("/publish/{publication_id}/now")
async def publish_now(
    publication_id: str,
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward an immediate publication request to Module 3."""

    path = f"/publish/{quote_path_segment(publication_id)}/now"
    return await proxy_request(request, upstream_service, UpstreamModule.MODULE3, path)


@router.get("/publish/{publication_id}/status")
async def publication_status(
    publication_id: str,
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward a publication status query to Module 3."""

    path = f"/publish/{quote_path_segment(publication_id)}/status"
    return await proxy_request(request, upstream_service, UpstreamModule.MODULE3, path)
