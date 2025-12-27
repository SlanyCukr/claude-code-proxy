"""Shared protocol definitions."""

from typing import Any, Protocol


class RequestLogger(Protocol):
    """Protocol for request logging (Dashboard)."""

    def log_anthropic(
        self,
        model: str,
        body: dict[str, Any],
        streaming: bool = False,
        *,
        path: str,
    ) -> None: ...
    def log_zai(
        self,
        model: str,
        body: dict[str, Any],
        headers: dict[str, str],
        *,
        path: str,
        session_body: dict[str, Any] | None = None,
    ) -> None: ...
    def log_error(self, route: str, status: int, message: str) -> None: ...
