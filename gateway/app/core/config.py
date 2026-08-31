"""Centralized settings for the PubTube API Gateway."""

from pydantic import Field
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

    jwt_secret: str = Field(default="", validation_alias="JWT_SECRET")
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias="JWT_ALGORITHM",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
