"""Routing orchestration for proxy requests."""

from typing import Any

from core.config import Config
from core.headers import HeaderBuilder
from core.protocols import RequestLogger
from core.router import RouteDecider
from core.sanitize import RequestSanitizer
from core.tool_tracker import count_tool_uses, inject_tool_limit_reminder
from core.transform import RequestTransformer

# (route_name, target_url, headers, body)
PreparedRequest = tuple[str, str, dict[str, str], dict[str, Any]]


class RoutingService:
    """Prepare requests for routing to Anthropic or z.ai."""

    def __init__(
        self,
        config: Config,
        logger: RequestLogger,
        decider: RouteDecider,
        transformer: RequestTransformer,
        sanitizer: RequestSanitizer,
        header_builder: HeaderBuilder,
    ) -> None:
        self._config = config
        self._logger = logger
        self._decider = decider
        self._transformer = transformer
        self._sanitizer = sanitizer
        self._headers = header_builder

    def prepare_messages(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
    ) -> PreparedRequest:
        """Prepare /v1/messages request for routing."""
        decision = self._decider.decide(body)
        is_zai = decision.route == "zai"
        # Keep MCP tools for z.ai subagents, strip for main session
        body = self._sanitizer.sanitize(body, strip_mcp=not is_zai)

        if is_zai:
            return self._prepare_zai_messages(body, headers, decision.model_override)
        return self._prepare_anthropic_messages(body, headers)

    def prepare_count_tokens(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
    ) -> PreparedRequest:
        """Prepare /v1/messages/count_tokens request for routing."""
        decision = self._decider.decide(body)
        is_zai = decision.route == "zai"
        body = self._sanitizer.sanitize(body, strip_mcp=not is_zai)

        if is_zai:
            return self._prepare_zai_count_tokens(body, headers)
        return self._prepare_anthropic_count_tokens(body, headers)

    def _prepare_anthropic_messages(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
    ) -> PreparedRequest:
        """Prepare /v1/messages for Anthropic."""
        model = body.get("model", "unknown")
        upstream_headers = self._headers.build_anthropic_headers(headers)
        is_streaming = body.get("stream", False)
        self._logger.log_anthropic(
            model,
            body,
            streaming=is_streaming,
            path="/v1/messages",
        )
        return "Anthropic", self._config.anthropic_base_url, upstream_headers, body

    def _prepare_anthropic_count_tokens(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
    ) -> PreparedRequest:
        """Prepare /v1/messages/count_tokens for Anthropic."""
        model = body.get("model", "unknown")
        self._logger.log_anthropic(
            model,
            body,
            path="/v1/messages/count_tokens",
        )
        upstream_headers = self._headers.build_anthropic_headers(headers)
        return "Anthropic", self._config.anthropic_base_url, upstream_headers, body

    def _prepare_zai_messages(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
        model_override: str | None,
    ) -> PreparedRequest:
        """Prepare /v1/messages for z.ai."""
        original_body = body  # Keep reference for session_id extraction
        model = body.get("model", "unknown")

        body = self._transformer.strip_anthropic_features(body)

        # Inject tool usage warning for subagents if threshold exceeded
        threshold = self._config.subagent_tool_warning
        if threshold > 0:
            tool_count = count_tool_uses(body.get("messages", []))
            body = inject_tool_limit_reminder(body, tool_count, threshold)

        if model_override:
            body["model"] = model_override
            model = f"{model_override} (was {model})"

        upstream_headers = self._headers.build_zai_headers(headers, self._config.zai_api_key)
        self._logger.log_zai(
            model,
            body,
            upstream_headers,
            path="/v1/messages",
            session_body=original_body,
        )
        return "z.ai", self._config.zai_base_url, upstream_headers, body

    def _prepare_zai_count_tokens(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
    ) -> PreparedRequest:
        """Prepare /v1/messages/count_tokens for z.ai."""
        model = body.get("model", "unknown")
        self._logger.log_zai(
            model,
            body,
            {},
            path="/v1/messages/count_tokens",
        )
        body = self._transformer.strip_anthropic_features(body)
        upstream_headers = self._headers.build_zai_headers(headers, self._config.zai_api_key)
        return "z.ai", self._config.zai_base_url, upstream_headers, body
