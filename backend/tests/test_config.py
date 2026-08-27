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


def test_multiple_missing_variables_are_comma_separated_and_value_free(
    monkeypatch: pytest.MonkeyPatch,
    test_environment: None,
) -> None:
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.delenv("JWT_SECRET")
    with pytest.raises(ConfigurationError) as error:
        load_settings()
    assert str(error.value) == (
        "Invalid or missing configuration variables: DATABASE_URL, JWT_SECRET"
    )


def test_openai_conditional_configuration_names_missing_variables_safely(
    monkeypatch: pytest.MonkeyPatch,
    test_environment: None,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    with pytest.raises(ConfigurationError) as error:
        load_settings()
    assert str(error.value) == (
        "Invalid or missing configuration variables: AI_API_KEY, AI_BASE_URL"
    )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_ai_rates_must_be_finite(
    monkeypatch: pytest.MonkeyPatch, test_environment: None, value: str
) -> None:
    monkeypatch.setenv("AI_INPUT_COST_PER_MILLION", value)
    with pytest.raises(ConfigurationError) as error:
        load_settings()
    assert "AI_INPUT_COST_PER_MILLION" in str(error.value)
    assert value not in str(error.value)
