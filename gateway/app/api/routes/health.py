"""Technical health endpoint for the API Gateway."""

from fastapi import APIRouter


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return the basic health status of the Gateway."""

    return {"status": "ok", "service": "gateway"}
