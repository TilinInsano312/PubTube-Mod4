"""Demo endpoint used to exercise the Gateway JWT authentication flow."""

from typing import Any

from fastapi import APIRouter, Request


router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/protected")
def protected_demo(request: Request) -> dict[str, Any]:
    """Return the identity propagated by the JWT authentication middleware."""

    return {
        "authenticated": True,
        "message": "JWT válido; el middleware autenticó la solicitud",
        "user_id": request.state.user_id,
        "role": request.state.role,
        "claims": request.state.jwt_claims,
    }
