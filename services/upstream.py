"""HTTP proxying utilities for upstream requests."""

from typing import Any

import httpx
from fastapi import Response
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from core.protocols import RequestLogger


class UpstreamClient:
    """Proxy requests to upstream services with streaming support."""

    def __init__(
        self,
        anthropic_client: httpx.AsyncClient,
        zai_client: httpx.AsyncClient,
    ) -> None:
        self._clients = {
            "Anthropic": anthropic_client,
            "z.ai": zai_client,
        }

    def _error_response(self, status: int, message: str) -> Response:
        """Create a standardized error response."""
        return Response(
            content=f'{{"error": "{message}"}}',
            status_code=status,
            media_type="application/json",
        )

    async def proxy_request(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: RequestLogger,
        route_name: str,
        endpoint: str = "/v1/messages",
    ) -> Response | StreamingResponse:
        """Proxy a request to the upstream provider.

        Args:
            body: Request body as JSON-serializable dict.
            headers: Request headers.
            target_url: Base URL of the target provider.
            logger: Logger for request/response tracking.
            route_name: Name of the route (for client selection).
            endpoint: Endpoint path (default: /v1/messages).

        Returns:
            Response or StreamingResponse from upstream.
        """
        client = self._client_for(route_name)

        # Handle /v1/messages/count_tokens endpoint
        if endpoint == "/v1/messages/count_tokens":
            return await self._count_tokens_request(
                client, body, headers, target_url, logger, route_name
            )

        # Handle /v1/messages endpoint (streaming or non-streaming)
        is_streaming = body.get("stream", False)

        try:
            if is_streaming:
                return await self._streaming_request(
                    client, body, headers, target_url, logger, route_name
                )
            return await self._non_streaming_request(
                client, body, headers, target_url, logger, route_name
            )
        except httpx.TimeoutException:
            logger.log_error(route_name, 504, "Upstream timeout")
            return self._error_response(504, "Upstream timeout")
        except httpx.RequestError as e:
            logger.log_error(route_name, 502, str(e))
            return self._error_response(502, f"Upstream connection error: {e}")

    async def _count_tokens_request(
        self,
        client: httpx.AsyncClient,
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: RequestLogger,
        route_name: str,
    ) -> Response:
        """Handle /v1/messages/count_tokens request."""
        try:
            response = await client.post(
                f"{target_url}/v1/messages/count_tokens",
                json=body,
                headers=headers,
                timeout=60.0,
            )
            self._log_non_200(response, logger, route_name)
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type=response.headers.get("content-type", "application/json"),
            )
        except httpx.TimeoutException:
            logger.log_error(route_name, 504, "Upstream timeout")
            return self._error_response(504, "Upstream timeout")
        except httpx.RequestError as e:
            logger.log_error(route_name, 502, str(e))
            return self._error_response(502, f"Upstream connection error: {e}")

    async def _streaming_request(
        self,
        client: httpx.AsyncClient,
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: RequestLogger,
        route_name: str,
    ) -> Response | StreamingResponse:
        """Handle streaming request with proper status code propagation."""
        req = client.build_request(
            "POST",
            f"{target_url}/v1/messages",
            json=body,
            headers=headers,
            timeout=300.0,
        )
        response = await client.send(req, stream=True)

        if response.status_code != 200:
            error_body = await response.aread()
            logger.log_error(route_name, response.status_code, error_body.decode())
            await response.aclose()
            return Response(
                content=error_body,
                status_code=response.status_code,
                media_type=response.headers.get("content-type", "application/json"),
            )

        return StreamingResponse(
            response.aiter_bytes(),
            status_code=200,
            media_type=response.headers.get("content-type", "text/event-stream"),
            background=BackgroundTask(self._cleanup_streaming, response),
        )

    async def _cleanup_streaming(self, response: httpx.Response) -> None:
        """Clean up streaming resources."""
        await response.aclose()

    async def _non_streaming_request(
        self,
        client: httpx.AsyncClient,
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: RequestLogger,
        route_name: str,
    ) -> Response:
        """Handle non-streaming request."""
        response = await client.post(
            f"{target_url}/v1/messages",
            json=body,
            headers=headers,
            timeout=300.0,
        )
        self._log_non_200(response, logger, route_name)
        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=response.headers.get("content-type", "application/json"),
        )

    def _log_non_200(
        self, response: httpx.Response, logger: RequestLogger, route_name: str
    ) -> None:
        """Log error if response status code is not 200."""
        if response.status_code != 200:
            logger.log_error(route_name, response.status_code, response.text)

    def _client_for(self, route_name: str) -> httpx.AsyncClient:
        """Select the appropriate cached client."""
        return self._clients.get(route_name, self._clients["Anthropic"])
