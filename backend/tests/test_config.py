from __future__ import annotations

import pytest

from app.core.config import ConfigurationError, Settings, load_settings


def test_settings_load_required_values(test_environment: None) -> None:
    settings = load_settings()
    assert settings.environment == "test"
    assert settings.database_url.get_secret_value().endswith("/flowtracer_test")


def test_missing_configuration_fails_fast_without_secret(
    monkeypatch: pytest.MonkeyPatch,
    test_environment: None,
) -> None:
    secret = "must-not-appear"  # noqa: S105 - synthetic redaction sentinel
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.setenv("REDIS_URL", f"redis://:{secret}@localhost:6379/0")

    with pytest.raises(ConfigurationError) as error:
        load_settings()

    assert "DATABASE_URL" in str(error.value)
    assert secret not in str(error.value)


def test_invalid_secret_configuration_is_safely_reported(
    monkeypatch: pytest.MonkeyPatch,
    test_environment: None,
) -> None:
    secret = "postgresql://user:very-secret@localhost/db"  # noqa: S105 - synthetic sentinel
    monkeypatch.setenv("DATABASE_URL", secret)

    with pytest.raises(ConfigurationError) as error:
        load_settings()

    assert "DATABASE_URL" in str(error.value)
    assert "very-secret" not in str(error.value)


def test_test_database_name_is_explicit(test_environment: None) -> None:
    settings = Settings()
    assert "_test" in settings.database_url.get_secret_value().rsplit("/", maxsplit=1)[-1]


def test_missing_jwt_secret_fails_fast_without_value(
    monkeypatch: pytest.MonkeyPatch,
    test_environment: None,
) -> None:
    monkeypatch.delenv("JWT_SECRET")
    with pytest.raises(ConfigurationError) as error:
        load_settings()
    assert "JWT_SECRET" in str(error.value)
    assert "unit-test-jwt-secret" not in str(error.value)
