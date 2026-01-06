"""Configuration models and loading."""

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

# User data directory (for OAuth tokens)
CONFIG_DIR = Path.home() / ".config" / "claude-code-proxy"

# Config files in repo root
CONFIG_FILE = Path(__file__).parent.parent / "config.toml"
CONFIG_EXAMPLE = Path(__file__).parent.parent / "config.example.toml"


class ProxySettings(BaseModel):
    port: int = 8080
    debug: bool = True


class AnthropicSettings(BaseModel):
    base_url: str = "https://api.anthropic.com"


class ZaiSettings(BaseModel):
    base_url: str = "https://api.z.ai/api/anthropic"
    api_key: str = ""


class RoutingSettings(BaseModel):
    subagent_markers: list[str] = Field(
        default_factory=lambda: ["You are a Claude agent, built on Anthropic's Claude Agent SDK."]
    )
    anthropic_markers: list[str] = Field(default_factory=list)


class LimitsSettings(BaseModel):
    max_body_size: int = 50 * 1024 * 1024  # 50MB
    timeout: float = 300.0  # 5 minutes
    max_connections: int = 100
    max_keepalive: int = 20


class Config(BaseModel):
    proxy: ProxySettings = Field(default_factory=ProxySettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    zai: ZaiSettings = Field(default_factory=ZaiSettings)
    routing: RoutingSettings = Field(default_factory=RoutingSettings)
    limits: LimitsSettings = Field(default_factory=LimitsSettings)


def load_config() -> Config:
    """Load config from TOML. Exit with message if missing."""
    if not CONFIG_FILE.exists():
        raise SystemExit(
            f"Config not found: {CONFIG_FILE}\n"
            f"Copy {CONFIG_EXAMPLE.name} to {CONFIG_FILE.name} and set your API key."
        )

    with CONFIG_FILE.open("rb") as f:
        data = tomllib.load(f)

    return Config.model_validate(data)
