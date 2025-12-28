"""Routing orchestration for proxy requests."""

from typing import Any

from core.config import Config
from core.headers import HeaderBuilder
from core.protocols import RequestLogger
from core.request_types import PreparedRequest
from core.router import RouteDecider
from core.sanitize import RequestSanitizer
from core.transform import RequestTransformer
from services.targets import AnthropicTarget, ZaiTarget


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
        anthropic_target: AnthropicTarget | None = None,
        zai_target: ZaiTarget | None = None,
    ) -> None:
        self._decider = decider
        self._transformer = transformer
        self._sanitizer = sanitizer
        self._anthropic = anthropic_target or AnthropicTarget(
            config, logger, header_builder
        )
        self._zai = zai_target or ZaiTarget(
            config, logger, transformer, header_builder
        )

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
            return self._zai.prepare_messages(body, headers, decision.model_override)

        return self._anthropic.prepare_messages(body, headers)

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
            return self._zai.prepare_count_tokens(body, headers)

        return self._anthropic.prepare_count_tokens(body, headers)
