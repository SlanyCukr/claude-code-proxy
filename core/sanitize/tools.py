"""Tool stripping logic for request sanitization."""

from typing import Any

from .patterns import (
    DEFAULT_STRIPPED_TOOLS,
    MCP_TOOL_ALLOWLIST,
    MCP_TOOL_PREFIX,
)


def strip_tools_inplace(
    body: dict[str, Any],
    *,
    strip_mcp: bool = True,
    stripped_tools: set[str] | None = None,
) -> None:
    """Strip unwanted tools from the request body in place.

    Args:
        body: Request body (modified in place).
        strip_mcp: Whether to strip MCP tools (except allowlisted ones).
        stripped_tools: Set of tool names to strip. Defaults to DEFAULT_STRIPPED_TOOLS.
    """
    tools = body.get("tools")
    if not isinstance(tools, list):
        return

    stripped = stripped_tools or DEFAULT_STRIPPED_TOOLS
    body["tools"] = [
        tool for tool in tools if not _should_strip_tool(tool, stripped, strip_mcp)
    ]

    # Remove tool_choice if it references a stripped tool
    tool_choice = body.get("tool_choice")
    if isinstance(tool_choice, dict) and tool_choice.get("name") in stripped:
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
    return strip_mcp and name.startswith(MCP_TOOL_PREFIX) and name not in MCP_TOOL_ALLOWLIST
