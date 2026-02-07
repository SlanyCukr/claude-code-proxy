"""Configuration models and loading using pydantic-settings."""

from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

# User data directory (for OAuth tokens)
CONFIG_DIR = Path.home() / ".config" / "claude-code-proxy"

# Config files in repo root
CONFIG_FILE = Path(__file__).parent.parent / "config.toml"
CONFIG_EXAMPLE = Path(__file__).parent.parent / "config.example.toml"


class ProxyConfig(BaseModel):
    """Proxy server settings."""

    port: int
    debug: bool


class AnthropicConfig(BaseModel):
    """Anthropic API settings."""

    base_url: str


class ZaiConfig(BaseModel):
    """z.ai API settings."""

    base_url: str
    api_key: str


class RoutingConfig(BaseModel):
    """Request routing settings."""

    subagent_markers: list[str]
    anthropic_markers: list[str]


class LimitsConfig(BaseModel):
    """Request limits settings."""

    max_body_size: int
    max_connections: int
    max_keepalive: int
    keepalive_expiry: float
    connect_timeout: float
    pool_timeout: float
    keep_alive_timeout: int
    subagent_tool_warning: int
    token_count_timeout: float
    message_timeout: float


class SanitizeConfig(BaseModel):
    """Request sanitization settings."""

    hidden_tools: list[str]
    stripped_agents: list[str]
    strip_claude_md_markers: list[str]


class Config(BaseSettings):
    """Application configuration loaded from TOML file. All values required."""

    model_config = SettingsConfigDict(
        toml_file=str(CONFIG_FILE),
        extra="forbid",
    )

    proxy: ProxyConfig
    anthropic: AnthropicConfig
    zai: ZaiConfig
    routing: RoutingConfig
    limits: LimitsConfig
    sanitize: SanitizeConfig

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Only load from TOML file, ignore environment variables."""
        return (TomlConfigSettingsSource(settings_cls),)


def load_config() -> Config:
    """Load config from TOML file. All values must be present."""
    if not CONFIG_FILE.exists():
        raise SystemExit(
            f"Config not found: {CONFIG_FILE}\n"
            f"Copy {CONFIG_EXAMPLE.name} to {CONFIG_FILE.name} and configure all values."
        )

    try:
        return Config()  # type: ignore[call-arg]  # Values loaded from TOML
    except Exception as e:
        raise SystemExit(f"Invalid config: {e}") from e
