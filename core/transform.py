"""Request body transformations for z.ai compatibility."""

from typing import Any

from core.sanitize.patterns import NOISE_REMINDER_MARKERS


def strip_anthropic_features_inplace(body: dict[str, Any]) -> None:
    """Strip Anthropic-specific features that z.ai/GLM may not support.

    Modifies body in place. Caller must ensure body is already a deep copy.
    """
    # Remove metadata field
    body.pop("metadata", None)

    # Remove cache_control from system prompts
    if isinstance(body.get("system"), list):
        for item in body["system"]:
            if isinstance(item, dict):
                item.pop("cache_control", None)

    # Process messages
    if isinstance(body.get("messages"), list):
        for msg in body["messages"]:
            if isinstance(msg.get("content"), list):
                # Filter out noise system-reminder blocks, preserve user context
                filtered = [
                    block
                    for block in msg["content"]
                    if not _is_noise_reminder(block)
                ]
                # Only update if we still have content (API rejects empty content lists)
                if filtered:
                    msg["content"] = filtered
                # Remove cache_control from remaining blocks
                for block in msg["content"]:
                    if isinstance(block, dict):
                        block.pop("cache_control", None)


def _is_noise_reminder(block: dict) -> bool:
    """Check if a system-reminder is noise (not user context like claudeMd)."""
    if not isinstance(block, dict):
        return False
    if block.get("type") != "text":
        return False
    text = block.get("text", "")
    if not isinstance(text, str) or "<system-reminder>" not in text:
        return False
    # Preserve user context (CLAUDE.md content, rules, etc.)
    if "# claudeMd" in text:
        return False
    # Strip known noise patterns
    return any(pattern in text for pattern in NOISE_REMINDER_MARKERS)
