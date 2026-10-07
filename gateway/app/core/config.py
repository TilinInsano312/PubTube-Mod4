"""Centralized settings for the PubTube API Gateway."""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or ``.env``."""

    app_name: str = Field(
        default="PubTube API Gateway",
        validation_alias="GATEWAY_APP_NAME",
    )
    environment: str = Field(
        default="local",
        validation_alias="GATEWAY_ENVIRONMENT",
    )
    app_version: str = Field(
        default="0.1.0",
        validation_alias="GATEWAY_APP_VERSION",
    )
    gateway_port: int = Field(default=8000, validation_alias="GATEWAY_PORT")

    module1_url: str = Field(
        default="http://localhost:8001",
        validation_alias="MODULE1_URL",
    )
    module2_url: str = Field(
        default="http://localhost:8002",
        validation_alias="MODULE2_URL",
    )
    module3_url: str = Field(
        default="http://localhost:8003",
        validation_alias="MODULE3_URL",
    )

    upstream_connect_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        validation_alias="UPSTREAM_CONNECT_TIMEOUT_SECONDS",
    )
    upstream_read_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        validation_alias="UPSTREAM_READ_TIMEOUT_SECONDS",
    )
    upstream_write_timeout_seconds: float = Field(
        default=300.0,
        gt=0,
        validation_alias="UPSTREAM_WRITE_TIMEOUT_SECONDS",
    )
    upstream_pool_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        validation_alias="UPSTREAM_POOL_TIMEOUT_SECONDS",
    )

    jwt_secret: str = Field(default="", validation_alias="JWT_SECRET")
    jwt_secret_file: str = Field(default="", validation_alias="JWT_SECRET_FILE")
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias="JWT_ALGORITHM",
    )
    public_test_routes: bool = Field(
        default=False,
        validation_alias="GATEWAY_PUBLIC_TEST_ROUTES",
    )

    rate_limit_requests: int = Field(
        default=60,
        ge=1,
        validation_alias=AliasChoices(
            "RATE_LIMIT_REQUESTS",
            "RATE_LIMIT_MAX_REQUESTS",
        ),
    )
    rate_limit_window_seconds: float = Field(
        default=60.0,
        gt=0,
        validation_alias="RATE_LIMIT_WINDOW_SECONDS",
    )
    trusted_proxy_ips: str = Field(
        default="",
        validation_alias="TRUSTED_PROXY_IPS",
    )

    otel_service_name: str = Field(
        default="module4-gateway",
        validation_alias="OTEL_SERVICE_NAME",
    )
    otel_traces_exporter: str = Field(
        default="none",
        validation_alias="OTEL_TRACES_EXPORTER",
    )
    otel_exporter_otlp_traces_endpoint: str = Field(
        default="",
        validation_alias="OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    )
    otel_traces_sampler: str = Field(
        default="always_on",
        validation_alias="OTEL_TRACES_SAMPLER",
    )
    otel_traces_sampler_arg: str = Field(
        default="",
        validation_alias="OTEL_TRACES_SAMPLER_ARG",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def load_jwt_secret_file(self) -> "Settings":
        if self.jwt_secret_file:
            self.jwt_secret = Path(self.jwt_secret_file).read_text(encoding="utf-8").strip()
            if not self.jwt_secret:
                raise ValueError("JWT_SECRET_FILE is empty")
        return self


settings = Settings()
