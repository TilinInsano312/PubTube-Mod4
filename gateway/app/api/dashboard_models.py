"""Request and response contracts for the publication dashboard."""

import re
from datetime import date, datetime, time, timezone
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator


class DashboardQuery(BaseModel):
    """Optional inclusive UTC bounds for the dashboard aggregation."""

    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None

    @field_validator("from_", "to", mode="before")
    @classmethod
    def parse_bound(cls, value: str | None, info: ValidationInfo) -> datetime | None:
        """Parse ISO dates or timestamps with an explicit timezone."""

        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Use an ISO date or a timestamp with a timezone")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            boundary = time.max if info.field_name == "to" else time.min
            return datetime.combine(date.fromisoformat(value), boundary, timezone.utc)
        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?"
            r"(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)",
            value,
        ):
            raise ValueError("Use YYYY-MM-DD or an ISO timestamp with a timezone")
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )

    @model_validator(mode="after")
    def validate_range(self) -> "DashboardQuery":
        """Reject ranges whose start is later than their end."""

        if self.from_ is not None and self.to is not None and self.from_ > self.to:
            raise ValueError("from must be earlier than or equal to to")
        return self


class DashboardCounts(BaseModel):
    """Counts supplied by the publication aggregation service."""

    scheduled: int = Field(ge=0, strict=True)
    published: int = Field(ge=0, strict=True)
    failed: int = Field(ge=0, strict=True)


class DashboardResponse(BaseModel):
    """Standard successful dashboard response."""

    status: Literal["ok"] = "ok"
    data: DashboardCounts


class DashboardError(BaseModel):
    """Standard error response without internal exception details."""

    status: Literal["error"] = "error"
    code: str
    message: str
