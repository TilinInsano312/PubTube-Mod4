"""FastAPI dependencies for the Gateway/BFF layer."""

from fastapi import Request

from ..services.upstreams import UpstreamService


def get_upstream_service(request: Request) -> UpstreamService:
    """Return the upstream service initialized by the application lifespan."""

    return request.app.state.upstream_service
