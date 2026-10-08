import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from dashboard_app.services.publication_dashboard import (
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
        return self.items


class FailingPublicationSource:
    async def list_publications(
        self,
        *,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> list[PublicationRecord]:
        raise RuntimeError("source unavailable")


@pytest.mark.parametrize("state", ["scheduled", "published", "failed"])
def test_single_state_preserves_details_and_leaves_other_buckets_empty(state: str) -> None:
    items = [record("first", state), record("second", state, 1)]
    result = asyncio.run(PublicationDashboardService(FakePublicationSource(items)).aggregate())

    for bucket_state in ("scheduled", "published", "failed"):
        bucket = getattr(result, bucket_state)
        expected_items = items if bucket_state == state else []
        assert bucket.count == len(expected_items)
        assert bucket.items == expected_items


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
    assert result.failed.count == 0
    assert result.failed.items == []
    assert source.bounds == (BASE_TIME, None)


def test_to_only_is_inclusive() -> None:
    source = FakePublicationSource([record("edge", "scheduled"), record("after", "failed", 1)])
    result = asyncio.run(PublicationDashboardService(source).aggregate(to_at=BASE_TIME))

    assert [item.id for item in result.scheduled.items] == ["edge"]
    assert result.failed.count == 0
    assert result.failed.items == []
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
    assert result.failed.count == 0
    assert result.failed.items == []
    assert source.bounds == (BASE_TIME, BASE_TIME + timedelta(days=1))


def test_range_with_no_matching_publications_returns_empty_buckets() -> None:
    source = FakePublicationSource(
        [record("before", "scheduled", -1), record("after", "published", 1)]
    )
    result = asyncio.run(
        PublicationDashboardService(source).aggregate(from_at=BASE_TIME, to_at=BASE_TIME)
    )

    assert result.scheduled.count == result.published.count == result.failed.count == 0
    assert result.scheduled.items == result.published.items == result.failed.items == []
    assert source.bounds == (BASE_TIME, BASE_TIME)


def test_offset_bounds_compare_absolute_instants() -> None:
    source = FakePublicationSource(
        [record("before", "failed", -1), record("edge", "scheduled"), record("after", "failed", 1)]
    )
    from_at = BASE_TIME.astimezone(timezone(timedelta(hours=-3)))
    to_at = BASE_TIME.astimezone(timezone(timedelta(hours=5, minutes=30)))
    result = asyncio.run(
        PublicationDashboardService(source).aggregate(from_at=from_at, to_at=to_at)
    )

    assert result.scheduled.count == 1
    assert [item.id for item in result.scheduled.items] == ["edge"]
    assert result.published.count == result.failed.count == 0
    assert result.published.items == result.failed.items == []
    assert source.bounds == (from_at, to_at)


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


@pytest.mark.parametrize(
    ("bound", "field_name"),
    [("from_at", "from_at"), ("to_at", "to_at")],
)
def test_naive_bounds_are_rejected_before_source_call(
    bound: str,
    field_name: str,
) -> None:
    source = FakePublicationSource([])
    value = datetime(2026, 9, 1)

    with pytest.raises(ValueError, match=f"{field_name} must be timezone-aware"):
        asyncio.run(
            PublicationDashboardService(source).aggregate(**{bound: value})
        )

    assert source.bounds is None


def test_naive_schedule_at_is_rejected_before_comparison() -> None:
    naive_record = PublicationRecord(
        id="naive",
        content_id="content-naive",
        state="scheduled",
        schedule_at=datetime(2026, 9, 1),
        timezone="UTC",
    )

    class NaivePublicationSource:
        async def list_publications(
            self,
            *,
            from_at: datetime | None = None,
            to_at: datetime | None = None,
        ) -> list[PublicationRecord]:
            return [naive_record]

    service = PublicationDashboardService(NaivePublicationSource())

    with pytest.raises(
        ValueError,
        match="PublicationRecord.schedule_at must be timezone-aware",
    ):
        asyncio.run(service.aggregate(from_at=BASE_TIME))


def test_unknown_state_fails_fast() -> None:
    service = PublicationDashboardService(FakePublicationSource([record("x", "pending")]))

    with pytest.raises(UnsupportedPublicationState, match="pending"):
        asyncio.run(service.aggregate())


def test_source_error_is_propagated() -> None:
    service = PublicationDashboardService(FailingPublicationSource())

    with pytest.raises(RuntimeError, match="source unavailable"):
        asyncio.run(service.aggregate())


def test_aggregation_module_has_no_fastapi_dependency() -> None:
    import dashboard_app.services.publication_dashboard as dashboard

    assert "fastapi" not in dashboard.__dict__
