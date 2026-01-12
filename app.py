"""FastAPI application factory."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response

from api.handlers import handle_count_tokens, handle_event_logging_batch, handle_messages
from core.config import Config
from core.exceptions import InvalidJSON, RequestTooLarge
from services.routing_service import RoutingService
from services.upstream import UpstreamClient
from ui.dashboard import Dashboard


def create_app(config: Config, logger: Dashboard) -> FastAPI:
    """Create and configure the FastAPI application."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        limits = httpx.Limits(
            max_connections=config.limits.max_connections,
            max_keepalive_connections=config.limits.max_keepalive,
        )
        anthropic_client = httpx.AsyncClient(
            base_url=config.anthropic.base_url,
            timeout=config.limits.timeout,
            limits=limits,
        )
        zai_client = httpx.AsyncClient(
            base_url=config.zai.base_url,
            timeout=config.limits.timeout,
            limits=limits,
        )
        app.state.upstream_client = UpstreamClient(
            anthropic_client, zai_client, config
        )
        app.state.routing_service = RoutingService(
            config=config,
            logger=logger,
        )
        try:
            yield
        finally:
            await anthropic_client.aclose()
            await zai_client.aclose()

    app = FastAPI(title="Claude Code Proxy", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(RequestTooLarge)
    async def request_too_large_handler(request: Request, exc: RequestTooLarge) -> Response:
        return Response(
            content='{"error": "Request body too large"}',
            status_code=413,
            media_type="application/json",
        )

    @app.exception_handler(InvalidJSON)
    async def invalid_json_handler(request: Request, exc: InvalidJSON) -> Response:
        return Response(
            content=f'{{"error": "{exc}"}}',
            status_code=400,
            media_type="application/json",
        )

    @app.post("/v1/messages")
    async def proxy_messages(request: Request):
        return await handle_messages(request, config, logger)

    @app.post("/v1/messages/count_tokens")
    async def proxy_count_tokens(request: Request):
        return await handle_count_tokens(request, config, logger)

    @app.post("/api/event_logging/batch")
    async def proxy_event_logging_batch(request: Request):
        return await handle_event_logging_batch(request, config)

    return app
