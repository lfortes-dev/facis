"""Configuration management for FACIS AI Insight Service."""

import logging
import os
from pathlib import Path
from typing import Any, ClassVar

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

logger = logging.getLogger(__name__)


class HttpConfig(BaseModel):
    """HTTP server settings."""

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080, ge=1, le=65535)


class LoggingConfig(BaseModel):
    """Logging settings."""

    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class OpenAIConfig(BaseModel):
    """OpenAI client settings."""

    api_key: str | None = Field(default=None)
    model: str = Field(default="gpt-4.1-mini")
    base_url: str | None = Field(default=None)
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class TrinoConfig(BaseModel):
    """Trino connection settings."""

    host: str = Field(default="localhost")
    port: int = Field(default=8080, ge=1, le=65535)
    user: str = Field(default="trino")
    catalog: str = Field(default="hive")
    schema: str = Field(default="default")
    http_scheme: str = Field(default="http")


class ServiceConfig(BaseModel):
    """Service-level settings."""

    name: str = Field(default="ai-insight-service")
    environment: str = Field(default="development")


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that loads values from YAML files."""

    _yaml_data: ClassVar[dict[str, Any]] = {}

    @classmethod
    def set_yaml_data(cls, data: dict[str, Any]) -> None:
        cls._yaml_data = data

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        field_value = self._yaml_data.get(field_name)
        return field_value, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._yaml_data


class Settings(BaseSettings):
    """Main settings object for AI Insight Service."""

    model_config = SettingsConfigDict(
        env_prefix="AI_INSIGHT_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    service: ServiceConfig = Field(default_factory=ServiceConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    trino: TrinoConfig = Field(default_factory=TrinoConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
        )


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge dictionaries with override precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_yaml_config(config_file: Path) -> dict[str, Any]:
    """Load YAML config file content."""
    if not config_file.exists():
        return {}
    with open(config_file, encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid root type in config file: {config_file}")
    return data


def load_config(config_path: Path | str | None = None, env: str | None = None) -> Settings:
    """Load settings from default YAML + environment YAML + env vars."""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config"
    elif isinstance(config_path, str):
        config_path = Path(config_path)

    default_cfg = load_yaml_config(config_path / "default.yaml")
    environment = env or os.getenv("FACIS_ENV", "development")
    env_cfg = load_yaml_config(config_path / f"{environment}.yaml")
    merged = deep_merge(default_cfg, env_cfg)

    YamlConfigSettingsSource.set_yaml_data(merged)
    settings = Settings()
    logger.debug("Loaded configuration for environment=%s", environment)
    return settings
