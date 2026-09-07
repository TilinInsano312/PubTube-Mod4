"""Centralized settings for the PubTube API Gateway."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or ``.env``."""

    app_name: str = Field(
        default="PubTube API Gateway",
        validation_alias="GATEWAY_APP_NAME",
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
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias="JWT_ALGORITHM",
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
