"""FastAPI route handlers."""

import json
from json import JSONDecodeError
from typing import Any

from fastapi import Request, Response
from fastapi.responses import StreamingResponse

from core.config import Config
from core.exceptions import InvalidJSON, RequestTooLarge
from ui.dashboard import Dashboard
from ui.log_utils import write_incoming_log


async def _parse_json_body(
    request: Request, max_body_size: int
) -> tuple[dict[str, Any], dict[str, str]]:
    """Parse request body as JSON, return (body, headers)."""
    raw_body = await request.body()
    if len(raw_body) > max_body_size:
        raise RequestTooLarge("Request body too large")

    try:
        text_body = raw_body.decode("utf-8")
    except UnicodeDecodeError as e:
        raise InvalidJSON(f"Invalid UTF-8 encoding: {e}") from e

    try:
        body = json.loads(text_body)
    except JSONDecodeError as e:
        write_incoming_log(request.method, request.url.path, dict(request.headers), text_body)
        raise InvalidJSON(f"Invalid JSON: {e}") from e

    headers = dict(request.headers)
    write_incoming_log(request.method, request.url.path, headers, body)
    return body, headers


async def _handle_proxy_request(
    request: Request,
    config: Config,
    logger: Dashboard,
    endpoint: str,
) -> Response | StreamingResponse:
    """Common logic for proxied requests.

    Args:
        request: The FastAPI request.
        config: Application configuration.
        logger: Logger for request/response tracking.
        endpoint: The endpoint path (e.g., "/v1/messages" or "/v1/messages/count_tokens").

    Returns:
        Response or StreamingResponse from the upstream provider.
    """
    body, headers = await _parse_json_body(request, config.limits.max_body_size)

    routing_service = request.app.state.routing_service
    if endpoint == "/v1/messages":
        route, target_url, upstream_headers, prepared_body = routing_service.prepare_messages(
            body, headers
        )
    else:
        route, target_url, upstream_headers, prepared_body = routing_service.prepare_count_tokens(
            body, headers
        )

    upstream = request.app.state.upstream_client
    return await upstream.proxy_request(
        prepared_body, upstream_headers, target_url, logger, route, endpoint
    )


async def handle_messages(
    request: Request,
    config: Config,
    logger: Dashboard,
) -> Response | StreamingResponse:
    """Handle /v1/messages endpoint."""
    return await _handle_proxy_request(request, config, logger, "/v1/messages")


async def handle_count_tokens(
    request: Request,
    config: Config,
    logger: Dashboard,
) -> Response | StreamingResponse:
    """Handle /v1/messages/count_tokens endpoint."""
    return await _handle_proxy_request(request, config, logger, "/v1/messages/count_tokens")


async def handle_event_logging_batch(
    request: Request,
    _config: Config,
) -> Response:
    """Discard /api/event_logging/batch requests."""
    await request.body()  # consume body
    return Response(status_code=204)
