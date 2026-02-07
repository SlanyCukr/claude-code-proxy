"""Task tool description filtering."""

from typing import Any

from .patterns import (
    AGENT_TOOLS_PATTERN,
    BASH_AGENT_NEW_DESC,
    BASH_AGENT_OLD_DESC,
    CONTEXT_PATTERN,
    EXAMPLE_PATTERN,
    NEW_TASK_OPENING,
    OLD_OPENING_PATTERN,
    build_agent_pattern,
)


def filter_task_tool_inplace(
    body: dict[str, Any],
    stripped_agents: list[str] | None = None,
) -> None:
    """Remove agent descriptions and unwanted sections from Task tool.

    Args:
        body: Request body (modified in place).
        stripped_agents: List of agent names to strip from Task tool description.
    """
    if stripped_agents is None:
        stripped_agents = []

    tools = body.get("tools")
    if not isinstance(tools, list):
        return

    for tool in tools:
        if not isinstance(tool, dict) or tool.get("name") != "Task":
            continue
        description = tool.get("description", "")
        if not description:
            continue

        # Replace opening text
        description = OLD_OPENING_PATTERN.sub(NEW_TASK_OPENING, description)

        # Filter out configured agent entries
        for agent in stripped_agents:
            pattern = build_agent_pattern(agent)
            description = pattern.sub("", description)

        # Strip instruction and example sections
        description = CONTEXT_PATTERN.sub("", description)
        description = EXAMPLE_PATTERN.sub("", description)

        # Strip "(Tools: ...)" from agent descriptions
        description = AGENT_TOOLS_PATTERN.sub("", description)

        # Replace Bash agent description with more restrictive guidance
        description = BASH_AGENT_OLD_DESC.sub(BASH_AGENT_NEW_DESC, description)

        tool["description"] = description
        break
