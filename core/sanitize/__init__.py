"""Request sanitization for upstream routing.

This package handles all request body sanitization before routing to upstream
providers. It removes unwanted tools, filters Task tool descriptions, strips
system reminders, and replaces the system prompt.
"""

import copy
from typing import Any

from .reminders import (
    strip_claude_md_reminder_inplace,
    strip_post_env_info_inplace,
    strip_system_reminders_inplace,
    strip_tool_result_logs_inplace,
    transform_plan_mode_reminder_inplace,
)
from .system_prompt import replace_system_prompt_inplace
from .task_tool import filter_task_tool_inplace
from .tools import strip_tools_inplace

__all__ = ["sanitize"]


def sanitize(
    body: dict[str, Any],
    *,
    strip_mcp: bool = True,
    strip_claude_md: bool = False,
    strip_tools: bool = True,
    strip_post_env: bool = False,
    stripped_tools: set[str] | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Sanitize request body for upstream routing.

    Creates a single deep copy, then applies all transformations in place.

    Args:
        body: Original request body (not modified).
        strip_mcp: Whether to strip MCP tools (except allowlisted ones).
        strip_claude_md: Whether to strip CLAUDE.md context reminders (for subagents).
        stripped_tools: Set of tool names to strip.
        system_prompt: Custom system prompt replacement.

    Returns:
        Sanitized copy of the request body.
    """
    body = copy.deepcopy(body)

    if strip_tools:
        strip_tools_inplace(body, strip_mcp=strip_mcp, stripped_tools=stripped_tools)
    filter_task_tool_inplace(body)
    strip_system_reminders_inplace(body)
    transform_plan_mode_reminder_inplace(body)
    strip_tool_result_logs_inplace(body)
    if strip_claude_md:
        strip_claude_md_reminder_inplace(body)
    if strip_post_env:
        strip_post_env_info_inplace(body)
    replace_system_prompt_inplace(body, system_prompt)

    return body
