"""Gateway routes owned by PubTube Module 1."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from ...api.dependencies import get_upstream_service
from ...services.upstreams import UpstreamModule, UpstreamService
from .proxy import proxy_request, quote_nested_path, quote_path_segment


router = APIRouter(tags=["module1"])


@router.post("/content")
async def create_content(
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward content creation to Module 1."""

    return await proxy_request(
        request,
        upstream_service,
        UpstreamModule.MODULE1,
        "/content",
    )


@router.put("/content/{content_id}/metadata")
async def update_content_metadata(
    content_id: str,
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward metadata updates to Module 1."""

    path = f"/content/{quote_path_segment(content_id)}/metadata"
    return await proxy_request(request, upstream_service, UpstreamModule.MODULE1, path)


@router.get("/content")
async def list_content(
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward the Module 1 content collection query."""

    return await proxy_request(
        request,
        upstream_service,
        UpstreamModule.MODULE1,
        "/content",
    )


@router.get("/content/{content_path:path}")
async def get_content(
    content_path: str,
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward content paths below the Module 1 collection."""

    path = "/content"
    if content_path:
        path = f"/content/{quote_nested_path(content_path)}"
    return await proxy_request(request, upstream_service, UpstreamModule.MODULE1, path)
