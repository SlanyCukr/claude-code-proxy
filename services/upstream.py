"""HTTP proxying utilities for upstream requests."""

from typing import Any

import httpx
from fastapi import Response
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from core.config import Config
from core.exceptions import UpstreamConnectionError, UpstreamTimeoutError
from core.router import Route
from ui.dashboard import Dashboard

_DISPLAY_NAMES: dict[Route, str] = {"anthropic": "Anthropic", "zai": "z.ai"}


def _build_response(response: httpx.Response) -> Response:
    """Build a FastAPI Response from an httpx Response.

    Args:
        response: The httpx Response to convert.

    Returns:
        A FastAPI Response with status, content, and media type from the
        httpx Response.
    """
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type", "application/json"),
    )


class UpstreamClient:
    """Proxy requests to upstream services with streaming support."""

    def __init__(
        self,
        anthropic_client: httpx.AsyncClient,
        zai_client: httpx.AsyncClient,
        config: Config,
    ) -> None:
        self._clients: dict[Route, httpx.AsyncClient] = {
            "anthropic": anthropic_client,
            "zai": zai_client,
        }
        self._config = config

    async def proxy_request(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: Dashboard,
        route: Route,
        endpoint: str = "/v1/messages",
    ) -> Response | StreamingResponse:
        """Proxy a request to the upstream provider.

        Args:
            body: Request body as JSON-serializable dict.
            headers: Request headers.
            target_url: Base URL of the target provider.
            logger: Logger for request/response tracking.
            route: Route key for client selection.
            endpoint: Endpoint path (default: /v1/messages).

        Returns:
            Response or StreamingResponse from upstream.

        Raises:
            UpstreamTimeoutError: If the upstream request times out.
            UpstreamConnectionError: If connection to upstream fails.
        """
        client = self._clients[route]
        display_name = _DISPLAY_NAMES[route]
        is_streaming = body.get("stream", False)

        try:
            if endpoint == "/v1/messages/count_tokens":
                return await self._count_tokens_request(
                    client, body, headers, target_url, logger, display_name
                )
            if is_streaming:
                return await self._streaming_request(
                    client, body, headers, target_url, logger, display_name
                )
            return await self._non_streaming_request(
                client, body, headers, target_url, logger, display_name
            )
        except httpx.TimeoutException as e:
            logger.log_error(display_name, 504, "Upstream timeout")
            raise UpstreamTimeoutError(
                f"Timeout connecting to {display_name}", provider=route
            ) from e
        except httpx.ConnectError as e:
            logger.log_error(display_name, 502, str(e))
            raise UpstreamConnectionError(
                f"Connection error to {display_name}: {e}", provider=route
            ) from e
        except httpx.RequestError as e:
            logger.log_error(display_name, 502, str(e))
            raise UpstreamConnectionError(
                f"Request error to {display_name}: {e}", provider=route
            ) from e

    async def _count_tokens_request(
        self,
        client: httpx.AsyncClient,
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: Dashboard,
        route_name: str,
    ) -> Response:
        """Handle /v1/messages/count_tokens request."""
        response = await client.post(
            f"{target_url}/v1/messages/count_tokens",
            json=body,
            headers=headers,
            timeout=self._config.limits.token_count_timeout,
        )
        self._log_non_200(response, logger, route_name)
        return _build_response(response)

    async def _streaming_request(
        self,
        client: httpx.AsyncClient,
        body: dict[str, Any],
        headers: dict[str, str],
        target_url: str,
        logger: Dashboard,
        route_name: str,
    ) -> Response | StreamingResponse:
        """Handle streaming request with proper status code propagation.

        Returns:
            Response for non-200 status codes (e.g., 400 from Anthropic),
            or StreamingResponse for successful streaming requests.

        Raises:
            httpx.TimeoutException: If the upstream request times out.
            httpx.ConnectError: If connection to upstream fails.
            httpx.RequestError: If the request fails for other reasons.
        """
        req = client.build_request(
            "POST",
            f"{target_url}/v1/messages",
            json=body,
            headers=headers,
            timeout=self._config.limits.message_timeout,
        )
        response = await client.send(req, stream=True)

        if response.status_code != 200:
            error_body = await response.aread()
            logger.log_error(route_name, response.status_code, error_body.decode())
            await response.aclose()
            # Return error response for non-200 status codes
            # (e.g., 400 from Anthropic for invalid requests)
            error_response = httpx.Response(
                status_code=response.status_code,
                content=error_body,
                headers=response.headers,
                request=response.request,
            )
            return _build_response(error_response)

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
        logger: Dashboard,
        route_name: str,
    ) -> Response:
        """Handle non-streaming request.

        Raises:
            httpx.TimeoutException: If the upstream request times out.
            httpx.ConnectError: If connection to upstream fails.
            httpx.RequestError: If the request fails for other reasons.
        """
        response = await client.post(
            f"{target_url}/v1/messages",
            json=body,
            headers=headers,
            timeout=self._config.limits.message_timeout,
        )
        self._log_non_200(response, logger, route_name)
        return _build_response(response)

    def _log_non_200(
        self, response: httpx.Response, logger: Dashboard, route_name: str
    ) -> None:
        """Log error if response status code is not 200."""
        if response.status_code != 200:
            logger.log_error(route_name, response.status_code, response.text)
