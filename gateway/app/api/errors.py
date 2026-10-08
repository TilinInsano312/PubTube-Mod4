"""Standard error envelopes for public HTTP contracts."""

from starlette.responses import JSONResponse

def standard_error(
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build a standard error while preserving protocol headers."""

    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "code": code, "message": message},
        headers=headers,
    )
