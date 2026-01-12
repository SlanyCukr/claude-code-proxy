"""Task tool description filtering."""

from typing import Any

from .patterns import (
    AGENT_PATTERNS,
    AGENT_TOOLS_PATTERN,
    BASH_AGENT_NEW_DESC,
    BASH_AGENT_OLD_DESC,
    CONTEXT_PATTERN,
    DEFAULT_STRIPPED_AGENTS,
    EXAMPLE_PATTERN,
    NEW_TASK_OPENING,
    OLD_OPENING_PATTERN,
)


def filter_task_tool_inplace(body: dict[str, Any]) -> None:
    """Remove default agent descriptions and unwanted sections from Task tool.

    Args:
        body: Request body (modified in place).
    """
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

        # Filter out default agent entries
        for agent in DEFAULT_STRIPPED_AGENTS:
            description = AGENT_PATTERNS[agent].sub("", description)

        # Strip instruction and example sections
        description = CONTEXT_PATTERN.sub("", description)
        description = EXAMPLE_PATTERN.sub("", description)

        # Strip "(Tools: ...)" from agent descriptions
        description = AGENT_TOOLS_PATTERN.sub("", description)

        # Replace Bash agent description with more restrictive guidance
        description = BASH_AGENT_OLD_DESC.sub(BASH_AGENT_NEW_DESC, description)

        tool["description"] = description
        break
