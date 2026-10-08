"""Environment settings for the standalone dashboard service."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configure the dashboard without importing the Gateway."""

    dashboard_port: int = Field(default=8004, ge=1, le=65535, validation_alias="DASHBOARD_PORT")
    environment: str = Field(default="local", validation_alias="DASHBOARD_ENVIRONMENT")
    otel_service_name: str = Field(default="module4-dashboard", validation_alias="OTEL_SERVICE_NAME")
    otel_traces_exporter: Literal["none", "otlp"] = Field(
        default="none", validation_alias="OTEL_TRACES_EXPORTER"
    )
    otel_endpoint: str = Field(
        default="http://localhost:4318/v1/traces",
        validation_alias="OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    )
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8", extra="ignore",
    )


settings = Settings()
