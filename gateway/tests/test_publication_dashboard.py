import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.services.publication_dashboard import (
    PublicationDashboardService,
    PublicationRecord,
    UnsupportedPublicationState,
)


BASE_TIME = datetime(2026, 9, 1, tzinfo=timezone.utc)


def record(publication_id: str, state: str, offset: int = 0) -> PublicationRecord:
    return PublicationRecord(
        id=publication_id,
        content_id=f"content-{publication_id}",
        state=state,
        schedule_at=BASE_TIME + timedelta(days=offset),
        timezone="UTC",
        youtube_video_id=f"video-{publication_id}" if state == "published" else None,
        attempts=2,
        last_error="upload failed" if state == "failed" else None,
    )


class FakePublicationSource:
    def __init__(self, items: list[PublicationRecord]) -> None:
        self.items = items
        self.bounds: tuple[datetime | None, datetime | None] | None = None

    async def list_publications(
        self,
        *,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> list[PublicationRecord]:
        self.bounds = (from_at, to_at)
        return [
            item
            for item in self.items
            if (from_at is None or item.schedule_at >= from_at)
            and (to_at is None or item.schedule_at <= to_at)
        ]


class FailingPublicationSource:
    async def list_publications(
        self,
        *,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> list[PublicationRecord]:
        raise RuntimeError("source unavailable")


def test_aggregates_status_counts_and_preserves_details() -> None:
    items = [
        record("s1", "scheduled"),
        record("s2", "scheduled", 1),
        record("p1", "published"),
        record("f1", "failed"),
    ]
    result = asyncio.run(PublicationDashboardService(FakePublicationSource(items)).aggregate())

    assert (result.scheduled.count, result.published.count, result.failed.count) == (
        2,
        1,
        1,
    )
    assert result.scheduled.items == items[:2]
    assert result.published.items == [items[2]]
    assert result.failed.items == [items[3]]
    assert result.published.items[0].youtube_video_id == "video-p1"
    assert result.failed.items[0].last_error == "upload failed"


def test_empty_source_returns_all_empty_buckets() -> None:
    result = asyncio.run(PublicationDashboardService(FakePublicationSource([])).aggregate())

    assert result.scheduled.count == result.published.count == result.failed.count == 0
    assert result.scheduled.items == result.published.items == result.failed.items == []


def test_from_only_is_inclusive() -> None:
    source = FakePublicationSource([record("before", "failed", -1), record("edge", "scheduled")])
    result = asyncio.run(PublicationDashboardService(source).aggregate(from_at=BASE_TIME))

    assert [item.id for item in result.scheduled.items] == ["edge"]
    assert source.bounds == (BASE_TIME, None)


def test_to_only_is_inclusive() -> None:
    source = FakePublicationSource([record("edge", "scheduled"), record("after", "failed", 1)])
    result = asyncio.run(PublicationDashboardService(source).aggregate(to_at=BASE_TIME))

    assert [item.id for item in result.scheduled.items] == ["edge"]
    assert source.bounds == (None, BASE_TIME)


def test_from_and_to_are_inclusive() -> None:
    source = FakePublicationSource(
        [record("before", "failed", -1), record("from", "scheduled"), record("to", "published", 1), record("after", "failed", 2)]
    )
    result = asyncio.run(
        PublicationDashboardService(source).aggregate(
            from_at=BASE_TIME,
            to_at=BASE_TIME + timedelta(days=1),
        )
    )

    assert [item.id for item in result.scheduled.items] == ["from"]
    assert [item.id for item in result.published.items] == ["to"]


def test_invalid_range_is_rejected_before_source_call() -> None:
    source = FakePublicationSource([])

    with pytest.raises(ValueError, match="from_at"):
        asyncio.run(
            PublicationDashboardService(source).aggregate(
                from_at=BASE_TIME + timedelta(days=1),
                to_at=BASE_TIME,
            )
        )

    assert source.bounds is None


def test_unknown_state_fails_fast() -> None:
    service = PublicationDashboardService(FakePublicationSource([record("x", "pending")]))

    with pytest.raises(UnsupportedPublicationState, match="pending"):
        asyncio.run(service.aggregate())


def test_source_error_is_propagated() -> None:
    service = PublicationDashboardService(FailingPublicationSource())

    with pytest.raises(RuntimeError, match="source unavailable"):
        asyncio.run(service.aggregate())


def test_aggregation_module_has_no_fastapi_dependency() -> None:
    import app.services.publication_dashboard as dashboard

    assert "fastapi" not in dashboard.__dict__
