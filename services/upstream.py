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

    async def proxy_messages(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: RequestLogger,
        route_name: str,
    ) -> Response | StreamingResponse:
        """Proxy /v1/messages requests."""
        return await self._proxy_request(body, headers, target_url, logger, route_name)

    async def proxy_count_tokens(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: RequestLogger,
        route_name: str,
    ) -> Response:
        """Proxy /v1/messages/count_tokens requests."""
        client = self._client_for(route_name)
        try:
            response = await client.post(
                f"{target_url}/v1/messages/count_tokens",
                json=body,
                headers=headers,
                timeout=60.0,
            )
            if response.status_code != 200:
                logger.log_error(route_name, response.status_code, response.text)
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type=response.headers.get("content-type", "application/json"),
            )
        except httpx.TimeoutException:
            logger.log_error(route_name, 504, "Upstream timeout")
            return Response(
                content='{"error": "Upstream timeout"}',
                status_code=504,
                media_type="application/json",
            )
        except httpx.RequestError as e:
            logger.log_error(route_name, 502, str(e))
            return Response(
                content=f'{{"error": "Upstream connection error: {e}"}}',
                status_code=502,
                media_type="application/json",
            )

    async def _proxy_request(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: RequestLogger,
        route_name: str,
    ) -> Response | StreamingResponse:
        """Execute the proxied request (streaming or non-streaming)."""
        is_streaming = body.get("stream", False)

        try:
            if is_streaming:
                return await self._streaming_request(body, headers, target_url, logger, route_name)
            return await self._non_streaming_request(body, headers, target_url, logger, route_name)
        except httpx.TimeoutException:
            logger.log_error(route_name, 504, "Upstream timeout")
            return Response(
                content='{"error": "Upstream timeout"}',
                status_code=504,
                media_type="application/json",
            )
        except httpx.RequestError as e:
            logger.log_error(route_name, 502, str(e))
            return Response(
                content=f'{{"error": "Upstream connection error: {e}"}}',
                status_code=502,
                media_type="application/json",
            )

    async def _streaming_request(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: RequestLogger,
        route_name: str,
    ) -> Response | StreamingResponse:
        """Handle streaming request with proper status code propagation."""
        client = self._client_for(route_name)

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
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: RequestLogger,
        route_name: str,
    ) -> Response:
        """Handle non-streaming request."""
        client = self._client_for(route_name)
        response = await client.post(
            f"{target_url}/v1/messages",
            json=body,
            headers=headers,
            timeout=300.0,
        )

        if response.status_code != 200:
            logger.log_error(route_name, response.status_code, response.text)

        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=response.headers.get("content-type", "application/json"),
        )

    def _client_for(self, route_name: str) -> httpx.AsyncClient:
        """Select the appropriate cached client."""
        return self._clients.get(route_name, self._clients["Anthropic"])
