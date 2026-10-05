"""Domain aggregation for publication dashboard data."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class PublicationRecord:
    """Confirmed publication fields needed by the dashboard."""

    id: str
    content_id: str
    state: str
    schedule_at: datetime
    timezone: str
    youtube_video_id: str | None = None
    attempts: int = 0
    last_error: str | None = None


class PublicationSource(Protocol):
    """Async boundary that supplies publication records to the aggregator."""

    async def list_publications(
        self,
        *,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> list[PublicationRecord]:
        """List records within inclusive schedule timestamp bounds."""


class UnsupportedPublicationState(ValueError):
    """Raised when a source returns a state outside the dashboard contract."""


@dataclass(frozen=True)
class PublicationStatusBucket:
    """A dashboard category and its matching publication details."""

    count: int
    items: list[PublicationRecord]


@dataclass(frozen=True)
class PublicationDashboardAggregation:
    """Stable aggregate containing all dashboard publication categories."""

    scheduled: PublicationStatusBucket
    published: PublicationStatusBucket
    failed: PublicationStatusBucket


class PublicationDashboardService:
    """Aggregate publication records without depending on an HTTP framework."""

    def __init__(self, source: PublicationSource) -> None:
        self._source = source

    async def aggregate(
        self,
        *,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> PublicationDashboardAggregation:
        """Fetch and group records, preserving source failures and details.

        Args:
            from_at: Inclusive lower bound for ``schedule_at``.
            to_at: Inclusive upper bound for ``schedule_at``.

        Returns:
            A stable aggregation with scheduled, published, and failed buckets.

        Raises:
            ValueError: If the lower bound is after the upper bound.
            UnsupportedPublicationState: If a record has an unknown state.
        """
        if from_at is not None and to_at is not None and from_at > to_at:
            raise ValueError("from_at must be less than or equal to to_at")

        records = await self._source.list_publications(
            from_at=from_at,
            to_at=to_at,
        )
        buckets: dict[str, list[PublicationRecord]] = {
            "scheduled": [],
            "published": [],
            "failed": [],
        }
        for record in records:
            if from_at is not None and record.schedule_at < from_at:
                continue
            if to_at is not None and record.schedule_at > to_at:
                continue
            try:
                buckets[record.state].append(record)
            except KeyError as error:
                raise UnsupportedPublicationState(
                    f"Unsupported publication state: {record.state}"
                ) from error

        return PublicationDashboardAggregation(
            scheduled=_bucket(buckets["scheduled"]),
            published=_bucket(buckets["published"]),
            failed=_bucket(buckets["failed"]),
        )


def _bucket(items: list[PublicationRecord]) -> PublicationStatusBucket:
    """Create a bucket whose count always matches its details."""
    return PublicationStatusBucket(count=len(items), items=items)
