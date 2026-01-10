"""Configuration models and loading."""

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

# User data directory (for OAuth tokens)
CONFIG_DIR = Path.home() / ".config" / "claude-code-proxy"

# Config files in repo root
CONFIG_FILE = Path(__file__).parent.parent / "config.toml"
CONFIG_EXAMPLE = Path(__file__).parent.parent / "config.example.toml"


class Config(BaseModel):
    """Flattened configuration model."""

    # Proxy settings
    port: int = 8080
    debug: bool = True

    # Anthropic settings
    anthropic_base_url: str = "https://api.anthropic.com"

    # z.ai settings
    zai_base_url: str = "https://api.z.ai/api/anthropic"
    zai_api_key: str = ""

    # Routing settings
    subagent_markers: list[str] = Field(
        default_factory=lambda: ["You are a Claude agent, built on Anthropic's Claude Agent SDK."]
    )
    anthropic_markers: list[str] = Field(default_factory=list)

    # Limits settings
    max_body_size: int = 50 * 1024 * 1024  # 50MB
    timeout: float = 300.0  # 5 minutes
    max_connections: int = 100
    max_keepalive: int = 20
    subagent_tool_warning: int = 30  # Warn subagents after N tool uses (0 to disable)


def load_config() -> Config:
    """Load config from TOML. Exit with message if missing."""
    if not CONFIG_FILE.exists():
        raise SystemExit(
            f"Config not found: {CONFIG_FILE}\n"
            f"Copy {CONFIG_EXAMPLE.name} to {CONFIG_FILE.name} and set your API key."
        )

    with CONFIG_FILE.open("rb") as f:
        data = tomllib.load(f)

    # Flatten nested structure from TOML
    flat = {
        "port": data.get("proxy", {}).get("port", 8080),
        "debug": data.get("proxy", {}).get("debug", True),
        "anthropic_base_url": data.get("anthropic", {}).get("base_url", "https://api.anthropic.com"),
        "zai_base_url": data.get("zai", {}).get("base_url", "https://api.z.ai/api/anthropic"),
        "zai_api_key": data.get("zai", {}).get("api_key", ""),
        "subagent_markers": data.get("routing", {}).get("subagent_markers", ["You are a Claude agent, built on Anthropic's Claude Agent SDK."]),
        "anthropic_markers": data.get("routing", {}).get("anthropic_markers", []),
        "max_body_size": data.get("limits", {}).get("max_body_size", 50 * 1024 * 1024),
        "timeout": data.get("limits", {}).get("timeout", 300.0),
        "max_connections": data.get("limits", {}).get("max_connections", 100),
        "max_keepalive": data.get("limits", {}).get("max_keepalive", 20),
        "subagent_tool_warning": data.get("limits", {}).get("subagent_tool_warning", 30),
    }
    return Config.model_validate(flat)
