"""Request routing logic - determines Anthropic vs z.ai."""

from typing import Any, Literal

from core.sanitize.system_prompt import extract_system_text

Route = Literal["anthropic", "zai"]
# (route, is_subagent)
RouteResult = tuple[Route, bool]


def decide_route(
    body: dict[str, Any],
    subagent_markers: list[str],
    anthropic_markers: list[str],
) -> RouteResult:
    """Return route and subagent status based on system prompt patterns.

    Args:
        body: Request body containing system prompt
        subagent_markers: Markers that indicate z.ai routing
        anthropic_markers: Markers that force Anthropic routing

    Returns:
        Tuple of (route, is_subagent) where route is 'anthropic' or 'zai'
    """
    system_text = extract_system_text(body.get("system"))
    is_subagent = any(marker in system_text for marker in subagent_markers)

    # Check exclusions first - force Anthropic for specific agents
    if any(marker in system_text for marker in anthropic_markers):
        return "anthropic", is_subagent

    # Route subagents to z.ai
    if is_subagent:
        return "zai", True

    return "anthropic", False
