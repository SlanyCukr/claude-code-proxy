"""FastAPI route handlers."""

import json
from json import JSONDecodeError
from typing import Any

from fastapi import Request, Response
from fastapi.responses import StreamingResponse

from core.config import Config
from core.protocols import RequestLogger
from ui.log_utils import write_incoming_log

MAX_BODY_SIZE = 50 * 1024 * 1024  # 50MB


async def _parse_json_body(request: Request) -> tuple[dict[str, Any], dict[str, str]] | Response:
    """Parse request body as JSON, return (body, headers) or error Response."""
    raw_body = await request.body()
    if len(raw_body) > MAX_BODY_SIZE:
        return Response(
            content='{"error": "Request body too large"}',
            status_code=413,
            media_type="application/json",
        )

    text_body = raw_body.decode("utf-8", errors="replace")
    try:
        body = json.loads(text_body)
    except (JSONDecodeError, ValueError) as e:
        write_incoming_log(request.method, request.url.path, dict(request.headers), text_body)
        return Response(
            content=f'{{"error": "Invalid JSON: {e}"}}',
            status_code=400,
            media_type="application/json",
        )

    headers = dict(request.headers)
    write_incoming_log(request.method, request.url.path, headers, body)
    return body, headers


async def handle_messages(
    request: Request,
    config: Config,
    logger: RequestLogger,
) -> Response | StreamingResponse:
    """Handle /v1/messages endpoint with routing logic."""
    result = await _parse_json_body(request)
    if isinstance(result, Response):
        return result
    body, headers = result

    routing_service = request.app.state.routing_service
    prepared = routing_service.prepare_messages(body, headers)
    upstream = request.app.state.upstream_client

    return await upstream.proxy_messages(
        prepared.body,
        prepared.headers,
        prepared.target_url,
        logger,
        prepared.route_name,
    )


async def handle_count_tokens(
    request: Request,
    config: Config,
    logger: RequestLogger,
) -> Response:
    """Handle /v1/messages/count_tokens with routing logic."""
    result = await _parse_json_body(request)
    if isinstance(result, Response):
        return result
    body, headers = result

    routing_service = request.app.state.routing_service
    prepared = routing_service.prepare_count_tokens(body, headers)
    upstream = request.app.state.upstream_client

    return await upstream.proxy_count_tokens(
        prepared.body,
        prepared.headers,
        prepared.target_url,
        logger,
        prepared.route_name,
    )


async def handle_event_logging_batch(
    request: Request,
    _config: Config,
) -> Response:
    """Discard /api/event_logging/batch requests."""
    await request.body()  # consume body
    return Response(status_code=204)
