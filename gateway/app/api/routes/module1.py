"""Gateway routes owned by PubTube Module 1."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from ...api.dependencies import get_upstream_service
from ...services.upstreams import UpstreamModule, UpstreamService
from .proxy import proxy_request, quote_nested_path, quote_path_segment


router = APIRouter(tags=["module1"])


@router.get("/content/health")
async def module1_health(
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward a Gateway smoke check to Module 1's health endpoint."""

    return await proxy_request(request, upstream_service, UpstreamModule.MODULE1, "/health")


@router.post("/content/init")
async def init_content_upload(
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward upload initialization to the Module 1 contract."""

    return await proxy_request(
        request,
        upstream_service,
        UpstreamModule.MODULE1,
        "/api/content/init",
    )


@router.get("/content/{session_id}/part/{part_number}")
async def get_content_upload_part(
    session_id: str,
    part_number: int,
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward a signed part URL request to Module 1."""

    path = f"/api/content/{quote_path_segment(session_id)}/part/{part_number}"
    return await proxy_request(request, upstream_service, UpstreamModule.MODULE1, path)


@router.get("/content/upload/{session_id}/status")
async def get_content_upload_status(
    session_id: str,
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward multipart upload status requests to Module 1."""

    path = f"/api/content/upload/{quote_path_segment(session_id)}/status"
    return await proxy_request(request, upstream_service, UpstreamModule.MODULE1, path)


@router.post("/content/upload/{session_id}/complete")
async def complete_content_upload(
    session_id: str,
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward multipart upload completion requests to Module 1."""

    path = f"/api/content/upload/{quote_path_segment(session_id)}/complete"
    return await proxy_request(request, upstream_service, UpstreamModule.MODULE1, path)


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
        "/api/content",
    )


@router.put("/content/{content_id}/metadata")
async def update_content_metadata(
    content_id: str,
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward metadata updates to Module 1."""

    path = f"/api/content/{quote_path_segment(content_id)}/metadata"
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
        "/api/content",
    )


@router.get("/content/{content_path:path}")
async def get_content(
    content_path: str,
    request: Request,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward content paths below the Module 1 collection."""

    path = "/api/content"
    if content_path:
        path = f"/api/content/{quote_nested_path(content_path)}"
    return await proxy_request(request, upstream_service, UpstreamModule.MODULE1, path)
