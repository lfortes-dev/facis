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


class LlmConfig(BaseModel):
    """Provider-agnostic LLM client settings."""

    api_key: str | None = Field(default=None)
    model: str = Field(default="gpt-4.1-mini")
    chat_completions_url: str | None = Field(default=None)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_base_delay_seconds: float = Field(default=0.5, gt=0, le=10)
    retry_max_delay_seconds: float = Field(default=8.0, gt=0, le=60)
    require_https: bool = Field(default=True)


class TrinoConfig(BaseModel):
    """Trino connection settings."""

    host: str = Field(default="localhost")
    port: int = Field(default=8080, ge=1, le=65535)
    user: str = Field(default="trino")
    oidc_token_url: str | None = Field(default=None)
    oidc_client_id: str | None = Field(default=None)
    oidc_client_secret: str | None = Field(default=None)
    oidc_username: str | None = Field(default=None)
    oidc_password: str | None = Field(default=None)
    oidc_scope: str | None = Field(default="openid")
    oidc_verify: bool | str = Field(default=True)
    target_schema: str = Field(default="gold")
    table_net_grid_hourly: str = Field(default="net_grid_hourly")
    table_event_impact_daily: str = Field(default="event_impact_daily")
    table_streetlight_zone_hourly: str = Field(default="streetlight_zone_hourly")
    table_weather_hourly: str = Field(default="weather_hourly")
    table_energy_cost_daily: str = Field(default="energy_cost_daily")
    table_pv_self_consumption_daily: str = Field(default="pv_self_consumption_daily")
    catalog: str = Field(default="hive")
    schema: str = Field(default="default")
    http_scheme: str = Field(default="http")
    verify: bool | str = Field(default=True)
    request_timeout_seconds: int = Field(default=120, ge=1, le=300)


class ServiceConfig(BaseModel):
    """Service-level settings."""

    name: str = Field(default="ai-insight-service")
    environment: str = Field(default="development")


class PolicyConfig(BaseModel):
    """API-level policy enforcement settings."""

    enabled: bool = Field(default=True)
    agreement_header: str = Field(default="x-agreement-id")
    asset_header: str = Field(default="x-asset-id")
    role_header: str = Field(default="x-user-roles")
    required_roles: list[str] = Field(default_factory=lambda: ["ai_insight_consumer"])
    allowed_agreement_ids: list[str] = Field(default_factory=list)
    allowed_asset_ids: list[str] = Field(default_factory=list)


class RateLimitConfig(BaseModel):
    """Agreement-scoped rate limiting settings."""

    enabled: bool = Field(default=True)
    requests_per_minute: int = Field(default=10, ge=1, le=10000)


class CacheConfig(BaseModel):
    """Insight caching settings."""

    enabled: bool = Field(default=False)
    backend: str = Field(default="redis")
    redis_url: str | None = Field(default=None)
    ttl_seconds: int = Field(default=300, ge=1, le=86400)
    key_prefix: str = Field(default="ai-insight:cache:v1")
    connect_timeout_seconds: float = Field(default=1.0, gt=0, le=30)


class AuditConfig(BaseModel):
    """Audit logging settings."""

    enabled: bool = Field(default=True)
    log_prompts: bool = Field(default=True)
    log_responses: bool = Field(default=True)
    logger_name: str = Field(default="src.audit")


class PromptTemplatesConfig(BaseModel):
    """Prompt template externalization settings."""

    enabled: bool = Field(default=False)
    path: str = Field(default="/app/config/prompts")


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
        env_file=".env",
        env_file_encoding="utf-8",
    )

    service: ServiceConfig = Field(default_factory=ServiceConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    trino: TrinoConfig = Field(default_factory=TrinoConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    prompt_templates: PromptTemplatesConfig = Field(default_factory=PromptTemplatesConfig)

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
            dotenv_settings,
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
