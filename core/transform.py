"""Request body transformations for z.ai compatibility."""

from typing import Any

# Noise patterns in system-reminders that should be stripped (not user instructions)
NOISE_PATTERNS = [
    "TodoWrite tool hasn't been used",
    "Plan mode is active",
    "consider whether it would be considered malware",
    "SessionStart:",
    "UserPromptSubmit:",
]


def strip_anthropic_features(body: dict[str, Any]) -> dict[str, Any]:
    """Strip Anthropic-specific features that z.ai/GLM may not support."""
    # Shallow copy the top-level dict
    body = body.copy()

    # Remove metadata field
    body.pop("metadata", None)

    # Remove cache_control from system prompts
    if isinstance(body.get("system"), list):
        # Shallow copy system list and items we modify
        body["system"] = [dict(item) if isinstance(item, dict) else item for item in body["system"]]
        for item in body["system"]:
            if isinstance(item, dict):
                item.pop("cache_control", None)

    # Process messages
    if isinstance(body.get("messages"), list):
        # Shallow copy messages list
        body["messages"] = list(body["messages"])
        for msg in body["messages"]:
            if isinstance(msg.get("content"), list):
                # Filter out noise system-reminder blocks, preserve user context
                filtered_content = [
                    block
                    for block in msg["content"]
                    if not _is_noise_reminder(block)
                ]
                # Shallow copy the filtered content blocks we modify
                msg["content"] = [dict(block) if isinstance(block, dict) else block for block in filtered_content]
                # Remove cache_control from remaining blocks
                for block in msg["content"]:
                    if isinstance(block, dict):
                        block.pop("cache_control", None)

    return body


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
    return any(pattern in text for pattern in NOISE_PATTERNS)
