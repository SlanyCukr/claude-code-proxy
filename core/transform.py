"""Request body transformations for z.ai compatibility."""

import copy
from typing import Any

# Noise patterns in system-reminders that should be stripped (not user instructions)
NOISE_PATTERNS = [
    "TodoWrite tool hasn't been used",
    "Plan mode is active",
    "consider whether it would be considered malware",
    "SessionStart:",
    "UserPromptSubmit:",
]


class RequestTransformer:
    """Transform request bodies for upstream compatibility."""

    def strip_anthropic_features(self, body: dict[str, Any]) -> dict[str, Any]:
        """Strip Anthropic-specific features that z.ai/GLM may not support."""
        body = copy.deepcopy(body)

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
                    msg["content"] = [
                        block
                        for block in msg["content"]
                        if not self._is_noise_reminder(block)
                    ]
                    # Remove cache_control from remaining blocks
                    for block in msg["content"]:
                        if isinstance(block, dict):
                            block.pop("cache_control", None)

        return body

    @staticmethod
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
