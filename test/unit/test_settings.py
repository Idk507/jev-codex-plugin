"""Tests for application configuration."""

import pytest
from pydantic import ValidationError

from jev_plugin.config import Settings


def test_settings_loads_required_typesafe_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings should load successfully when the API key is provided."""
    monkeypatch.setenv(
        "TYPESAFE_API_KEY",
        "test-api-key",
    )

    settings = Settings()

    assert settings.app_name == "jev-chatgpt-plugin"
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.typesafe_model == "jev-latest"
    assert settings.typesafe_api_key.get_secret_value() == "test-api-key"


def test_settings_rejects_missing_typesafe_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings should fail when the required API key is missing."""
    monkeypatch.delenv(
        "TYPESAFE_API_KEY",
        raising=False,
    )

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_loads_pre_tool_probability_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Codex pre-tool policy threshold should be configurable."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-api-key")
    monkeypatch.setenv("JEV_PRE_TOOL_MINIMUM_PROBABILITY", "0.82")

    settings = Settings()

    assert settings.jev_pre_tool_minimum_probability == 0.82

