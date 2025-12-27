"""Request routing logic - determines Anthropic vs z.ai."""

from dataclasses import dataclass
from typing import Any

SUBAGENT_MARKER = "<role>"


@dataclass(frozen=True)
class RouteDecision:
    """Routing decision for a request."""

    route: str
    model_override: str | None = None


class RouteDecider:
    """Decide whether a request should go to Anthropic or z.ai."""

    def decide(self, body: dict[str, Any]) -> RouteDecision:
        """Return the route based on system prompt patterns."""
        if self._has_subagent_marker(body):
            return RouteDecision(route="zai")
        return RouteDecision(route="anthropic")

    def _has_subagent_marker(self, body: dict[str, Any]) -> bool:
        """Check if system prompt contains subagent marker."""
        system = body.get("system", [])
        if isinstance(system, str):
            return SUBAGENT_MARKER in system
        if isinstance(system, list):
            for item in system:
                if isinstance(item, dict) and SUBAGENT_MARKER in item.get("text", ""):
                    return True
        return False
