"""Application configuration for the JEV Codex tool gate.

This module centralizes runtime configuration and prevents environment
variables from being accessed directly throughout the application.

Configuration is loaded using Pydantic Settings, which gives us:

- Environment-variable based configuration.
- Type validation.
- Sensible defaults for non-secret values.
- A single configuration object shared by the application.
- A clean boundary between configuration and business logic.

Secrets such as the TypeSafe API key are never hard-coded.
"""

from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
    """Application runtime configuration.

    Attributes:
        app_name: Logical name of the application.
        app_env: Runtime environment such as development or production.
        log_level: Application logging level.
        typesafe_api_key: API credential used to authenticate with TypeSafe.
        typesafe_model: Jev model used for System One requests.
        jev_pre_tool_minimum_probability: Allow threshold for Codex tools.
    """

    app_name: str = Field(
        default="jev-chatgpt-plugin",
        description="Application name.",
    )

    app_env: str = Field(
        default="development",
        description="Application runtime environment.",
    )

    log_level: str = Field(
        default="INFO",
        description="Application logging level.",
    )

    typesafe_api_key: SecretStr = Field(
        description="TypeSafe API key.",
    )

    typesafe_model: str = Field(
        default="jev-latest",
        description="TypeSafe Jev model to use.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    jev_pre_tool_minimum_probability: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        validation_alias="JEV_PRE_TOOL_MINIMUM_PROBABILITY",
        description="Minimum JEV yes probability required to allow a Codex tool call.",
    )



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the application settings singleton.

    The settings object is cached so that the environment is parsed once
    during the lifetime of the application process.

    Returns:
        A validated Settings instance.

    Raises:
        pydantic.ValidationError:
            If a required configuration value is missing or invalid.
    """
    return Settings()
