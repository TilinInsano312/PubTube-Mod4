"""Standard error responses for the dashboard HTTP contract."""

from starlette.responses import JSONResponse

from .dashboard_models import DashboardError


def dashboard_error(
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build a standard error while preserving protocol headers."""

    return JSONResponse(
        status_code=status_code,
        content=DashboardError(code=code, message=message).model_dump(),
        headers=headers,
    )
