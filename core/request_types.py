"""Shared request data types."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PreparedRequest:
    """Prepared data for an upstream request."""

    route_name: str
    target_url: str
    headers: dict[str, str]
    body: dict[str, Any]
