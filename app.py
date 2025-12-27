"""FastAPI application factory."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request

from api.handlers import handle_count_tokens, handle_event_logging_batch, handle_messages
from core.config import Config
from core.headers import HeaderBuilder
from core.protocols import RequestLogger
from core.router import RouteDecider
from core.sanitize import RequestSanitizer
from core.transform import RequestTransformer
from services.routing_service import RoutingService
from services.upstream import UpstreamClient


def create_app(config: Config, logger: RequestLogger) -> FastAPI:
    """Create and configure the FastAPI application."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
        anthropic_client = httpx.AsyncClient(
            base_url=config.anthropic.base_url,
            timeout=300.0,
            limits=limits,
        )
        zai_client = httpx.AsyncClient(
            base_url=config.zai.base_url,
            timeout=300.0,
            limits=limits,
        )
        app.state.upstream_client = UpstreamClient(anthropic_client, zai_client)
        app.state.routing_service = RoutingService(
            config=config,
            logger=logger,
            decider=RouteDecider(),
            transformer=RequestTransformer(),
            sanitizer=RequestSanitizer(),
            header_builder=HeaderBuilder(),
        )
        try:
            yield
        finally:
            await anthropic_client.aclose()
            await zai_client.aclose()

    app = FastAPI(title="Claude Code Proxy", version="0.1.0", lifespan=lifespan)

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
