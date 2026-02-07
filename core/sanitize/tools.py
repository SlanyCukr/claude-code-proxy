"""Tool stripping logic for request sanitization."""

from typing import Any

from .patterns import (
    MCP_TOOL_ALLOWLIST,
    MCP_TOOL_PREFIX,
    MCP_TOOL_PREFIX_ALLOWLIST,
)


def strip_tools_inplace(
    body: dict[str, Any],
    *,
    strip_mcp: bool = True,
    stripped_tools: set[str],
) -> None:
    """Strip unwanted tools from the request body in place.

    Args:
        body: Request body (modified in place).
        strip_mcp: Whether to strip MCP tools (except allowlisted ones).
        stripped_tools: Set of tool names to strip.
    """
    tools = body.get("tools")
    if not isinstance(tools, list):
        return

    stripped = stripped_tools
    body["tools"] = [
        tool for tool in tools if not _should_strip_tool(tool, stripped, strip_mcp)
    ]

    # Remove tool_choice if it references a stripped tool (using same logic as tool filtering)
    tool_choice = body.get("tool_choice")
    if isinstance(tool_choice, dict):
        name = tool_choice.get("name")
        if name in stripped or (
            strip_mcp
            and isinstance(name, str)
            and name.startswith(MCP_TOOL_PREFIX)
            and name not in MCP_TOOL_ALLOWLIST
            and not any(name.startswith(prefix) for prefix in MCP_TOOL_PREFIX_ALLOWLIST)
        ):
            body.pop("tool_choice", None)


def _should_strip_tool(tool: Any, stripped_tools: set[str], strip_mcp: bool) -> bool:
    """Determine if a tool should be stripped."""
    if not isinstance(tool, dict):
        return False
    name = tool.get("name")
    if not isinstance(name, str):
        return False
    if name in stripped_tools:
        return True
    if not strip_mcp or not name.startswith(MCP_TOOL_PREFIX):
        return False
    # Check exact allowlist
    if name in MCP_TOOL_ALLOWLIST:
        return False
    # Check prefix allowlist (allow all tools from certain servers)
    return not any(name.startswith(prefix) for prefix in MCP_TOOL_PREFIX_ALLOWLIST)
