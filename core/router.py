"""Request routing logic - determines Anthropic vs z.ai."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RouteDecision:
    """Routing decision for a request."""

    route: str
    model_override: str | None = None


class RouteDecider:
    """Decide whether a request should go to Anthropic or z.ai."""

    def __init__(self, subagent_markers: list[str] | None = None):
        self.subagent_markers = subagent_markers or []

    def decide(self, body: dict[str, Any]) -> RouteDecision:
        """Return the route based on system prompt patterns."""
        if self._has_subagent_marker(body):
            return RouteDecision(route="zai")
        return RouteDecision(route="anthropic")

    def _has_subagent_marker(self, body: dict[str, Any]) -> bool:
        """Check if system prompt contains any subagent marker."""
        system = body.get("system", [])
        system_text = self._extract_system_text(system)
        return any(marker in system_text for marker in self.subagent_markers)

    def _extract_system_text(self, system: str | list[Any]) -> str:
        """Extract all text from system prompt."""
        if isinstance(system, str):
            return system
        if isinstance(system, list):
            parts = []
            for item in system:
                if isinstance(item, dict):
                    parts.append(item.get("text", ""))
            return " ".join(parts)
        return ""
