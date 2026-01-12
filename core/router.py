"""Request routing logic - determines Anthropic vs z.ai."""

from core.sanitize.system_prompt import extract_system_text


def decide_route(
    body: dict,
    subagent_markers: list[str],
    anthropic_markers: list[str],
) -> str:
    """Return 'anthropic' or 'zai' based on system prompt patterns.

    Args:
        body: Request body containing system prompt
        subagent_markers: Markers that indicate z.ai routing
        anthropic_markers: Markers that force Anthropic routing

    Returns:
        'anthropic' or 'zai'
    """
    system_text = extract_system_text(body.get("system"))

    # Check exclusions first - force Anthropic for specific agents
    if any(marker in system_text for marker in anthropic_markers):
        return "anthropic"

    # Then check subagent markers
    if any(marker in system_text for marker in subagent_markers):
        return "zai"

    return "anthropic"
