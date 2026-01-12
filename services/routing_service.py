"""Routing orchestration for proxy requests."""

from typing import Any

from core.config import Config
from core.headers import build_anthropic_headers, build_zai_headers
from core.router import decide_route
from core.sanitize import sanitize
from core.sanitize.system_prompt import extract_system_text
from core.tool_tracker import count_tool_uses, inject_tool_limit_reminder
from core.transform import strip_anthropic_features
from ui.dashboard import Dashboard

# (route_name, target_url, headers, body)
PreparedRequest = tuple[str, str, dict[str, str], dict[str, Any]]


class RoutingService:
    """Prepare requests for routing to Anthropic or z.ai."""

    def __init__(
        self,
        config: Config,
        logger: Dashboard,
    ) -> None:
        self._config = config
        self._logger = logger
        self._subagent_markers = config.routing.subagent_markers
        self._anthropic_markers = config.routing.anthropic_markers

    def prepare_messages(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
    ) -> PreparedRequest:
        """Prepare /v1/messages request for routing."""
        return self._prepare_request(body, headers, "/v1/messages", is_messages=True)

    def _sanitize_request(
        self,
        body: dict[str, Any],
        is_zai: bool,
        strip_claude_md: bool,
    ) -> dict[str, Any]:
        """Apply sanitization rules to request body.

        Args:
            body: Request body to sanitize
            is_zai: Whether request is routed to z.ai
            strip_claude_md: Whether to strip CLAUDE.md context

        Returns:
            Sanitized request body
        """
        return sanitize(
            body,
            strip_mcp=not is_zai,
            strip_claude_md=strip_claude_md,
            strip_tools=not is_zai,
            strip_post_env=is_zai,
            stripped_tools=set(self._config.sanitize.hidden_tools),
        )

    def _should_strip_claude_md(self, body: dict[str, Any]) -> bool:
        """Check if CLAUDE.md should be stripped based on configured markers."""
        markers = self._config.sanitize.strip_claude_md_markers
        if not markers:
            return False
        system_text = extract_system_text(body.get("system"))
        return any(marker in system_text for marker in markers)

    def prepare_count_tokens(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
    ) -> PreparedRequest:
        """Prepare /v1/messages/count_tokens request for routing."""
        return self._prepare_request(body, headers, "/v1/messages/count_tokens", is_messages=False)

    def _prepare_request(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
        path: str,
        is_messages: bool,
    ) -> PreparedRequest:
        """Common preparation logic for all request types.

        Args:
            body: Request body to prepare
            headers: Original request headers
            path: API path (for logging/context)
            is_messages: Whether this is a /v1/messages request (vs count_tokens)

        Returns:
            Prepared request tuple
        """
        route = decide_route(body, self._subagent_markers, self._anthropic_markers)
        is_zai = route == "zai"

        # Keep MCP tools for z.ai subagents, strip for main session
        # Strip CLAUDE.md context only for specific subagents (configured markers)
        strip_claude_md = is_zai and self._should_strip_claude_md(body)
        body = self._sanitize_request(body, is_zai, strip_claude_md)

        if is_zai:
            return self._prepare_zai(body, headers, path, is_messages)
        return self._prepare_anthropic(body, headers, path, is_messages)

    def _log_request(
        self,
        route: str,
        model: str,
        body: dict[str, Any],
        path: str,
        is_messages: bool,
        session_body: dict[str, Any] | None = None,
    ) -> None:
        """Log request to dashboard.

        Args:
            route: Target route ('anthropic' or 'zai')
            model: Model name
            body: Request body
            path: API path
            is_messages: Whether this is a /v1/messages request
            session_body: Original session body (z.ai only)
        """
        if route == "anthropic":
            if is_messages:
                self._logger.log_anthropic(model, body, streaming=body.get("stream", False), path=path)
            else:
                self._logger.log_anthropic(model, body, path=path)
        else:  # zai
            if is_messages:
                self._logger.log_zai(model, body, {}, path=path, session_body=session_body)
            else:
                self._logger.log_zai(model, body, {}, path=path)

    def _prepare_anthropic(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
        path: str,
        is_messages: bool,
    ) -> PreparedRequest:
        """Prepare request for Anthropic."""
        model = body.get("model", "unknown")
        upstream_headers = build_anthropic_headers(headers)
        self._log_request("anthropic", model, body, path, is_messages)
        return "Anthropic", self._config.anthropic.base_url, upstream_headers, body

    def _prepare_zai(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
        path: str,
        is_messages: bool,
    ) -> PreparedRequest:
        """Prepare request for z.ai."""
        original_body = body
        model = body.get("model", "unknown")

        if is_messages:
            body = strip_anthropic_features(body)
            threshold = self._config.limits.subagent_tool_warning
            if threshold > 0:
                tool_count = count_tool_uses(body.get("messages", []))
                body = inject_tool_limit_reminder(body, tool_count, threshold)
            self._log_request("zai", model, body, path, is_messages, session_body=original_body)
        else:
            body = strip_anthropic_features(body)
            self._log_request("zai", model, body, path, is_messages)

        upstream_headers = build_zai_headers(headers, self._config.zai.api_key)
        return "z.ai", self._config.zai.base_url, upstream_headers, body
