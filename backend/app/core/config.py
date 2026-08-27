from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
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
    ai_provider: Literal["fake", "openai_compatible"] = Field(alias="AI_PROVIDER")
    ai_model: str = Field(alias="AI_MODEL", min_length=1, max_length=160)
    ai_base_url: str | None = Field(None, alias="AI_BASE_URL")
    ai_api_key: SecretStr | None = Field(None, alias="AI_API_KEY")
    ai_input_cost_per_million: Decimal = Field(alias="AI_INPUT_COST_PER_MILLION", ge=0)
    ai_output_cost_per_million: Decimal = Field(alias="AI_OUTPUT_COST_PER_MILLION", ge=0)
    dependency_timeout_seconds: float = 2.0

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("must be a standard log level")
        return normalized

    @field_validator("ai_model")
    @classmethod
    def validate_ai_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("ai_input_cost_per_million", "ai_output_cost_per_million")
    @classmethod
    def validate_ai_rate(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("must be finite")
        return value

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

    @model_validator(mode="after")
    def validate_ai_provider(self) -> Settings:
        if self.ai_provider == "openai_compatible":
            missing: list[str] = []
            if not self.ai_base_url:
                missing.append("AI_BASE_URL")
            if self.ai_api_key is None or not self.ai_api_key.get_secret_value():
                missing.append("AI_API_KEY")
            if missing:
                raise ValueError(f"missing required variables: {', '.join(missing)}")
            base_url = self.ai_base_url or ""
            parsed = urlsplit(base_url)
            loopback_test = self.environment == "test" and parsed.hostname in {
                "127.0.0.1",
                "::1",
                "localhost",
            }
            if (
                parsed.scheme not in ({"https", "http"} if loopback_test else {"https"})
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("AI_BASE_URL must be a safe HTTPS URL")
            try:
                _port = parsed.port
            except ValueError:
                raise ValueError("AI_BASE_URL contains an invalid port") from None
        return self


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        variables: set[str] = set()
        for error in exc.errors():
            location = error["loc"]
            if location:
                variables.add(str(location[0]))
                continue
            message = str(error["msg"])
            for name in ("AI_BASE_URL", "AI_API_KEY"):
                if name in message:
                    variables.add(name)
        if not variables:
            variables.add("configuration")
        raise ConfigurationError(
            f"Invalid or missing configuration variables: {', '.join(sorted(variables))}"
        ) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
