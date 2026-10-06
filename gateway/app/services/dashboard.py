"""Integration boundary for the publication dashboard aggregator."""

from datetime import datetime
from typing import Protocol

import httpx

from ..api.dashboard_models import DashboardCounts
from .publication_dashboard import PublicationDashboardService


class DashboardAggregator(Protocol):
    """Aggregate publication counts within optional inclusive UTC bounds."""

    async def aggregate(
        self, *, from_: datetime | None, to: datetime | None
    ) -> DashboardCounts:
        """Return scheduled, published and failed counts for the range."""
        ...


class PublicationDashboardAdapter:
    """Expose domain aggregation through the Gateway's count contract."""

    def __init__(self, service: PublicationDashboardService) -> None:
        self._service = service

    async def aggregate(
        self, *, from_: datetime | None, to: datetime | None
    ) -> DashboardCounts:
        """Translate filter names and return counts from the real aggregator."""

        try:
            result = await self._service.aggregate(from_at=from_, to_at=to)
        except httpx.TimeoutException as error:
            raise TimeoutError("Publication source timed out") from error
        return DashboardCounts(
            scheduled=result.scheduled.count,
            published=result.published.count,
            failed=result.failed.count,
        )
