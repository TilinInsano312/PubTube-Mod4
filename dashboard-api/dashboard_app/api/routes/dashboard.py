"""Public dashboard endpoint and temporal filter validation."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import ValidationError
from starlette.responses import JSONResponse

from ..dashboard_models import DashboardCounts, DashboardError, DashboardQuery, DashboardResponse
from ..errors import dashboard_error
from ...services.dashboard import DashboardAggregator, PublicationDashboardAdapter
from ...services.publication_dashboard import PublicationDashboardService


router = APIRouter(tags=["dashboard"])


def get_dashboard_aggregator(request: Request) -> DashboardAggregator | None:
    """Return the aggregator registered by the application integration."""

    aggregator = getattr(request.app.state, "dashboard_aggregator", None)
    if isinstance(aggregator, PublicationDashboardService):
        return PublicationDashboardAdapter(aggregator)
    return aggregator


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get aggregated publication states",
    description=(
        "Returns scheduled, published and failed counts. Filters are optional and "
        "inclusive. Use YYYY-MM-DD (whole UTC days) or ISO timestamps with a timezone. "
        "This endpoint does not require JWT authentication."
    ),
    responses={
        422: {"model": DashboardError, "description": "Invalid date or reversed range"},
        500: {"model": DashboardError, "description": "Aggregation failed"},
        503: {"model": DashboardError, "description": "Aggregator unavailable"},
        504: {"model": DashboardError, "description": "Aggregation timed out"},
    },
)
async def get_dashboard(
    from_: Annotated[
        str | None,
        Query(alias="from", description="Inclusive start: YYYY-MM-DD or timestamp with timezone"),
    ] = None,
    to: Annotated[
        str | None,
        Query(description="Inclusive end: YYYY-MM-DD or timestamp with timezone"),
    ] = None,
    aggregator: DashboardAggregator | None = Depends(get_dashboard_aggregator),
) -> DashboardResponse | JSONResponse:
    """Validate the temporal range and request aggregated publication counts."""

    try:
        filters = DashboardQuery.model_validate({"from": from_, "to": to})
    except (ValidationError, OverflowError):
        return dashboard_error(
            422,
            "INVALID_DATE_RANGE",
            "Use valid ISO dates or timestamps with timezone, with from <= to",
        )

    if aggregator is None:
        return dashboard_error(
            503, "DASHBOARD_UNAVAILABLE", "Dashboard aggregation is not available"
        )

    try:
        counts = await aggregator.aggregate(from_=filters.from_, to=filters.to)
        return DashboardResponse(data=DashboardCounts.model_validate(counts))
    except TimeoutError:
        return dashboard_error(
            504, "DASHBOARD_TIMEOUT", "Dashboard aggregation timed out"
        )
    except Exception:
        return dashboard_error(
            500, "DASHBOARD_ERROR", "Dashboard aggregation failed"
        )
