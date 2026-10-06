"""Integration boundary for the publication dashboard aggregator."""

from datetime import datetime
from typing import Protocol

from ..api.dashboard_models import DashboardCounts


class DashboardAggregator(Protocol):
    """Aggregate publication counts within optional inclusive UTC bounds."""

    async def aggregate(
        self, *, from_: datetime | None, to: datetime | None
    ) -> DashboardCounts:
        """Return scheduled, published and failed counts for the range."""
        ...
