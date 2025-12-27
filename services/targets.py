"""Upstream target handlers for Anthropic and z.ai."""

from typing import Any

from core.config import Config
from core.headers import HeaderBuilder
from core.protocols import RequestLogger
from core.request_types import PreparedRequest
from core.transform import RequestTransformer


class AnthropicTarget:
    """Anthropic-specific request preparation."""

    def __init__(
        self,
        config: Config,
        logger: RequestLogger,
        header_builder: HeaderBuilder,
    ) -> None:
        self._config = config
        self._logger = logger
        self._headers = header_builder

    def prepare_messages(
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
        return PreparedRequest("Anthropic", self._config.anthropic.base_url, upstream_headers, body)

    def prepare_count_tokens(
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
        return PreparedRequest("Anthropic", self._config.anthropic.base_url, upstream_headers, body)


class ZaiTarget:
    """z.ai-specific request preparation."""

    def __init__(
        self,
        config: Config,
        logger: RequestLogger,
        transformer: RequestTransformer,
        header_builder: HeaderBuilder,
    ) -> None:
        self._config = config
        self._logger = logger
        self._transformer = transformer
        self._headers = header_builder

    def prepare_messages(
        self,
        body: dict[str, Any],
        headers: dict[str, Any],
        model_override: str | None = None,
    ) -> PreparedRequest:
        """Prepare /v1/messages for z.ai."""
        original_body = body  # Keep reference for session_id extraction
        model = body.get("model", "unknown")

        body = self._transformer.strip_anthropic_features(body)

        if model_override:
            body["model"] = model_override
            model = f"{model_override} (was {model})"

        upstream_headers = self._headers.build_zai_headers(headers, self._config.zai.api_key)
        self._logger.log_zai(
            model,
            body,
            upstream_headers,
            path="/v1/messages",
            session_body=original_body,
        )
        return PreparedRequest("z.ai", self._config.zai.base_url, upstream_headers, body)

    def prepare_count_tokens(
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
        upstream_headers = self._headers.build_zai_headers(headers, self._config.zai.api_key)
        return PreparedRequest("z.ai", self._config.zai.base_url, upstream_headers, body)
