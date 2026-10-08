"""Standard errors for the dashboard HTTP contract."""

from starlette.responses import JSONResponse

from .dashboard_models import DashboardError


def dashboard_error(status_code: int, code: str, message: str) -> JSONResponse:
    """Build a safe error response without internal exception details."""
    return JSONResponse(
        status_code=status_code,
        content=DashboardError(code=code, message=message).model_dump(),
    )
