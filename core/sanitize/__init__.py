"""Request sanitization for upstream routing.

This package handles all request body sanitization before routing to upstream
providers. It removes unwanted tools, filters Task tool descriptions, strips
system reminders, and replaces the system prompt.
"""

import copy
from typing import Any, Literal

from core.transform import strip_anthropic_features_inplace

from .bash_description import strip_bash_description_inplace
from .edit_tools import relax_read_requirement_inplace
from .reminders import (
    strip_claude_md_reminder_inplace,
    strip_post_env_info_inplace,
    strip_system_reminders_inplace,
    strip_tool_result_logs_inplace,
    transform_plan_mode_reminder_inplace,
)
from .search_tools import prioritize_semantic_search_inplace
from .system_prompt import replace_system_prompt_inplace
from .task_tool import filter_task_tool_inplace
from .tools import strip_tools_inplace

__all__ = ["sanitize"]


def sanitize(
    body: dict[str, Any],
    *,
    target_provider: Literal["anthropic", "zai"] = "anthropic",
    strip_mcp: bool = True,
    strip_claude_md: bool = False,
    strip_tools: bool = True,
    strip_post_env: bool = False,
    replace_system_prompt: bool = True,
    stripped_tools: set[str],
    stripped_agents: list[str] | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Sanitize request body for upstream routing.

    Creates a single deep copy, then applies all transformations in place.

    Args:
        body: Original request body (not modified).
        target_provider: Target provider ("anthropic" or "zai").
        strip_mcp: Whether to strip MCP tools (except allowlisted ones).
        strip_claude_md: Whether to strip CLAUDE.md context reminders (for subagents).
        strip_tools: Whether to strip tools from request.
        strip_post_env: Whether to strip post-env info from system prompt.
        replace_system_prompt: Whether to replace the system prompt.
        stripped_tools: Set of tool names to strip (from config).
        stripped_agents: List of agent names to strip from Task tool description.
        system_prompt: Custom system prompt replacement.

    Returns:
        Sanitized copy of the request body.
    """
    body = copy.deepcopy(body)

    if strip_tools:
        strip_tools_inplace(body, strip_mcp=strip_mcp, stripped_tools=stripped_tools)
    filter_task_tool_inplace(body, stripped_agents=stripped_agents)
    strip_system_reminders_inplace(body)
    transform_plan_mode_reminder_inplace(body)
    strip_tool_result_logs_inplace(body)
    if strip_claude_md:
        strip_claude_md_reminder_inplace(body)
    if strip_post_env:
        strip_post_env_info_inplace(body)
    if replace_system_prompt:
        replace_system_prompt_inplace(body, system_prompt)

    # Tool description transforms (all providers)
    prioritize_semantic_search_inplace(body)
    relax_read_requirement_inplace(body)
    strip_bash_description_inplace(body)

    # z.ai-specific transforms
    if target_provider == "zai":
        strip_anthropic_features_inplace(body)

    return body
