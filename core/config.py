"""Configuration models and loading."""

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

CONFIG_DIR = Path.home() / ".config" / "claude-code-proxy"
CONFIG_FILE = CONFIG_DIR / "config.json"


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


class Config(BaseModel):
    proxy: ProxySettings = Field(default_factory=ProxySettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    zai: ZaiSettings = Field(default_factory=ZaiSettings)
    routing: RoutingSettings = Field(default_factory=RoutingSettings)


def load_config() -> Config:
    """Load configuration from JSON file, creating default if needed."""
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        default = Config()
        CONFIG_FILE.write_text(default.model_dump_json(indent=2))
        return default

    try:
        data = json.loads(CONFIG_FILE.read_text())
        return Config.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        # Backup corrupted config and recreate default
        backup = CONFIG_FILE.with_suffix(".json.bak")
        CONFIG_FILE.rename(backup)
        default = Config()
        CONFIG_FILE.write_text(default.model_dump_json(indent=2))
        return default
