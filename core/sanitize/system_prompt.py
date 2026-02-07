"""System prompt replacement logic."""

import logging
from functools import cache
from pathlib import Path
from typing import Any

from core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# System prompt file path
_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "default_system.txt"


@cache
def get_default_system_prompt() -> str:
    """Load the default system prompt (cached after first call)."""
    if not _PROMPT_FILE.exists():
        raise ConfigurationError(f"System prompt not found: {_PROMPT_FILE}")
    return _PROMPT_FILE.read_text()


def replace_system_prompt_inplace(
    body: dict[str, Any],
    system_prompt: str | None = None,
) -> None:
    """Replace the system prompt with custom version, preserving env block.

    Args:
        body: Request body (modified in place).
        system_prompt: Custom system prompt. Defaults to the built-in prompt.
    """
    if "system" not in body:
        return

    prompt = system_prompt or get_default_system_prompt()
    original_system = body.get("system")
    original_text = extract_system_text(original_system)
    merged_prompt = _merge_env(prompt, original_text)
    normalized = _normalize_system(merged_prompt, original_system)

    if original_system != normalized:
        body["system"] = normalized


def _normalize_system(system_prompt: str, original_system: Any) -> Any:
    """Normalize system prompt to match original format."""
    if isinstance(original_system, list):
        updated = []
        replaced = False
        for item in original_system:
            if (
                isinstance(item, dict)
                and isinstance(item.get("text"), str)
                and "You are an interactive CLI tool" in item["text"]
            ):
                new_item = dict(item)
                new_item["text"] = system_prompt
                updated.append(new_item)
                replaced = True
            else:
                updated.append(item)
        if not replaced:
            logger.warning("System prompt replacement failed: marker 'You are an interactive CLI tool' not found")
        return updated if replaced else original_system

    if isinstance(original_system, dict):
        return {"type": "text", "text": system_prompt}

    return system_prompt


def extract_system_text(system: Any) -> str:
    """Extract text content from system prompt (handles various formats)."""
    if isinstance(system, list):
        parts: list[str] = []
        for item in system:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(system) if system else ""


def _extract_env_block(text: str) -> str | None:
    """Extract <env>...</env> block from text."""
    if not text:
        return None
    start = text.find("<env>")
    if start == -1:
        return None
    end = text.find("</env>", start)
    if end == -1:
        return None
    return text[start : end + len("</env>")]


def _merge_env(base_prompt: str, original_system: str) -> str:
    """Merge env block from original system into base prompt."""
    original_env = _extract_env_block(original_system)
    if not original_env:
        return base_prompt
    base_env = _extract_env_block(base_prompt)
    if not base_env:
        return base_prompt
    return base_prompt.replace(base_env, original_env, 1)
