"""JWT authentication middleware for protected Gateway routes."""

from typing import Any

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..core.config import settings


PUBLIC_PATHS = frozenset(
    {
        "/api/health",
        "/api/health/",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/openapi.json",
    }
)
UNAUTHORIZED_DETAIL = "Invalid authentication credentials"


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """Validate Bearer JWT credentials before handling protected requests."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Authenticate the request or return an HTTP 401 response."""

        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        token = _extract_bearer_token(request.headers.get("Authorization"))
        if token is None:
            return _unauthorized_response()

        claims = _decode_token(token)
        if claims is None:
            return _unauthorized_response()

        request.state.jwt_claims = claims
        request.state.user = claims
        request.state.user_id = claims.get("user_id", claims.get("sub"))
        request.state.role = claims.get("role")

        return await call_next(request)


def _extract_bearer_token(authorization: str | None) -> str | None:
    """Extract a token from a valid Bearer authorization header."""

    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]


def _decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT with the configured algorithm and secret."""

    if not settings.jwt_secret or not settings.jwt_algorithm:
        return None

    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={
                "require": ["exp"],
                "verify_signature": True,
                "verify_exp": True,
            },
        )
    except (jwt.PyJWTError, NotImplementedError, TypeError, ValueError):
        return None

    if not isinstance(claims, dict):
        return None

    return claims


def _unauthorized_response() -> JSONResponse:
    """Build the generic response used for all authentication failures."""

    return JSONResponse(
        status_code=401,
        content={"detail": UNAUTHORIZED_DETAIL},
        headers={"WWW-Authenticate": "Bearer"},
    )
