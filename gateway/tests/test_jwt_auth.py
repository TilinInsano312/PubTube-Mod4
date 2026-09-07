from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.middleware.jwt_auth import JWTAuthenticationMiddleware


JWT_SECRET = "test-only-jwt-secret-for-suite-123456789"
JWT_ALGORITHM = "HS256"


@pytest.fixture(autouse=True)
def configured_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", JWT_SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", JWT_ALGORITHM)


@pytest.fixture
def protected_client() -> TestClient:
    test_app = FastAPI()
    test_app.add_middleware(JWTAuthenticationMiddleware)

    @test_app.get("/protected")
    def protected(request: Request) -> dict[str, str | None]:
        return {
            "sub": request.state.user["sub"],
            "user_id": request.state.user_id,
            "role": request.state.role,
        }

    return TestClient(test_app)


def create_token(**claims: object) -> str:
    payload = {
        "sub": "user-123",
        "role": "viewer",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        **claims,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def test_missing_authorization_header_returns_401(
    protected_client: TestClient,
) -> None:
    response = protected_client.get("/protected")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_authorization_without_bearer_scheme_returns_401(
    protected_client: TestClient,
) -> None:
    response = protected_client.get(
        "/protected",
        headers={"Authorization": "Basic credentials"},
    )

    assert response.status_code == 401


def test_invalid_jwt_returns_401(protected_client: TestClient) -> None:
    response = protected_client.get(
        "/protected",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401


def test_modified_jwt_signature_returns_401(protected_client: TestClient) -> None:
    token = create_token()
    modified_token = f"{token[:-1]}{'a' if token[-1] != 'a' else 'b'}"

    response = protected_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {modified_token}"},
    )

    assert response.status_code == 401


def test_expired_jwt_returns_401(protected_client: TestClient) -> None:
    token = create_token(
        exp=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    response = protected_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_valid_jwt_continues_and_exposes_claims(
    protected_client: TestClient,
) -> None:
    token = create_token(user_id="account-456")

    response = protected_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "sub": "user-123",
        "user_id": "account-456",
        "role": "viewer",
    }


def test_health_route_is_public() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_documentation_routes_are_public(path: str) -> None:
    response = TestClient(app).get(path)

    assert response.status_code == 200


def test_non_public_gateway_route_requires_jwt() -> None:
    response = TestClient(app).get("/api/not-registered")

    assert response.status_code == 401


def test_valid_jwt_reaches_gateway_router() -> None:
    token = create_token()

    response = TestClient(app).get(
        "/api/not-registered",
        headers={"Authorization": f"Bearer {token}"},
    )

    # The current Gateway has no module proxy registered, so a valid request
    # reaches FastAPI routing and receives its normal not-found response.
    assert response.status_code == 404
