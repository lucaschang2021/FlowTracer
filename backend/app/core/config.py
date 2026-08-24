from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    """A safe startup error that names invalid variables without exposing values."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, env_file=None, extra="ignore")

    environment: Literal["development", "test"] = Field(alias="FLOWTRACER_ENV")
    log_level: str = Field(alias="FLOWTRACER_LOG_LEVEL")
    app_version: str = Field(alias="FLOWTRACER_APP_VERSION")
    api_host: str = Field(alias="FLOWTRACER_API_HOST")
    api_port: int = Field(alias="FLOWTRACER_API_PORT", ge=1, le=65535)
    database_url: SecretStr = Field(alias="DATABASE_URL")
    redis_url: SecretStr = Field(alias="REDIS_URL")
    celery_broker_url: SecretStr = Field(alias="CELERY_BROKER_URL")
    celery_result_backend: SecretStr = Field(alias="CELERY_RESULT_BACKEND")
    jwt_secret: SecretStr = Field(alias="JWT_SECRET")
    access_token_ttl_minutes: int = Field(15, alias="ACCESS_TOKEN_TTL_MINUTES", ge=1)
    refresh_token_ttl_days: int = Field(30, alias="REFRESH_TOKEN_TTL_DAYS", ge=1)
    jwt_issuer: str = Field("flowtracer-api", alias="JWT_ISSUER", min_length=1)
    jwt_audience: str = Field("flowtracer-desktop", alias="JWT_AUDIENCE", min_length=1)
    dependency_timeout_seconds: float = 2.0

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("must be a standard log level")
        return normalized

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("must use postgresql+asyncpg")
        return value

    @field_validator("redis_url", "celery_broker_url", "celery_result_backend")
    @classmethod
    def validate_redis_url(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(("redis://", "rediss://")):
            raise ValueError("must use redis or rediss")
        return value

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("must contain at least 32 bytes")
        return value


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        variables = sorted({str(error["loc"][0]) for error in exc.errors()})
        raise ConfigurationError(
            f"Invalid or missing configuration variables: {', '.join(variables)}"
        ) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
