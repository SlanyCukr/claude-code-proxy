"""System reminder stripping and transformation."""

from collections.abc import Callable
from typing import Any

from .patterns import (
    CLAUDE_MD_REMINDER_PATTERN,
    MALWARE_REMINDER_PATTERN,
    PLAN_MODE_REPLACEMENTS,
    POST_ENV_INFO_PATTERN,
    POST_ENV_REPLACEMENT,
    RESULT_SEPARATOR,
    TOOL_CALL_LOG_PATTERN,
    TOOL_RESULT_OUTPUT_WRAPPER,
)

# Marker text for malware reminder detection
_MALWARE_MARKER = "you should consider whether it would be considered malware"


def _content_contains(content: Any, marker: str) -> bool:
    """Check if content (str or list of blocks) contains marker text.

    Args:
        content: Content value to search (str, list, or other).
        marker: Text marker to search for.

    Returns:
        True if marker is found in any text blocks, False otherwise.
    """
    if isinstance(content, str):
        return marker in content
    if isinstance(content, list):
        for b in content:
            if not isinstance(b, dict):
                continue
            # Check text blocks
            if b.get("type") == "text" and marker in b.get("text", ""):
                return True
            # Check tool_result blocks
            if b.get("type") == "tool_result":
                tool_content = b.get("content", "")
                if isinstance(tool_content, str) and marker in tool_content:
                    return True
    return False


def _contains_malware_marker(content: Any) -> bool:
    """Check if content contains the malware reminder marker."""
    return _content_contains(content, _MALWARE_MARKER)


def _strip_malware_reminder(text: str) -> str:
    """Strip malware reminder from text."""
    return MALWARE_REMINDER_PATTERN.sub("", text)


def _apply_to_content_blocks(
    content: Any,
    transform: Callable[[str], str],
) -> Any:
    """Apply a transformation function to text content blocks.

    Args:
        content: Content value (str, list, or other).
        transform: Function that transforms text content.

    Returns:
        Transformed content in the same structure.
    """
    if isinstance(content, str):
        result = transform(content)
        return result if result.strip() else content
    if isinstance(content, list):
        to_remove: list[int] = []
        for i, block in enumerate(content):
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if isinstance(text, str):
                    result = transform(text)
                    if result.strip():
                        block["text"] = result
                    else:
                        to_remove.append(i)
        for i in reversed(to_remove):
            content.pop(i)
    return content


def _apply_to_messages(
    body: dict[str, Any],
    transform: Callable[[str], str],
    *,
    role: str | None = None,
    content_key: str = "content",
    content_filter: Callable[[Any], bool] | None = None,
) -> None:
    """Apply a transformation function to message content blocks.

    Args:
        body: Request body (modified in place).
        transform: Function that transforms text content.
        role: Optional role filter (e.g., "user").
        content_key: Key to access content in messages (default "content").
        content_filter: Optional predicate to filter which messages to process.
    """
    messages = body.get("messages")
    if not isinstance(messages, list):
        return

    for msg in messages:
        if role is not None and msg.get("role") != role:
            continue
        content = msg.get(content_key)
        if content_filter is not None and not content_filter(content):
            continue
        msg[content_key] = _apply_to_content_blocks(content, transform)


def _apply_to_system(
    body: dict[str, Any],
    transform: Callable[[str], str],
) -> None:
    """Apply a transformation function to system prompt.

    Args:
        body: Request body (modified in place).
        transform: Function that transforms text content.
    """
    system = body.get("system")
    if not system:
        return

    body["system"] = _apply_to_content_blocks(system, transform)


def strip_system_reminders_inplace(body: dict[str, Any]) -> None:
    """Strip specific <system-reminder> blocks from message content.

    Args:
        body: Request body (modified in place).
    """
    messages = body.get("messages")
    if not isinstance(messages, list):
        return

    # Check for markers
    has_malware = any(_contains_malware_marker(msg.get("content")) for msg in messages)

    if not has_malware:
        return

    # Apply to text blocks in messages
    _apply_to_messages(body, _strip_malware_reminder)

    # Apply to tool_result blocks
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, list):
            _apply_transform_to_blocks(content, "tool_result", _strip_malware_reminder)


def strip_claude_md_reminder_inplace(body: dict[str, Any]) -> None:
    """Strip CLAUDE.md context reminders from message content.

    These reminders are injected by Claude Code for all requests but are
    unnecessary for subagents that don't need project context.

    Args:
        body: Request body (modified in place).
    """
    _apply_to_messages(body, lambda text: CLAUDE_MD_REMINDER_PATTERN.sub("", text))


def _strip_post_env_info(text: str) -> str:
    """Strip post-env info if present."""
    if "</env>" in text:
        return POST_ENV_INFO_PATTERN.sub(POST_ENV_REPLACEMENT, text)
    return text


def strip_post_env_info_inplace(body: dict[str, Any]) -> None:
    """Strip verbose info after </env> block from system prompt.

    Removes model info, knowledge cutoff, claude_background_info, and gitStatus
    which are unnecessary for subagents.

    Args:
        body: Request body (modified in place).
    """
    _apply_to_system(body, _strip_post_env_info)


def transform_plan_mode_reminder_inplace(body: dict[str, Any]) -> None:
    """Transform plan mode system reminder to use plugin agents.

    Args:
        body: Request body (modified in place).
    """
    plan_mode_marker = "Plan mode is active"

    messages = body.get("messages")
    if not isinstance(messages, list):
        return

    if not any(_content_contains(msg.get("content"), plan_mode_marker) for msg in messages):
        return

    def _transform(text: str) -> str:
        for old, new in PLAN_MODE_REPLACEMENTS:
            text = text.replace(old, new)
        return text

    _apply_to_messages(body, _transform)


def strip_tool_result_logs_inplace(body: dict[str, Any]) -> None:
    """Strip verbose tool call logs from tool_result content blocks.

    Args:
        body: Request body (modified in place).
    """
    messages = body.get("messages")
    if not isinstance(messages, list):
        return

    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        _apply_transform_to_blocks(content, "tool_result", _strip_tool_call_logs)


def _apply_transform_to_blocks(
    blocks: list[dict[str, Any]],
    block_type: str,
    transform: Callable[[str], str],
    content_key: str = "content",
) -> None:
    """Apply a transformation function to specific block types in a content list.

    Args:
        blocks: List of content blocks (modified in place).
        block_type: The type of block to transform (e.g., "tool_result").
        transform: Function that transforms content.
        content_key: Key to access content within blocks (default "content").
    """
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == block_type:
            raw_content = block.get(content_key)
            if isinstance(raw_content, str):
                block[content_key] = transform(raw_content)


def _strip_tool_call_logs(content: str) -> str:
    """Strip tool call logs from <output> section, keeping metadata and result."""
    output_match = TOOL_RESULT_OUTPUT_WRAPPER.search(content)
    if not output_match:
        return content

    inner = output_match.group(1)

    # Find the actual result after separator
    if RESULT_SEPARATOR in inner:
        result_idx = inner.find(RESULT_SEPARATOR)
        cleaned_inner = inner[result_idx:].strip()  # Keep separator + result
    else:
        # No separator - strip tool call logs
        cleaned_inner = TOOL_CALL_LOG_PATTERN.sub("", inner).strip()

    # Replace original <output> section with cleaned version
    return content.replace(
        output_match.group(0), f"<output>\n{cleaned_inner}\n</output>"
    )
