"""Header construction for upstream requests."""

from typing import Any


class HeaderBuilder:
    """Build upstream headers for different targets."""

    def build_anthropic_headers(self, headers: dict[str, Any]) -> dict[str, str]:
        """Pass through auth and anthropic-* headers."""
        upstream: dict[str, str] = {"Content-Type": "application/json"}
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in ("authorization", "x-api-key") or key_lower.startswith("anthropic-"):
                upstream[key] = str(value)
        return upstream

    def build_zai_headers(self, headers: dict[str, Any], api_key: str) -> dict[str, str]:
        """Build upstream headers for z.ai."""
        return {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": str(headers.get("anthropic-version", "2023-06-01")),
        }
