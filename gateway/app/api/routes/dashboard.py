"""Public forwarding route for the independently deployed dashboard API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from ..dependencies import get_upstream_service
from ..errors import standard_error
from ...clients.errors import UpstreamError, UpstreamTimeoutError
from ...services.upstreams import UpstreamModule, UpstreamService
from .proxy import _response_from_upstream

router = APIRouter(tags=["dashboard"])

# HTTP boundary documentation only. Validation and aggregation belong to dashboard-api.
ERROR_SCHEMA = {
    "type": "object", "required": ["status", "code", "message"],
    "properties": {
        "status": {"type": "string", "enum": ["error"]},
        "code": {"type": "string"}, "message": {"type": "string"},
    },
}
COUNT_SCHEMA = {
    "type": "object", "required": ["scheduled", "published", "failed"],
    "properties": {name: {"type": "integer", "minimum": 0} for name in ("scheduled", "published", "failed")},
}


@router.get(
    "/dashboard",
    summary="Get aggregated publication states",
    description="Public endpoint, without JWT. Inclusive from/to filters are validated by dashboard-api.",
    responses={
        200: {"content": {"application/json": {"schema": {
            "type": "object", "required": ["status", "data"],
            "properties": {"status": {"type": "string", "enum": ["ok"]}, "data": COUNT_SCHEMA},
        }}}},
        **{code: {"description": description, "content": {"application/json": {"schema": ERROR_SCHEMA}}}
           for code, description in {
               422: "Invalid date or range", 429: "Rate limit exceeded",
               500: "Aggregation failed", 503: "Dashboard or publication source unavailable",
               504: "Dashboard or publication source timed out",
           }.items()},
    },
)
async def get_dashboard(
    request: Request,
    from_: Annotated[str | None, Query(alias="from", description="Inclusive start date or timestamp")] = None,
    to: Annotated[str | None, Query(description="Inclusive end date or timestamp")] = None,
    upstream_service: UpstreamService = Depends(get_upstream_service),
) -> Response:
    """Forward filters and headers without importing dashboard business code."""
    try:
        response = await upstream_service.client_for(UpstreamModule.DASHBOARD).request(
            method="GET", path="/api/dashboard",
            headers=request.headers, params=list(request.query_params.multi_items()),
            correlation_id=getattr(request.state, "correlation_id", None),
            raise_for_status=False,
        )
    except UpstreamTimeoutError:
        return standard_error(504, "DASHBOARD_TIMEOUT", "Dashboard request timed out")
    except (UpstreamError, ValueError):
        return standard_error(503, "DASHBOARD_UNAVAILABLE", "Dashboard service is not available")
    return _response_from_upstream(response)
